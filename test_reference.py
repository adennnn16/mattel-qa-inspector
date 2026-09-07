"""Self-check for per-SKU golden samples. Run: python3 test_reference.py"""
import sqlite3
import tempfile
from pathlib import Path

import app


def fresh(tmp):
    app.DB_PATH = Path(tmp) / "inspections.db"
    app.CAPTURE_DIR = Path(tmp) / "captures"
    app.REFERENCE_DIR = Path(tmp) / "references"


def test_stores_and_reads_back_a_golden_sample():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        assert app.references_for("GTX99") == [], "an unknown SKU holds no samples"

        app.save_reference("GTX99", b"golden bytes", ".jpg")
        held = app.references_for("GTX99")
        assert len(held) == 1
        assert Path(held[0]["path"]).read_bytes() == b"golden bytes"
        assert app.known_skus() == ["GTX99"]


def test_holds_several_samples_per_sku_in_the_order_added():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_reference("GTX99", b"first", ".jpg")
        app.save_reference("GTX99", b"second", ".jpg")
        app.save_reference("GTX99", b"third", ".jpg")

        held = app.references_for("GTX99")
        assert len(held) == 3, f"expected three samples, got {len(held)}"
        assert Path(held[0]["path"]).read_bytes() == b"first", "the anchor should come first"
        assert app.known_skus() == ["GTX99"], "several samples are still one SKU"


def test_the_same_bytes_twice_is_one_sample():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_reference("GTX99", b"same", ".jpg")
        app.save_reference("GTX99", b"same", ".jpg")
        assert len(app.references_for("GTX99")) == 1


def test_removing_a_sample_leaves_the_others_and_the_regions():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_reference("GTX99", b"first", ".jpg")
        app.save_reference("GTX99", b"second", ".jpg")
        app.save_zone("GTX99", "brush", 10, 20, 100, 60)

        app.delete_reference(app.references_for("GTX99")[1]["id"])

        held = app.references_for("GTX99")
        assert len(held) == 1 and Path(held[0]["path"]).read_bytes() == b"first"
        assert [z["name"] for z in app.zones_for("GTX99")] == ["brush"]


def test_each_sku_keeps_its_own_samples_and_regions():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_reference("GTX99", b"beach", ".jpg")
        app.save_reference("HJK12", b"camper", ".jpg")
        app.save_zone("GTX99", "brush", 0, 0, 10, 10)
        app.save_zone("HJK12", "wheel", 0, 0, 10, 10)

        assert app.known_skus() == ["GTX99", "HJK12"], "SKUs should come back sorted"
        assert [z["name"] for z in app.zones_for("HJK12")] == ["wheel"]
        assert len(app.references_for("GTX99")) == 1


def test_carries_a_single_sample_table_over_to_the_wider_one():
    """A database written when a SKU could hold only one sample must keep that sample."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        old = sqlite3.connect(app.DB_PATH)
        with old:
            old.execute("""
                CREATE TABLE reference (
                    sku       TEXT NOT NULL PRIMARY KEY,
                    digest    TEXT NOT NULL DEFAULT '',
                    path      TEXT NOT NULL DEFAULT '',
                    added_at  TEXT NOT NULL DEFAULT (datetime('now'))
                )
            """)
            old.execute("INSERT INTO reference (sku, digest, path)"
                        " VALUES ('GTX99', 'deadbeef', 'references/GTX99.jpg')")
        old.close()

        held = app.references_for("GTX99")
        assert len(held) == 1, "the existing sample should survive the rebuild"
        assert held[0]["digest"] == "deadbeef"
        assert held[0]["path"] == "references/GTX99.jpg"
        assert "id" in held[0], "the rebuilt table should be keyed on an id"

        app.save_reference("GTX99", b"a second one", ".jpg")
        assert len(app.references_for("GTX99")) == 2, "and the SKU can now hold more"


def test_logs_the_sku_and_migrates_a_database_without_the_column():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        old = sqlite3.connect(app.DB_PATH)
        with old:
            old.execute(app.SCHEMA)
            old.execute("INSERT INTO inspection (verdict, similarity) VALUES ('PASS', 91.0)")
        old.close()

        app.log_inspection("d" * 64, b"frame", ".jpg", "REJECT", 40.0, 1, True, 80, 800,
                           "brush", "GTX99")

        rows = app.recent_inspections()
        assert len(rows) == 2, "the pre-existing row should survive the migration"
        assert rows[0]["sku"] == "GTX99"
        assert rows[1]["sku"] == "", "the older row should default rather than fail to load"


if __name__ == "__main__":
    test_stores_and_reads_back_a_golden_sample()
    test_holds_several_samples_per_sku_in_the_order_added()
    test_the_same_bytes_twice_is_one_sample()
    test_removing_a_sample_leaves_the_others_and_the_regions()
    test_each_sku_keeps_its_own_samples_and_regions()
    test_carries_a_single_sample_table_over_to_the_wider_one()
    test_logs_the_sku_and_migrates_a_database_without_the_column()
    print("ok")
