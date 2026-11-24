"""Tkinter front end for the website email scraper.

Only native ttk widgets are used (no hard-coded colours), so the window follows
the system look, including macOS light/dark mode.
"""

from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from tkinter import font as tkfont

from . import __version__
from .scraper import ScraperError, ScrapeOutput, SiteResult, scrape_file

logger = logging.getLogger("email_tool")

IS_MAC = sys.platform == "darwin"
PAD = 16

HELP_TEXT = (
    "1. Choose an Excel (.xlsx) file with a column named “website”.\n"
    "2. Click Start. Each website's main page and up to 5 contact-style pages are checked.\n"
    "3. Results are saved in an “Output” folder next to your file:\n"
    "      • scraped_emails  (website, email, page found on)\n"
    "      • no_emails_found  (with the reason)\n"
    "      • summary\n\n"
    "You can cancel at any time; partial results are still saved."
)


def log_dir() -> Path:
    if IS_MAC:
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
    if IS_MAC:
        subprocess.run(["open", str(path)], check=False)
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.run(["xdg-open", str(path)], check=False)


def summarize_emails(emails: dict[str, str]) -> str:
    items = sorted(emails)
    text = ", ".join(items[:2])
    if len(items) > 2:
        text += f"  +{len(items) - 2} more"
    return text


class StatBlock(ttk.Frame):
    """A big number with a small caption underneath."""

    def __init__(self, parent: tk.Misc, caption: str, number_font: tkfont.Font) -> None:
        super().__init__(parent, relief="groove", borderwidth=1, padding=(12, 8))
        self.value = tk.StringVar(value="0")
        ttk.Label(self, textvariable=self.value, font=number_font, anchor="center").pack(fill="x")
        ttk.Label(self, text=caption, anchor="center").pack(fill="x")

    def set(self, n: int) -> None:
        self.value.set(str(n))


