"""Pure splitting logic. No GUI code lives here, so it is easy to test."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_COLUMN = "Primary Email"

# Values that count as "no email" even though the cell is not truly blank.
EMPTY_MARKERS = {"", "nan", "none", "null", "n/a", "na", "-", "--"}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")


class SplitterError(Exception):
    """Raised for problems the user can fix (bad file, missing column)."""


@dataclass(frozen=True)
class SplitResult:
    emailed_count: int
    non_emailed_count: int
    emailed_file: Path
    non_emailed_file: Path
    output_dir: Path


def _norm(name: object) -> str:
    return re.sub(r"\s+", " ", str(name)).strip().lower()


def find_email_column(df: pd.DataFrame, column: str = DEFAULT_COLUMN) -> str:
    """Return the real column name matching `column`, ignoring case/whitespace."""
    target = _norm(column)
    for col in df.columns:
        if _norm(col) == target:
            return col
    raise SplitterError(
        f'Could not find a column named "{column}".\n\n'
        f"Columns found: {', '.join(map(str, df.columns))}"
    )


def _clean(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() in EMPTY_MARKERS else text


def split_by_email(
    df: pd.DataFrame,
    column: str = DEFAULT_COLUMN,
    validate: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split `df` into (emailed, non_emailed).

    If `validate` is True, a value must also look like an email address
    to count as emailed.
    """
    col = find_email_column(df, column)
    cleaned = df[col].map(_clean)
    has_email = cleaned != ""
    if validate:
        has_email &= cleaned.map(lambda v: bool(_EMAIL_RE.match(v)))
    return df[has_email].copy(), df[~has_email].copy()


def split_file(
    input_file: str | Path,
    output_dir: str | Path | None = None,
    column: str = DEFAULT_COLUMN,
    validate: bool = False,
) -> SplitResult:
    """Read an Excel file, split it, and write two timestamped output files."""
    input_path = Path(input_file)
    if not input_path.is_file():
        raise SplitterError(f"File not found: {input_path}")
    if input_path.suffix.lower() != ".xlsx":
        raise SplitterError("Only .xlsx files are supported. Please re-save as .xlsx.")

    try:
        df = pd.read_excel(input_path)
    except Exception as exc:  # corrupt file, password protected, etc.
        raise SplitterError(f"Could not read the Excel file: {exc}") from exc

    logger.info("Read %d rows from %s", len(df), input_path)
    emailed, non_emailed = split_by_email(df, column, validate)

    out_dir = Path(output_dir) if output_dir else input_path.parent / "Output"
    out_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    emailed_file = out_dir / f"Emailed_Sheet_{stamp}.xlsx"
    non_emailed_file = out_dir / f"Non_Emailed_Sheet_{stamp}.xlsx"

    try:
        emailed.to_excel(emailed_file, index=False)
        non_emailed.to_excel(non_emailed_file, index=False)
    except PermissionError as exc:
        raise SplitterError(
            f"Could not write to {out_dir}. Check folder permissions."
        ) from exc

    logger.info("Wrote %s and %s", emailed_file, non_emailed_file)
    return SplitResult(
        len(emailed), len(non_emailed), emailed_file, non_emailed_file, out_dir
    )
