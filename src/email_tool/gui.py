"""Thin Tkinter wrapper around splitter.py."""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from . import __version__
from .splitter import SplitterError, split_file

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


def main() -> None:
    log_file = setup_logging()
    logger.info("EmailTool %s started", __version__)

    root = tk.Tk()
    root.withdraw()

    input_file = filedialog.askopenfilename(
        title="Select your Excel file",
        filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
    )
    if not input_file:
        logger.info("No file selected")
        return

    try:
        result = split_file(input_file)
    except SplitterError as exc:
        logger.warning("Split failed: %s", exc)
        messagebox.showerror("Error", str(exc))
        return
    except Exception as exc:
        logger.exception("Unexpected error")
        messagebox.showerror(
            "Unexpected error",
            f"{exc}\n\nPlease send this log file to support:\n{log_file}",
        )
        return

    messagebox.showinfo(
        "Success",
        "Files created successfully!\n\n"
        f"Emailed rows: {result.emailed_count}\n"
        f"Non-emailed rows: {result.non_emailed_count}\n\n"
        f"Output folder:\n{result.output_dir}",
    )


if __name__ == "__main__":
    main()
