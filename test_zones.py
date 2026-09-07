"""Self-check for the named inspection regions. Run: python3 test_zones.py"""
import sqlite3
import tempfile
from pathlib import Path

import app

REF = "a" * 64


def fresh(tmp):
    app.DB_PATH = Path(tmp) / "inspections.db"
    app.CAPTURE_DIR = Path(tmp) / "captures"


def test_saves_lists_and_removes_a_region():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_zone(REF, "brush", 10, 20, 100, 60)
        app.save_zone(REF, "stand", 200, 40, 80, 90)

        zones = app.zones_for(REF)
        assert [z["name"] for z in zones] == ["brush", "stand"], "regions should come back by name"
        assert (zones[0]["x"], zones[0]["y"], zones[0]["w"], zones[0]["h"]) == (10, 20, 100, 60)

        app.delete_zone(zones[0]["id"])
        assert [z["name"] for z in app.zones_for(REF)] == ["stand"]


def test_resaving_a_name_moves_it_rather_than_duplicating():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_zone(REF, "brush", 10, 20, 100, 60)
        app.save_zone(REF, "brush", 300, 300, 50, 50)

        zones = app.zones_for(REF)
        assert len(zones) == 1, f"expected one region, got {len(zones)}"
        assert (zones[0]["x"], zones[0]["y"]) == (300, 300)


def test_regions_belong_to_their_own_golden_sample():
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        app.save_zone(REF, "brush", 10, 20, 100, 60)
        app.save_zone("b" * 64, "wheel", 10, 20, 100, 60)
        assert [z["name"] for z in app.zones_for(REF)] == ["brush"]


def test_matches_a_defect_to_the_region_it_overlaps_most():
    zones = [
        {"name": "brush", "x": 0, "y": 0, "w": 100, "h": 100},
        {"name": "stand", "x": 90, "y": 0, "w": 100, "h": 100},
    ]
    assert app.zone_for_box(zones, (10, 10, 20, 20)) == "brush"
    assert app.zone_for_box(zones, (150, 10, 20, 20)) == "stand"
    # straddling the two, but mostly in stand
    assert app.zone_for_box(zones, (80, 10, 60, 20)) == "stand"
    # nowhere near either
    assert app.zone_for_box(zones, (400, 400, 20, 20)) is None
    # touching an edge is not overlapping it
    assert app.zone_for_box(zones, (100, 200, 10, 10)) is None


def test_adds_the_regions_column_to_an_older_database():
    """A database written before regions existed must still load and log."""
    with tempfile.TemporaryDirectory() as tmp:
        fresh(tmp)
        old = sqlite3.connect(app.DB_PATH)
        with old:
            old.execute(app.SCHEMA)
            old.execute("INSERT INTO inspection (verdict, similarity) VALUES ('PASS', 91.0)")
        old.close()

        app.log_inspection("c" * 64, b"frame", ".jpg", "REJECT", 40.0, 1, True, 80, 800, "brush")

        rows = app.recent_inspections()
        assert len(rows) == 2, "the pre-existing row should survive the migration"
        assert rows[0]["regions"] == "brush"
        assert rows[1]["regions"] == "", "the older row should default rather than fail to load"


if __name__ == "__main__":
    test_saves_lists_and_removes_a_region()
    test_resaving_a_name_moves_it_rather_than_duplicating()
    test_regions_belong_to_their_own_golden_sample()
    test_matches_a_defect_to_the_region_it_overlaps_most()
    test_adds_the_regions_column_to_an_older_database()
    print("ok")
