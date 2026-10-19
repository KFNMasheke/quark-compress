/* Original QCore accelerator, MIT License, Copyright (c) 2026 Kaziwale Masheke.
 * Emits and reads QKC1 token streams; does not call a third-party compressor.
 * CPython buffer lengths are checked before every indexed read/write.
 */
#define PY_SSIZE_T_CLEAN
#include <Python.h>
#include <stdint.h>
#include <string.h>

#define BLOCK_SIZE 262144
#define TOKEN_LIMIT (BLOCK_SIZE + BLOCK_SIZE / 128)
#define TABLE_SIZE 65536

static PyObject *bad(const char *message) {
    PyErr_SetString(PyExc_ValueError, message);
    return NULL;
}

static uint32_t hash4(const unsigned char *p) {
    uint32_t key = ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
                   | ((uint32_t)p[2] << 8) | p[3];
    return (key * UINT32_C(2654435761)) >> 16;
}

static void flush_literals(unsigned char *dst, Py_ssize_t *used,
                           const unsigned char *src, Py_ssize_t start,
                           Py_ssize_t count) {
    if (count) {
        dst[(*used)++] = (unsigned char)(count - 1);
        memcpy(dst + *used, src + start, (size_t)count);
        *used += count;
    }
}

static PyObject *lz_encode(PyObject *self, PyObject *args) {
    const unsigned char *src;
    Py_ssize_t n, used = 0, pos = 0, lit_start = 0, lit_count = 0;
    int32_t *head, *previous;
    PyObject *result;
    unsigned char *dst;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#", &src, &n)) return NULL;
    if (n > BLOCK_SIZE) return bad("Native LZ input exceeds block budget");
    head = PyMem_Malloc(TABLE_SIZE * sizeof(int32_t));
    previous = PyMem_Malloc((size_t)(n ? n : 1) * sizeof(int32_t));
    if (!head || !previous) {
        PyMem_Free(head); PyMem_Free(previous); return PyErr_NoMemory();
    }
    memset(head, 255, TABLE_SIZE * sizeof(int32_t));
    result = PyBytes_FromStringAndSize(NULL, 2 * n + 16);
    if (!result) { PyMem_Free(head); PyMem_Free(previous); return NULL; }
    dst = (unsigned char *)PyBytes_AS_STRING(result);
    while (pos < n) {
        Py_ssize_t best = 0, distance = 0, advance, inserted;
        if (pos + 4 <= n) {
            int32_t start = head[hash4(src + pos)];
            unsigned attempts = 0;
            Py_ssize_t max_match = n - pos;
            if (max_match > 65535) max_match = 65535;
            while (start >= 0 && attempts++ < 64) {
                Py_ssize_t match = 0;
                if (pos - start > 65535) break;
                if (src[start] == src[pos] && src[start + 1] == src[pos + 1]
                    && src[start + 2] == src[pos + 2] && src[start + 3] == src[pos + 3]) {
                    match = 4;
                    while (match < max_match && src[start + match] == src[pos + match])
                        ++match;
                    if (match > best) { best = match; distance = pos - start; }
                    if (best == max_match) break;
                }
                start = previous[start];
            }
        }
        if (best >= 4) {
            flush_literals(dst, &used, src, lit_start, lit_count);
            lit_count = 0;
            dst[used++] = best >= 130 ? 255 : (unsigned char)(128 | (best - 3));
            dst[used++] = (unsigned char)(distance >> 8);
            dst[used++] = (unsigned char)distance;
            if (best >= 130) {
                dst[used++] = (unsigned char)(best >> 8);
                dst[used++] = (unsigned char)best;
            }
            advance = best;
        } else {
            if (!lit_count) lit_start = pos;
            ++lit_count;
            if (lit_count == 128) {
                flush_literals(dst, &used, src, lit_start, lit_count);
                lit_count = 0;
            }
            advance = 1;
        }
        for (inserted = pos; inserted < pos + advance; ++inserted) {
            if (inserted + 4 <= n) {
                uint32_t hash = hash4(src + inserted);
                previous[inserted] = head[hash];
                head[hash] = (int32_t)inserted;
            }
        }
        pos += advance;
    }
    flush_literals(dst, &used, src, lit_start, lit_count);
    PyMem_Free(head); PyMem_Free(previous);
    if (_PyBytes_Resize(&result, used) < 0) return NULL;
    return result;
}

