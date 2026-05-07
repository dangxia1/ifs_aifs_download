import pytest
from datetime import datetime, timedelta, timezone

SINGLE_PARAMS = ["2t", "msl", "tp", "ssrd"]
LEVEL_PARAMS = ["q", "u", "v", "t"]
LEVELS = [1000, 925, 850, 700, 500, 300, 250, 200, 50]
ALL_PARAMS = SINGLE_PARAMS + LEVEL_PARAMS


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: test that downloads real data from ECMWF/Azure (requires network)",
    )


@pytest.fixture
def recent_date():
    """A date within ecmwf's ~4 day retention window."""
    return (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")


@pytest.fixture
def azure_date():
    """A stable historical date guaranteed to exist on Azure."""
    return "2025-06-15"


def verify_grib(path):
    """Return (count, param_set) from a GRIB file."""
    import eccodes

    with open(path, "rb") as f:
        params = []
        while True:
            msg_id = eccodes.codes_grib_new_from_file(f)
            if msg_id is None:
                break
            params.append(eccodes.codes_get(msg_id, "shortName"))
            eccodes.codes_release(msg_id)
    return len(params), set(params)
