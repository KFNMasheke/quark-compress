"""Double-click bootstrap; installs into a repository-local isolated environment."""
from pathlib import Path
import os
import subprocess
import sys
import urllib.request
import webbrowser
import threading

ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)

def main():
    url = "http://127.0.0.1:3881"
    try:
        with urllib.request.urlopen(url + "/api/session", timeout=1) as response:
            if b'"backend"' in response.read(4096):
                webbrowser.open(url)
                return
    except OSError:
        pass
    if sys.version_info < (3, 11):
        raise RuntimeError("Install Python 3.11 or newer, then reopen Quark.")
    python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    flags = {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}
    marker = ROOT / ".venv" / "quark-gui-installed"
    if not marker.exists():
        import tkinter as tk
        from tkinter import ttk
        window = tk.Tk()
        window.title("Opening Quark")
        window.geometry("420x150")
        window.resizable(False, False)
        tk.Label(window, text="Setting up your local Quark workspace", font=("Arial", 13)).pack(pady=(25, 10))
        tk.Label(window, text="First launch needs internet access. This can take a few minutes.").pack()
        progress = ttk.Progressbar(window, mode="indeterminate", length=350)
        progress.pack(pady=15)
        progress.start()
        window.protocol("WM_DELETE_WINDOW", lambda: None)
        errors = []
        finished = threading.Event()
        def install():
            try:
                if not python.exists():
                    subprocess.run([sys.executable, "-m", "venv", str(ROOT / ".venv")], check=True, **flags)
                subprocess.run([str(python), "-m", "pip", "install", "-e", str(ROOT)], check=True, **flags)
                marker.write_text("installed\n")
            except Exception as error:
                errors.append(error)
            finally:
                finished.set()
        def check():
            if finished.is_set():
                window.destroy()
            else:
                window.after(100, check)
        threading.Thread(target=install, daemon=True).start()
        window.after(100, check)
        window.mainloop()
        if errors:
            raise errors[0]
    subprocess.run([str(python), "-m", "quarkcompress.gui"], check=True, **flags)

if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        import tkinter.messagebox
        tkinter.messagebox.showerror("Quark could not open", str(error))