static PyObject *lz_decode(PyObject *self, PyObject *args) {
    const unsigned char *src;
    Py_ssize_t n, expected, pos = 0, used = 0;
    PyObject *result;
    unsigned char *dst;
    const char *error = NULL;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#n", &src, &n, &expected)) return NULL;
    if (expected < 0 || expected > BLOCK_SIZE || n > TOKEN_LIMIT)
        return bad("Native LZ size budget exceeded");
    result = PyBytes_FromStringAndSize(NULL, expected);
    if (!result) return NULL;
    dst = (unsigned char *)PyBytes_AS_STRING(result);
    while (pos < n) {
        unsigned token = src[pos++];
        Py_ssize_t length;
        if (token < 128) {
            length = token + 1;
            if (length > n - pos || length > expected - used) {
                error = "Invalid LZ literal"; break;
            }
            memcpy(dst + used, src + pos, (size_t)length);
            pos += length; used += length;
        } else {
            Py_ssize_t distance, start, remaining;
            if (n - pos < 2) { error = "Truncated LZ distance"; break; }
            distance = ((Py_ssize_t)src[pos] << 8) | src[pos + 1]; pos += 2;
            length = (token & 127) + 3;
            if (token == 255) {
                if (n - pos < 2) { error = "Truncated extended LZ length"; break; }
                length = ((Py_ssize_t)src[pos] << 8) | src[pos + 1]; pos += 2;
                if (length < 130) { error = "Invalid extended LZ length"; break; }
            }
            if (distance < 1 || distance > used || length > expected - used) {
                error = "Invalid LZ match"; break;
            }
            start = used - distance; remaining = length;
            while (remaining) {
                Py_ssize_t count = used - start;
                if (count > remaining) count = remaining;
                memcpy(dst + used, dst + start, (size_t)count);
                used += count; remaining -= count;
            }
        }
    }
    if (error || used != expected) {
        Py_DECREF(result); return bad(error ? error : "LZ output size mismatch");
    }
    return result;
}

static PyObject *delta_transform(PyObject *args, int inverse) {
    const unsigned char *src;
    Py_ssize_t n, i;
    PyObject *result;
    unsigned char *dst;
    unsigned previous = 0;
    if (!PyArg_ParseTuple(args, "y#", &src, &n)) return NULL;
    if (n > BLOCK_SIZE) return bad("Native delta size budget exceeded");
    result = PyBytes_FromStringAndSize(NULL, n);
    if (!result) return NULL;
    dst = (unsigned char *)PyBytes_AS_STRING(result);
    for (i = 0; i < n; ++i) {
        if (inverse) { previous = (previous + src[i]) & 255; dst[i] = (unsigned char)previous; }
        else { dst[i] = (unsigned char)((src[i] - previous) & 255); previous = src[i]; }
    }
    return result;
}
static PyObject *delta(PyObject *self, PyObject *args) { (void)self; return delta_transform(args, 0); }
static PyObject *undelta(PyObject *self, PyObject *args) { (void)self; return delta_transform(args, 1); }

static PyObject *frequencies(PyObject *self, PyObject *args) {
    const unsigned char *src;
    Py_ssize_t n, i;
    uint32_t counts[256] = {0};
    PyObject *result;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#", &src, &n)) return NULL;
    if (n > TOKEN_LIMIT) return bad("Native frequency size budget exceeded");
    for (i = 0; i < n; ++i) ++counts[src[i]];
    result = PyList_New(256);
    if (!result) return NULL;
    for (i = 0; i < 256; ++i) {
        PyObject *count = PyLong_FromUnsignedLong(counts[i]);
        if (!count) { Py_DECREF(result); return NULL; }
        PyList_SET_ITEM(result, i, count);
    }
    return result;
}

