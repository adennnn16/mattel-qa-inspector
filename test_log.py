"""Self-check for the inspection log. Run: python3 test_log.py"""
import tempfile
from pathlib import Path

import app


def test_writes_a_row_and_keeps_the_frame():
    with tempfile.TemporaryDirectory() as tmp:
        app.DB_PATH = Path(tmp) / "inspections.db"
        app.CAPTURE_DIR = Path(tmp) / "captures"

        frame = b"\xff\xd8\xff not really a jpeg"
        app.log_inspection("a" * 64, frame, ".jpg", "REJECT", 84.2, 3, True, 80, 800)

        rows = app.recent_inspections()
        assert len(rows) == 1, f"expected one row, got {len(rows)}"
        row = rows[0]
        assert row["verdict"] == "REJECT"
        assert row["defects"] == 3
        assert row["aligned"] == 1
        assert row["similarity"] == 84.2
        assert row["inspected_at"], "inspected_at should default to the current time"

        kept = Path(row["capture"])
        assert kept.read_bytes() == frame, "the captured frame was not kept intact"
        assert kept.name == "a" * 16 + ".jpg"


def test_orders_newest_first_and_survives_a_second_capture():
    with tempfile.TemporaryDirectory() as tmp:
        app.DB_PATH = Path(tmp) / "inspections.db"
        app.CAPTURE_DIR = Path(tmp) / "captures"

        app.log_inspection("b" * 64, b"one", ".jpg", "PASS", 99.0, 0, True, 80, 800)
        app.log_inspection("c" * 64, b"two", ".jpg", "REJECT", 41.5, 2, False, 80, 800)

        rows = app.recent_inspections()
        assert [r["verdict"] for r in rows] == ["REJECT", "PASS"], "newest row should come first"
        assert rows[0]["aligned"] == 0, "an unaligned capture should be recorded as such"


def test_reports_nothing_before_the_first_inspection():
    with tempfile.TemporaryDirectory() as tmp:
        app.DB_PATH = Path(tmp) / "missing.db"
        assert app.recent_inspections() == []


if __name__ == "__main__":
    test_writes_a_row_and_keeps_the_frame()
    test_orders_newest_first_and_survives_a_second_capture()
    test_reports_nothing_before_the_first_inspection()
    print("ok")
