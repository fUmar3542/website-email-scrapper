"""Tkinter front end for the website email scraper."""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import __version__
from .scraper import ScraperError, ScrapeOutput, scrape_file

logger = logging.getLogger("email_tool")


def log_dir() -> Path:
    if sys.platform == "darwin":
        path = Path.home() / "Library" / "Logs" / "EmailTool"
    else:
        path = Path.home() / ".emailtool"
    path.mkdir(parents=True, exist_ok=True)
    return path


def setup_logging() -> Path:
    log_file = log_dir() / "emailtool.log"
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    return log_file


def open_folder(path: Path) -> None:
    if sys.platform == "darwin":
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


class App:
    def __init__(self, root: tk.Tk, log_file: Path) -> None:
        self.root = root
        self.log_file = log_file
        self.input_file: str | None = None
        self.cancel = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_output: ScrapeOutput | None = None

        root.title(f"Website Email Scraper {__version__}")
        root.geometry("620x480")
        root.minsize(520, 400)
        root.protocol("WM_DELETE_WINDOW", self.on_close)

        frm = ttk.Frame(root, padding=14)
        frm.pack(fill="both", expand=True)

        ttk.Label(
            frm,
            text="Choose an Excel (.xlsx) file with a column named “website”.",
        ).pack(anchor="w")

        row = ttk.Frame(frm)
        row.pack(fill="x", pady=(8, 8))
        self.file_var = tk.StringVar(value="No file selected")
        ttk.Label(row, textvariable=self.file_var, width=48).pack(side="left", fill="x", expand=True)
        self.browse_btn = ttk.Button(row, text="Choose file…", command=self.choose_file)
        self.browse_btn.pack(side="right")

        btns = ttk.Frame(frm)
        btns.pack(fill="x", pady=(0, 8))
        self.start_btn = ttk.Button(btns, text="Start", command=self.start, state="disabled")
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(btns, text="Cancel", command=self.cancel_run, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(btns, text="Open results folder", command=self.open_results, state="disabled")
        self.open_btn.pack(side="right")

        self.progress = ttk.Progressbar(frm, mode="determinate")
        self.progress.pack(fill="x")
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(frm, textvariable=self.status_var).pack(anchor="w", pady=(4, 6))

        box = ttk.Frame(frm)
        box.pack(fill="both", expand=True)
        self.log = tk.Text(box, height=12, state="disabled", wrap="word")
        scroll = ttk.Scrollbar(box, command=self.log.yview)
        self.log.configure(yscrollcommand=scroll.set)
        self.log.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        self.root.after(100, self.poll)

    # ---- UI helpers
    def write_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def set_running(self, running: bool) -> None:
        self.start_btn.configure(state="disabled" if running or not self.input_file else "normal")
        self.browse_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    # ---- actions
    def choose_file(self) -> None:
        path = filedialog.askopenfilename(
            title="Select your Excel file",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if path:
            self.input_file = path
            self.file_var.set(Path(path).name)
            self.start_btn.configure(state="normal")

    def start(self) -> None:
        if not self.input_file or (self.worker and self.worker.is_alive()):
            return
        self.cancel.clear()
        self.progress.configure(value=0, maximum=1)
        self.status_var.set("Starting…")
        self.write_log(f"Processing {self.input_file}")
        self.set_running(True)
        self.open_btn.configure(state="disabled")
        self.worker = threading.Thread(target=self.run_worker, args=(self.input_file,), daemon=True)
        self.worker.start()

    def cancel_run(self) -> None:
        self.cancel.set()
        self.status_var.set("Cancelling… finishing current sites.")
        self.cancel_btn.configure(state="disabled")

    def open_results(self) -> None:
        if self.last_output:
            open_folder(self.last_output.output_dir)

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Quit", "A run is in progress. Quit anyway?"):
                return
            self.cancel.set()
        self.root.destroy()

    # ---- worker thread (never touches Tk widgets; talks via the queue)
    def run_worker(self, path: str) -> None:
        def progress(done: int, total: int, site: str, msg: str) -> None:
            self.events.put(("progress", done, total, site, msg))

        try:
            out = scrape_file(path, progress=progress, cancel=self.cancel)
            self.events.put(("done", out))
        except ScraperError as exc:
            logger.warning("Scrape failed: %s", exc)
            self.events.put(("error", str(exc), False))
        except Exception as exc:
            logger.exception("Unexpected error")
            self.events.put(("error", str(exc), True))

    def poll(self) -> None:
        try:
            while True:
                self.handle(self.events.get_nowait())
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def handle(self, event: tuple) -> None:
        kind = event[0]
        if kind == "progress":
            _, done, total, site, msg = event
            self.progress.configure(maximum=total, value=done)
            self.status_var.set(f"{done} of {total} websites done")
            self.write_log(f"[{done}/{total}] {site}: {msg}")
        elif kind == "done":
            out: ScrapeOutput = event[1]
            self.last_output = out
            self.set_running(False)
            self.open_btn.configure(state="normal")
            title = "Cancelled (partial results saved)" if out.cancelled else "Finished"
            self.status_var.set(title)
            self.write_log(
                f"{title}: {out.sites_with_emails} with emails, "
                f"{out.sites_without_emails} without, {out.sites_unreachable} unreachable."
            )
            messagebox.showinfo(
                title,
                f"Websites with emails: {out.sites_with_emails}\n"
                f"Websites with no emails: {out.sites_without_emails}\n"
                f"Websites that could not be loaded: {out.sites_unreachable}\n"
                f"Total unique emails: {out.total_emails}\n\n"
                f"Results saved in:\n{out.output_dir}",
            )
        elif kind == "error":
            _, msg, unexpected = event
            self.set_running(False)
            self.status_var.set("Error")
            self.write_log(f"Error: {msg}")
            if unexpected:
                msg += f"\n\nPlease send this log file to support:\n{self.log_file}"
            messagebox.showerror("Error", msg)


def main() -> None:
    log_file = setup_logging()
    logger.info("EmailTool %s started", __version__)
    root = tk.Tk()
    App(root, log_file)
    root.mainloop()


if __name__ == "__main__":
    main()
