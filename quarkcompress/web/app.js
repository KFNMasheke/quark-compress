"use strict";
const $ = (s) => document.querySelector(s);
let token = "",
  mode = "compress",
  file = null,
  busy = false;
const bytes = (n) =>
  n < 1024
    ? n + " B"
    : n < 1048576
      ? (n / 1024).toFixed(1) + " KiB"
      : (n / 1048576).toFixed(2) + " MiB";
const labels = {
  compress: [
    "Make room for more.",
    "Compress a file, verify every byte, and take the result with you.",
    "Compress a file",
    "Compress & verify ↗",
  ],
  compare: [
    "Find your best fit.",
    "Compare four engines on your actual file. Download the smallest verified result.",
    "Compare engines",
    "Compare & verify ↗",
  ],
  restore: [
    "Bring every byte back.",
    "Restore QCore, gzip, Zstandard, or XZ files locally.",
    "Restore a file",
    "Restore file ↗",
  ],
};
function status(text, error = false) {
  $("#status").textContent = text;
  $("#status").classList.toggle("error", error);
}
function update() {
  const l = labels[mode];
  $("#title").textContent = l[0];
  $("#subtitle").textContent = l[1];
  $("#operation").textContent = l[2];
  $("#run").textContent = busy ? "Working…" : l[3];
  $("#run").disabled = busy || !file || !token;
  $("#engine-field").hidden = mode !== "compress";
  $("#mode-note").textContent =
    mode === "compare"
      ? "Tests raw storage, Zstandard 3, Gzip 9, and experimental QCore 2. Timings include byte verification. QCore can take longer on large files."
      : mode === "restore"
        ? "Restored output is capped at 32 MiB. Concatenated archives are rejected. Raw files already contain their original bytes."
        : "Every compression is restored and compared with your original before download.";
  document.querySelectorAll("[data-mode]").forEach((b) => {
    b.disabled = busy;
    b.classList.toggle("active", b.dataset.mode === mode);
    b.setAttribute("aria-pressed", String(b.dataset.mode === mode));
  });
}
function choose(f) {
  if (busy) return;
  file = f;
  $("#file-label").textContent = f
    ? f.name + " · " + bytes(f.size)
    : "Drop your file here";
  status(f ? "Ready when you are." : "Choose a file to begin.");
  update();
}
document.querySelectorAll("[data-mode]").forEach((b) =>
  b.addEventListener("click", () => {
    mode = b.dataset.mode;
    update();
  }),
);
$("#file").addEventListener("change", (e) => choose(e.target.files[0]));
$("#drop").addEventListener("dragover", (e) => {
  e.preventDefault();
  $("#drop").classList.add("drag");
});
$("#drop").addEventListener("dragleave", () =>
  $("#drop").classList.remove("drag"),
);
$("#drop").addEventListener("drop", (e) => {
  e.preventDefault();
  $("#drop").classList.remove("drag");
  choose(e.dataTransfer.files[0]);
});
async function json(url, options) {
  const r = await fetch(url, options);
  const data = await r.json();
  if (!r.ok) throw Error(data.error || "Workspace request failed");
  return data;
}
const delay = (ms) => new Promise((r) => setTimeout(r, ms));
$("#run").addEventListener("click", async () => {
  busy = true;
  update();
  $("#result").hidden = true;
  $("#empty").hidden = false;
  try {
    status("Uploading to your local workspace…");
    const q = new URLSearchParams({
      name: file.name,
      mode,
      codec: $("#codec").value,
    });
    const job = await json("/api/jobs?" + q, {
      method: "POST",
      headers: { "X-Quark-Token": token },
      body: file,
    });
    let result;
    do {
      await delay(300);
      result = await json("/api/jobs/" + job.id);
      status(result.progress || "Working…");
    } while (result.status === "running");
    if (result.status === "failed") throw Error(result.error);
    $("#empty").hidden = true;
    $("#result").hidden = false;
    $("#result-name").textContent = result.filename;
    $("#verified").textContent = result.verified
      ? "✓ Byte-for-byte verified"
      : "✓ Decoded · original hash comparison required";
    $("#original").textContent = bytes(result.input_bytes);
    $("#packed").textContent = bytes(result.output_bytes);
    $("#saving").textContent = result.input_bytes
      ? ((1 - result.output_bytes / result.input_bytes) * 100).toFixed(1) + "%"
      : "—";
    $("#saving-label").textContent =
      mode === "restore" ? "Size change" : "Space saved";
    $("#result-message").textContent = result.message;
    $("#timing").textContent =
      "Total operation: " + result.seconds.toFixed(3) + " s";
    $("#hash").textContent = result.sha256;
    const tbody = $("#trials tbody");
    tbody.replaceChildren();
    $("#trials").hidden = !result.trials.length;
    for (const t of result.trials) {
      const row = document.createElement("tr");
      for (const value of [
        t.codec,
        bytes(t.output_bytes),
        (t.encode_seconds * 1000).toFixed(2) + " ms",
        (t.decode_seconds * 1000).toFixed(2) + " ms",
      ]) {
        const cell = document.createElement("td");
        cell.textContent = value;
        row.append(cell);
      }
      tbody.append(row);
    }
    $("#download").href = "/api/jobs/" + job.id + "/download";
    status(
      "Complete. Your last two results stay in memory until you close the workspace.",
    );
  } catch (e) {
    status(e.message, true);
  } finally {
    busy = false;
    update();
  }
});
json("/api/session")
  .then((s) => {
    token = s.token;
    $("#connection").textContent = "● Local session · " + s.backend;
    update();
  })
  .catch(() => {
    $("#connection").textContent = "Connection unavailable";
    status("Could not connect. Reopen Quark to try again.", true);
  });

$("#shutdown").addEventListener("click", async () => {
  if (busy) {
    status("Wait for the current operation to finish before closing.");
    return;
  }
  try {
    await json("/api/shutdown", {
      method: "POST",
      headers: { "X-Quark-Token": token },
    });
    token = "";
    update();
    $("#connection").textContent = "Workspace closed";
    status("Workspace closed. Reopen Quark to start a new session.");
  } catch (e) {
    status(e.message, true);
  }
});
