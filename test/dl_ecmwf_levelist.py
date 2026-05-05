"""Download 2026-04-30 step=0 pressure-level data, list variables & verify."""
import os
from ecmwf.opendata import Client

TARGET = os.path.join(os.path.dirname(__file__), "data_2026-04-30_step0_levelist.grib2")
PARAMS = ["q", "u", "v", "t"]
LEVELS = [1000, 925, 850, 700, 500, 300, 250, 200, 50]

print(f"Downloading 2026-04-30 step=0 pressure-level data (source=ecmwf) ...")
client = Client(source="ecmwf")
client.retrieve(
    date="2026-04-30",
    time=0,
    type="fc",
    step=0,
    param=PARAMS,
    levelist=LEVELS,
    target=TARGET,
)
print(f"Saved to {TARGET}\n")

import eccodes

with open(TARGET, "rb") as f:
    actual = []
    while True:
        msg_id = eccodes.codes_grib_new_from_file(f)
        if msg_id is None:
            break
        name = eccodes.codes_get(msg_id, "shortName")
        level = eccodes.codes_get(msg_id, "level")
        size = eccodes.codes_get_message_size(msg_id)
        actual.append(f"{name}/{level}")
        print(f"  [{len(actual):2d}] {name} @ {level}hPa: {size} bytes")
        eccodes.codes_release(msg_id)

expected = [f"{p}/{l}" for p in PARAMS for l in LEVELS]
missing = set(expected) - set(actual)
extra = set(actual) - set(expected)
print(f"\nExpected: {len(expected)} messages ({len(PARAMS)} params x {len(LEVELS)} levels)")
print(f"Found:    {len(actual)}")
print(f"Missing:  {missing or 'None'}")
print(f"Extra:    {extra or 'None'}")
print("VERIFY: OK" if not missing else f"VERIFY: FAIL - missing {missing}")