import numpy as np
import pandas as pd
import pytest

from email_tool.splitter import SplitterError, split_by_email, split_file


def make_df():
    return pd.DataFrame(
        {
            "Name": ["A", "B", "C", "D", "E", "F"],
            "Primary Email": ["a@x.com", None, "   ", "N/A", np.nan, " f@y.org "],
        }
    )


def test_basic_split():
    emailed, non = split_by_email(make_df())
    assert list(emailed["Name"]) == ["A", "F"]
    assert list(non["Name"]) == ["B", "C", "D", "E"]


def test_column_name_case_and_whitespace():
    df = make_df().rename(columns={"Primary Email": "  primary   EMAIL "})
    emailed, _ = split_by_email(df)
    assert len(emailed) == 2


def test_missing_column():
    with pytest.raises(SplitterError):
        split_by_email(pd.DataFrame({"Name": ["A"]}))


def test_validate_rejects_garbage():
    df = pd.DataFrame({"Primary Email": ["a@x.com", "not-an-email"]})
    emailed, non = split_by_email(df, validate=True)
    assert len(emailed) == 1 and len(non) == 1


def test_no_row_lost():
    emailed, non = split_by_email(make_df())
    assert len(emailed) + len(non) == 6


def test_split_file_roundtrip(tmp_path):
    src = tmp_path / "in.xlsx"
    make_df().to_excel(src, index=False)
    result = split_file(src)
    assert result.emailed_count == 2 and result.non_emailed_count == 4
    assert result.emailed_file.exists() and result.non_emailed_file.exists()


def test_rejects_xls(tmp_path):
    f = tmp_path / "old.xls"
    f.write_text("x")
    with pytest.raises(SplitterError):
        split_file(f)