/* Canonical tree validation shared by the encoder and decoder. */
static int canonical(const unsigned char *lengths, uint32_t *codes,
                     uint32_t *counts, uint32_t *first, uint32_t *offset,
                     unsigned char *ordered) {
    uint32_t code = 0, symbols = 0;
    unsigned length, symbol, max_length = 0;
    memset(counts, 0, 25 * sizeof(uint32_t));
    for (symbol = 0; symbol < 256; ++symbol) {
        if (lengths[symbol] > 24) return 0;
        if (lengths[symbol]) { ++counts[lengths[symbol]]; ++symbols; }
        if (lengths[symbol] > max_length) max_length = lengths[symbol];
    }
    if (!symbols) return 0;
    symbols = 0;
    for (length = 1; length <= 24; ++length) {
        code = (code + (length == 1 ? 0 : counts[length - 1])) << 1;
        first[length] = code; offset[length] = symbols;
        if (code + counts[length] > (UINT32_C(1) << length)) return 0;
        for (symbol = 0; symbol < 256; ++symbol) {
            if (lengths[symbol] == length) {
                codes[symbol] = code + symbols - offset[length];
                ordered[symbols++] = (unsigned char)symbol;
            }
        }
    }
    if (symbols == 1) return max_length == 1;
    return first[max_length] + counts[max_length] == (UINT32_C(1) << max_length);
}

static PyObject *huff_pack(PyObject *self, PyObject *args) {
    const unsigned char *src, *lengths;
    Py_ssize_t n, length_count, used = 260, i;
    uint32_t codes[256] = {0}, counts[25], first[25], offset[25];
    unsigned char ordered[256];
    uint64_t accumulator = 0;
    unsigned bits = 0;
    PyObject *result;
    unsigned char *dst;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#y#", &src, &n, &lengths, &length_count)) return NULL;
    if (n < 1 || n > TOKEN_LIMIT || length_count != 256)
        return bad("Native Huffman size budget exceeded");
    if (!canonical(lengths, codes, counts, first, offset, ordered))
        return bad("Invalid Huffman tree");
    for (i = 0; i < n; ++i) if (!lengths[src[i]]) return bad("Missing Huffman symbol");
    result = PyBytes_FromStringAndSize(NULL, 261 + 3 * n);
    if (!result) return NULL;
    dst = (unsigned char *)PyBytes_AS_STRING(result);
    dst[0] = (unsigned char)((uint32_t)n >> 24); dst[1] = (unsigned char)((uint32_t)n >> 16);
    dst[2] = (unsigned char)((uint32_t)n >> 8); dst[3] = (unsigned char)n;
    memcpy(dst + 4, lengths, 256);
    for (i = 0; i < n; ++i) {
        accumulator = (accumulator << lengths[src[i]]) | codes[src[i]];
        bits += lengths[src[i]];
        while (bits >= 8) { bits -= 8; dst[used++] = (unsigned char)(accumulator >> bits); }
        accumulator &= (UINT64_C(1) << bits) - 1;
    }
    if (bits) dst[used++] = (unsigned char)(accumulator << (8 - bits));
    if (_PyBytes_Resize(&result, used) < 0) return NULL;
    return result;
}

static int heap_less(int a, int b, const uint32_t *weights) {
    return weights[a] < weights[b] || (weights[a] == weights[b] && a < b);
}
static void heap_push(int *heap, int *size, int value, const uint32_t *weights) {
    int index = (*size)++;
    while (index) {
        int parent = (index - 1) / 2;
        if (!heap_less(value, heap[parent], weights)) break;
        heap[index] = heap[parent]; index = parent;
    }
    heap[index] = value;
}
static int heap_pop(int *heap, int *size, const uint32_t *weights) {
    int result = heap[0], value = heap[--(*size)], index = 0;
    while (index * 2 + 1 < *size) {
        int child = index * 2 + 1;
        if (child + 1 < *size && heap_less(heap[child + 1], heap[child], weights)) ++child;
        if (!heap_less(heap[child], value, weights)) break;
        heap[index] = heap[child]; index = child;
    }
    if (*size) heap[index] = value;
    return result;
}

