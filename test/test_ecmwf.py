"""Tests for ECMWF source downloads (IFS model, step=0)."""
import os
import pytest
from ecmwf.opendata import Client
from conftest import SINGLE_PARAMS, LEVEL_PARAMS, LEVELS, ALL_PARAMS, verify_grib

pytestmark = pytest.mark.integration


def test_download_single_level(recent_date, tmp_path):
    target = str(tmp_path / "single.grib2")
    Client(source="ecmwf").retrieve(
        date=recent_date, time=0, type="fc", step=0,
        param=SINGLE_PARAMS, target=target,
    )
    count, params = verify_grib(target)
    assert count == len(SINGLE_PARAMS), f"expected {len(SINGLE_PARAMS)} msgs, got {count}"
    assert params == set(SINGLE_PARAMS), f"mismatch: {params ^ set(SINGLE_PARAMS)}"


def test_download_pressure_levels(recent_date, tmp_path):
    target = str(tmp_path / "levels.grib2")
    Client(source="ecmwf").retrieve(
        date=recent_date, time=0, type="fc", step=0,
        param=LEVEL_PARAMS, levelist=LEVELS, target=target,
    )
    count, params = verify_grib(target)
    assert count == len(LEVEL_PARAMS) * len(LEVELS), (
        f"expected {len(LEVEL_PARAMS) * len(LEVELS)} msgs, got {count}"
    )
    assert params == set(LEVEL_PARAMS), f"mismatch: {params ^ set(LEVEL_PARAMS)}"


def test_download_combined(recent_date, tmp_path):
    target = str(tmp_path / "combined.grib2")
    s = str(tmp_path / "s.grib2")
    l = str(tmp_path / "l.grib2")

    c = Client(source="ecmwf")
    c.retrieve(date=recent_date, time=0, type="fc", step=0, param=SINGLE_PARAMS, target=s)
    c.retrieve(date=recent_date, time=0, type="fc", step=0, param=LEVEL_PARAMS, levelist=LEVELS, target=l)
    with open(target, "wb") as out:
        for t in (s, l):
            with open(t, "rb") as f:
                out.write(f.read())
    os.remove(s)
    os.remove(l)

    count, params = verify_grib(target)
    expected = len(SINGLE_PARAMS) + len(LEVEL_PARAMS) * len(LEVELS)
    assert count == expected, f"expected {expected} msgs, got {count}"
    assert params == set(ALL_PARAMS), f"mismatch: {params ^ set(ALL_PARAMS)}"
