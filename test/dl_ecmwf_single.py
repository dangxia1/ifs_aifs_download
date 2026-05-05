"""Download 2026-04-30 step=0 single-level data, list variables & verify."""
import os
from ecmwf.opendata import Client

TARGET = os.path.join(os.path.dirname(__file__), "data_2026-04-30_step0.grib2")
PARAMS = ["2t", "msl", "tp", "ssrd"]

# 1. Download
print("Downloading 2026-04-30 step=0 single-level data ...")
client = Client(source="ecmwf")
client.retrieve(
    date="2026-04-30",
    time=0,
    type="fc",
    step=0,
    param=PARAMS,
    target=TARGET,
)
print(f"Saved to {TARGET}\n")

# 2. List variables & verify
import eccodes

with open(TARGET, "rb") as f:
    actual = []
    while True:
        msg_id = eccodes.codes_grib_new_from_file(f)
        if msg_id is None:
            break
        name = eccodes.codes_get(msg_id, "shortName")
        size = eccodes.codes_get_message_size(msg_id)
        actual.append(name)
        print(f"  [{len(actual)}] {name}: {size} bytes")
        eccodes.codes_release(msg_id)

# 3. Verify completeness
missing = set(PARAMS) - set(actual)
extra = set(actual) - set(PARAMS)
print(f"\nExpected: {PARAMS}")
print(f"Found:    {actual}")
print(f"Missing:  {missing or 'None'}")
print(f"Extra:    {extra or 'None'}")
print("VERIFY: OK" if not missing else f"VERIFY: FAIL - missing {missing}")