static PyObject *huff_encode(PyObject *self, PyObject *args) {
    const unsigned char *src;
    Py_ssize_t n, i;
    uint32_t weights[512] = {0};
    int children_left[512], children_right[512], heap[256], heap_size = 0, serial = 256;
    int stack_node[512], stack_depth[512], stack_size = 0;
    unsigned char lengths[256] = {0};
    PyObject *length_object, *parameters, *result;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#", &src, &n)) return NULL;
    if (n > TOKEN_LIMIT) return bad("Native Huffman input budget exceeded");
    if (!n) Py_RETURN_NONE;
    for (i = 0; i < n; ++i) ++weights[src[i]];
    for (i = 0; i < 256; ++i) if (weights[i]) heap_push(heap, &heap_size, (int)i, weights);
    while (heap_size > 1) {
        int left = heap_pop(heap, &heap_size, weights);
        int right = heap_pop(heap, &heap_size, weights);
        weights[serial] = weights[left] + weights[right];
        children_left[serial] = left; children_right[serial] = right;
        heap_push(heap, &heap_size, serial, weights); ++serial;
    }
    stack_node[stack_size] = heap[0]; stack_depth[stack_size++] = 0;
    while (stack_size) {
        int node, depth;
        --stack_size; node = stack_node[stack_size]; depth = stack_depth[stack_size];
        if (node < 256) {
            if (depth > 24) Py_RETURN_NONE;
            lengths[node] = (unsigned char)(depth ? depth : 1);
        } else {
            stack_node[stack_size] = children_left[node]; stack_depth[stack_size++] = depth + 1;
            stack_node[stack_size] = children_right[node]; stack_depth[stack_size++] = depth + 1;
        }
    }
    length_object = PyBytes_FromStringAndSize((const char *)lengths, 256);
    if (!length_object) return NULL;
    parameters = PyTuple_Pack(2, PyTuple_GET_ITEM(args, 0), length_object);
    Py_DECREF(length_object);
    if (!parameters) return NULL;
    result = huff_pack(NULL, parameters);
    Py_DECREF(parameters);
    return result;
}

