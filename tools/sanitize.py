"""Build a separate ASan/UBSan extension and test it without replacing production binaries.

Linux developer tool; requires GCC, libasan, Python development headers and
setuptools. Leak detection is disabled for the host interpreter. No guarantee
of parser safety follows from a passing finite test run.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    if not sys.platform.startswith("linux"):
        raise SystemExit("This sanitizer helper currently supports Linux/GCC only")
    compiler = shutil.which("cc")
    if not compiler:
        raise SystemExit("A C compiler is required")
    libasan = subprocess.check_output([compiler, "-print-file-name=libasan.so"], text=True).strip()
    if not Path(libasan).is_file():
        raise SystemExit("GCC AddressSanitizer runtime was not found")
    with tempfile.TemporaryDirectory(prefix="qcore-sanitizer-") as folder:
        root = Path(folder)
        library = root / "lib"
        env = dict(os.environ, CC=compiler,
                   LDSHARED=f"{compiler} -shared -fsanitize=address,undefined",
                   CFLAGS="-O1 -g -fsanitize=address,undefined -fno-omit-frame-pointer")
        subprocess.run([sys.executable, "setup.py", "build_ext", "--force",
                        "--build-temp", str(root / "objects"), "--build-lib", str(library)],
                       cwd=ROOT, env=env, check=True)
        if not list((library / "quarkcompress").glob("_qcore_native*.so")):
            raise SystemExit("Sanitized extension build was skipped or failed")
        shutil.copytree(ROOT / "quarkcompress", library / "quarkcompress", dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.so", "*.pyd", "__pycache__"))
        run_env = dict(os.environ, LD_PRELOAD=libasan, PYTHONPATH=str(library),
                       QUARK_PURE_PYTHON="0", ASAN_OPTIONS="detect_leaks=0:abort_on_error=1",
                       UBSAN_OPTIONS="halt_on_error=1:print_stacktrace=1")
        subprocess.run([sys.executable, "-c",
                        "from quarkcompress.qcore import BACKEND; assert BACKEND == 'native'"],
                       cwd=root, env=run_env, check=True)
        subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", str(ROOT / "tests"), "-v"],
                       cwd=root, env=run_env, check=True)


if __name__ == "__main__":
    main()