class App:
    def __init__(self, root: tk.Tk, log_file: Path) -> None:
        self.root = root
        self.log_file = log_file
        self.input_file: str | None = None
        self.cancel = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.last_output: ScrapeOutput | None = None
        self.running = False
        self.started_at = 0.0
        self.counts = {"with": 0, "none": 0, "bad": 0}

        self.setup_window()
        self.setup_style()
        self.build_menu()
        self.build_ui()
        self.root.after(100, self.poll)

    # ------------------------------------------------------------ setup
    def setup_window(self) -> None:
        r = self.root
        r.title("Website Email Scraper")
        r.minsize(680, 560)
        w, h = 780, 640
        x = max((r.winfo_screenwidth() - w) // 2, 0)
        y = max((r.winfo_screenheight() - h) // 3, 0)
        r.geometry(f"{w}x{h}+{x}+{y}")
        r.protocol("WM_DELETE_WINDOW", self.on_close)
        mod = "Command" if IS_MAC else "Control"
        r.bind(f"<{mod}-o>", lambda _e: self.choose_file())
        if IS_MAC:
            r.createcommand("tk::mac::Quit", self.on_close)

    def setup_style(self) -> None:
        style = ttk.Style()
        if sys.platform.startswith("linux") and "clam" in style.theme_names():
            style.theme_use("clam")
        base = tkfont.nametofont("TkDefaultFont")
        size = base.cget("size")
        self.title_font = tkfont.Font(family=base.cget("family"), size=size + 9, weight="bold")
        self.number_font = tkfont.Font(family=base.cget("family"), size=size + 10, weight="bold")
        self.small_font = tkfont.Font(family=base.cget("family"), size=max(size - 1, 8))
        style.configure("Treeview", rowheight=26)

    def build_menu(self) -> None:
        mod = "⌘" if IS_MAC else "Ctrl+"
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Choose File…", accelerator=f"{mod}O", command=self.choose_file)
        file_menu.add_command(label="Open Results Folder", command=self.open_results)
        if not IS_MAC:  # macOS puts Quit in the application menu
            file_menu.add_separator()
            file_menu.add_command(label="Exit", command=self.on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="How to Use", command=lambda: messagebox.showinfo("How to Use", HELP_TEXT))
        help_menu.add_command(label="Show Log Folder", command=lambda: open_folder(log_dir()))
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def build_ui(self) -> None:
        outer = ttk.Frame(self.root, padding=PAD)
        outer.pack(fill="both", expand=True)

        # Header
        header = ttk.Frame(outer)
        header.pack(fill="x")
        ttk.Label(header, text="Website Email Scraper", font=self.title_font).pack(anchor="w")
        ttk.Label(
            header,
            text="Find contact email addresses for a list of websites.",
            font=self.small_font,
        ).pack(anchor="w", pady=(2, 0))

        # Step 1: input file
        file_box = ttk.LabelFrame(outer, text="Input file", padding=12)
        file_box.pack(fill="x", pady=(PAD, 10))
        row = ttk.Frame(file_box)
        row.pack(fill="x")
        self.file_var = tk.StringVar(value="No file selected")
        self.file_entry = ttk.Entry(row, textvariable=self.file_var, state="readonly")
        self.file_entry.pack(side="left", fill="x", expand=True)
        self.browse_btn = ttk.Button(row, text="Choose File…", command=self.choose_file)
        self.browse_btn.pack(side="left", padx=(8, 0))
        ttk.Label(
            file_box,
            text="Excel (.xlsx) with a column named “website”, e.g. example.com",
            font=self.small_font,
        ).pack(anchor="w", pady=(6, 0))

        # Controls
        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(controls, text="Start", command=self.start, state="disabled")
        self.start_btn.pack(side="left")
        self.cancel_btn = ttk.Button(controls, text="Cancel", command=self.cancel_run, state="disabled")
        self.cancel_btn.pack(side="left", padx=8)
        self.open_btn = ttk.Button(
            controls, text="Open Results Folder", command=self.open_results, state="disabled"
        )
        self.open_btn.pack(side="right")

        # Stats
        stats = ttk.Frame(outer)
        stats.pack(fill="x", pady=(0, 10))
        self.stat_done = StatBlock(stats, "Processed", self.number_font)
        self.stat_with = StatBlock(stats, "With emails", self.number_font)
        self.stat_none = StatBlock(stats, "No emails", self.number_font)
        self.stat_bad = StatBlock(stats, "Unreachable", self.number_font)
        for i, block in enumerate((self.stat_done, self.stat_with, self.stat_none, self.stat_bad)):
            block.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            stats.columnconfigure(i, weight=1, uniform="stat")

        # Progress
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=1, value=0)
        self.progress.pack(fill="x")
        prog_row = ttk.Frame(outer)
        prog_row.pack(fill="x", pady=(4, 8))
        self.progress_var = tk.StringVar(value="Choose a file to begin.")
        ttk.Label(prog_row, textvariable=self.progress_var).pack(side="left")
        self.elapsed_var = tk.StringVar(value="")
        ttk.Label(prog_row, textvariable=self.elapsed_var, font=self.small_font).pack(side="right")

        # Results table
        table_box = ttk.Frame(outer)
        table_box.pack(fill="both", expand=True)
        columns = ("website", "result", "emails")
        self.tree = ttk.Treeview(table_box, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("website", text="Website", anchor="w")
        self.tree.heading("result", text="Result", anchor="w")
        self.tree.heading("emails", text="Emails found", anchor="w")
        self.tree.column("website", width=240, anchor="w")
        self.tree.column("result", width=140, anchor="w", stretch=False)
        self.tree.column("emails", width=300, anchor="w")
        scroll = ttk.Scrollbar(table_box, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        # Footer
        footer = ttk.Frame(outer)
        footer.pack(fill="x", pady=(8, 0))
        ttk.Label(footer, text=f"Version {__version__}", font=self.small_font).pack(side="right")
        ttk.Label(
            footer,
            text="Only scrape websites you are permitted to.",
            font=self.small_font,
        ).pack(side="left")

    # ------------------------------------------------------------ helpers
    def set_running(self, running: bool) -> None:
        self.running = running
        self.start_btn.configure(state="disabled" if running or not self.input_file else "normal")
        self.browse_btn.configure(state="disabled" if running else "normal")
        self.cancel_btn.configure(state="normal" if running else "disabled")

    def reset_results(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self.counts = {"with": 0, "none": 0, "bad": 0}
        self.refresh_stats(0)
        self.progress.configure(value=0, maximum=1)
        self.elapsed_var.set("")

    def refresh_stats(self, done: int) -> None:
        self.stat_done.set(done)
        self.stat_with.set(self.counts["with"])
        self.stat_none.set(self.counts["none"])
        self.stat_bad.set(self.counts["bad"])

    def tick(self) -> None:
        if not self.running:
            return
        secs = int(time.time() - self.started_at)
        self.elapsed_var.set(f"Elapsed {secs // 60}:{secs % 60:02d}")
        self.root.after(1000, self.tick)

    # ------------------------------------------------------------ actions
    def choose_file(self) -> None:
        if self.running:
            return
        path = filedialog.askopenfilename(
            title="Select your Excel file",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
        )
        if not path:
            return
        self.input_file = path
        self.file_var.set(path)
        self.file_entry.xview_moveto(1.0)
        self.progress_var.set(f"Ready: {Path(path).name}")
        self.start_btn.configure(state="normal")

    def start(self) -> None:
        if not self.input_file or self.running:
            return
        self.cancel.clear()
        self.reset_results()
        self.progress_var.set("Starting…")
        self.set_running(True)
        self.open_btn.configure(state="disabled")
        self.started_at = time.time()
        self.tick()
        self.worker = threading.Thread(target=self.run_worker, args=(self.input_file,), daemon=True)
        self.worker.start()

    def cancel_run(self) -> None:
        self.cancel.set()
        self.progress_var.set("Cancelling… finishing the sites in progress.")
        self.cancel_btn.configure(state="disabled")

    def open_results(self) -> None:
        if self.last_output:
            open_folder(self.last_output.output_dir)

    def on_close(self) -> None:
        if self.running:
            if not messagebox.askyesno("Quit", "A run is in progress. Quit anyway?"):
                return
            self.cancel.set()
        self.root.destroy()

    # ------------------------------------------------------------ worker thread
    def run_worker(self, path: str) -> None:
        """Runs off the UI thread; talks to the UI only through the queue."""

        def progress(done: int, total: int, site: str, msg: str, result: SiteResult | None) -> None:
            self.events.put(("progress", done, total, site, result))

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
            _, done, total, site, result = event
            self.progress.configure(maximum=total, value=done)
            pct = int(done * 100 / total) if total else 0
            self.progress_var.set(f"{done} of {total} websites  ·  {pct}%")
            if result is not None:
                if not result.reachable:
                    self.counts["bad"] += 1
                    row = (site, "✕ Could not load", "")
                elif result.emails:
                    self.counts["with"] += 1
                    row = (site, f"✓ {len(result.emails)} found", summarize_emails(result.emails))
                else:
                    self.counts["none"] += 1
                    row = (site, "– None found", "")
                iid = self.tree.insert("", "end", values=row)
                self.tree.see(iid)
            self.refresh_stats(done)

        elif kind == "done":
            out: ScrapeOutput = event[1]
            self.last_output = out
            self.set_running(False)
            self.open_btn.configure(state="normal")
            title = "Cancelled: partial results saved" if out.cancelled else "Finished"
            self.progress_var.set(title)
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
            self.progress_var.set("Something went wrong.")
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