static PyObject *huff_decode(PyObject *self, PyObject *args) {
    const unsigned char *src, *encoded, *lengths;
    Py_ssize_t n, limit, expected, encoded_size, bitpos = 0, used;
    uint32_t codes[256] = {0}, counts[25], first[25], offset[25];
    unsigned char ordered[256], fast_symbol[256] = {0}, fast_length[256] = {0};
    PyObject *result;
    unsigned char *dst;
    unsigned symbol, length;
    const char *error = NULL;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#n", &src, &n, &limit)) return NULL;
    if (limit < 1 || limit > TOKEN_LIMIT || n < 261 || n > 261 + 3 * TOKEN_LIMIT)
        return bad("Invalid native Huffman size");
    {
        uint32_t declared = ((uint32_t)src[0] << 24) | ((uint32_t)src[1] << 16)
                            | ((uint32_t)src[2] << 8) | src[3];
        if (declared > (uint32_t)limit) return bad("Huffman expansion exceeds budget");
        expected = (Py_ssize_t)declared;
    }
    if (expected < 1 || expected > limit) return bad("Huffman expansion exceeds budget");
    lengths = src + 4; encoded = src + 260; encoded_size = n - 260;
    if (!canonical(lengths, codes, counts, first, offset, ordered))
        return bad("Invalid Huffman tree");
    for (symbol = 0; symbol < 256; ++symbol) {
        length = lengths[symbol];
        if (length && length <= 8) {
            unsigned begin = codes[symbol] << (8 - length);
            unsigned end = begin + (1U << (8 - length)), i;
            for (i = begin; i < end; ++i) {
                fast_symbol[i] = (unsigned char)symbol; fast_length[i] = (unsigned char)length;
            }
        }
    }
    result = PyBytes_FromStringAndSize(NULL, expected);
    if (!result) return NULL;
    dst = (unsigned char *)PyBytes_AS_STRING(result);
    for (used = 0; used < expected; ++used) {
        uint32_t code = 0;
        if (encoded_size * 8 - bitpos >= 8) {
            Py_ssize_t bytepos = bitpos >> 3;
            unsigned pair = (unsigned)encoded[bytepos] << 8;
            unsigned prefix;
            if (bytepos + 1 < encoded_size) pair |= encoded[bytepos + 1];
            prefix = (pair >> (8 - (bitpos & 7))) & 255;
            if (fast_length[prefix]) {
                dst[used] = fast_symbol[prefix]; bitpos += fast_length[prefix]; continue;
            }
        }
        for (length = 1; length <= 24; ++length) {
            if (bitpos >= encoded_size * 8) { error = "Truncated Huffman bits"; break; }
            code = (code << 1) | ((encoded[bitpos >> 3] >> (7 - (bitpos & 7))) & 1);
            ++bitpos;
            if (code >= first[length] && code - first[length] < counts[length]) {
                dst[used] = ordered[offset[length] + code - first[length]]; break;
            }
        }
        if (error || length > 24) { if (!error) error = "Invalid Huffman code"; break; }
    }
    if (!error && (bitpos + 7) / 8 != encoded_size) error = "Trailing Huffman data";
    if (!error && (bitpos & 7) && (encoded[encoded_size - 1] & ((1U << (8 - (bitpos & 7))) - 1)))
        error = "Nonzero Huffman padding";
    if (error) { Py_DECREF(result); return bad(error); }
    return result;
}

static PyObject *factor(PyObject *self, PyObject *args) {
    const unsigned char *src;
    Py_ssize_t n, pos = 0, used[6] = {0};
    PyObject *buffers[6] = {NULL}, *result = NULL;
    unsigned char *dst[6];
    int i;
    const char *error = NULL;
    (void)self;
    if (!PyArg_ParseTuple(args, "y#", &src, &n)) return NULL;
    if (n > TOKEN_LIMIT) return bad("Factored token size budget exceeded");
    for (i = 0; i < 6; ++i) {
        buffers[i] = PyBytes_FromStringAndSize(NULL, n);
        if (!buffers[i]) goto cleanup;
        dst[i] = (unsigned char *)PyBytes_AS_STRING(buffers[i]);
    }
    while (pos < n) {
        unsigned token = src[pos++];
        dst[0][used[0]++] = (unsigned char)token;
        if (token < 128) {
            Py_ssize_t length = token + 1;
            if (length > n - pos) { error = "Truncated factored literals"; goto cleanup; }
            memcpy(dst[1] + used[1], src + pos, (size_t)length);
            used[1] += length; pos += length;
        } else {
            if (n - pos < 2) { error = "Truncated factored distance"; goto cleanup; }
            dst[2][used[2]++] = src[pos++]; dst[3][used[3]++] = src[pos++];
            if (token == 255) {
                if (n - pos < 2) { error = "Truncated factored length"; goto cleanup; }
                dst[4][used[4]++] = src[pos++]; dst[5][used[5]++] = src[pos++];
            }
        }
    }
    for (i = 0; i < 6; ++i) if (_PyBytes_Resize(&buffers[i], used[i]) < 0) goto cleanup;
    result = PyTuple_New(6);
    if (!result) goto cleanup;
    for (i = 0; i < 6; ++i) { PyTuple_SET_ITEM(result, i, buffers[i]); buffers[i] = NULL; }
cleanup:
    for (i = 0; i < 6; ++i) Py_XDECREF(buffers[i]);
    if (error) { Py_XDECREF(result); return bad(error); }
    return result;
}

static PyObject *join(PyObject *self, PyObject *args) {
    PyObject *fields, *result;
    const unsigned char *src[6];
    Py_ssize_t size[6], pos[6] = {0}, limit, total = 0, used = 0, c;
    unsigned char *dst;
    int i;
    const char *error = NULL;
    (void)self;
    if (!PyArg_ParseTuple(args, "O!n", &PyTuple_Type, &fields, &limit)) return NULL;
    if (limit < 0 || limit > TOKEN_LIMIT || PyTuple_GET_SIZE(fields) != 6)
        return bad("Invalid factored field count or limit");
    for (i = 0; i < 6; ++i) {
        PyObject *field = PyTuple_GET_ITEM(fields, i);
        if (!PyBytes_Check(field)) return bad("Factored fields must be bytes");
        size[i] = PyBytes_GET_SIZE(field);
        if (size[i] > limit - total) return bad("Factored field budget exceeded");
        total += size[i]; src[i] = (const unsigned char *)PyBytes_AS_STRING(field);
    }
    if (size[2] != size[3] || size[4] != size[5]) return bad("Factored field length mismatch");
    result = PyBytes_FromStringAndSize(NULL, total);
    if (!result) return NULL;
    dst = (unsigned char *)PyBytes_AS_STRING(result);
    for (c = 0; c < size[0]; ++c) {
        unsigned token = src[0][c];
        if (used >= total) { error = "Factored output exceeds budget"; break; }
        dst[used++] = (unsigned char)token;
        if (token < 128) {
            Py_ssize_t length = token + 1;
            if (length > size[1] - pos[1] || length > total - used) {
                error = "Truncated factored literals"; break;
            }
            memcpy(dst + used, src[1] + pos[1], (size_t)length);
            pos[1] += length; used += length;
        } else {
            if (pos[2] >= size[2] || total - used < 2) { error = "Truncated factored distance"; break; }
            dst[used++] = src[2][pos[2]++]; dst[used++] = src[3][pos[3]++];
            if (token == 255) {
                if (pos[4] >= size[4] || total - used < 2) { error = "Truncated factored length"; break; }
                dst[used++] = src[4][pos[4]++]; dst[used++] = src[5][pos[5]++];
            }
        }
    }
    for (i = 1; i < 6; ++i) if (pos[i] != size[i]) error = "Unused factored field data";
    if (!error && used != total) error = "Factored output size mismatch";
    if (error) { Py_DECREF(result); return bad(error); }
    return result;
}

static PyMethodDef methods[] = {
    {"lz_encode", lz_encode, METH_VARARGS, "Encode one bounded QCore LZ block."},
    {"lz_decode", lz_decode, METH_VARARGS, "Decode one bounded QCore LZ block."},
    {"delta", delta, METH_VARARGS, "Apply byte-delta transform."},
    {"undelta", undelta, METH_VARARGS, "Reverse byte-delta transform."},
    {"frequencies", frequencies, METH_VARARGS, "Count byte frequencies."},
    {"huff_pack", huff_pack, METH_VARARGS, "Pack canonical Huffman codes."},
    {"huff_encode", huff_encode, METH_VARARGS, "Build and encode a bounded Huffman model."},
    {"huff_decode", huff_decode, METH_VARARGS, "Decode bounded Huffman payload."},
    {"factor", factor, METH_VARARGS, "Factor bounded LZ token fields."},
    {"join", join, METH_VARARGS, "Reconstruct bounded LZ tokens from fields."},
    {NULL, NULL, 0, NULL}
};
static struct PyModuleDef module = { PyModuleDef_HEAD_INIT, "_qcore_native", NULL, -1, methods };
PyMODINIT_FUNC PyInit__qcore_native(void) { return PyModule_Create(&module); }
