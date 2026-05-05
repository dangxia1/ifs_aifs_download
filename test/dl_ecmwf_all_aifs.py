"""Test AIFS download: single-level + pressure-level data."""
import os
import tempfile
from ecmwf.opendata import Client

TARGET = os.path.join(os.path.dirname(__file__), "data_2026-05-02_step0_all_aifs.grib2")
SINGLE_PARAMS = ["2t", "msl", "tp", "ssrd"]
LEVEL_PARAMS = ["q", "u", "v", "t"]
LEVELS = [1000, 925, 850, 700, 500, 300, 250, 200, 50]

client = Client(source="ecmwf", model="aifs-single")

print("Trying single retrieve() with all params (AIFS) ...")
client.retrieve(
    date="2026-05-02", time=0, type="fc", step=0,
    param=SINGLE_PARAMS + LEVEL_PARAMS, levelist=LEVELS, target=TARGET,
)

import eccodes
with open(TARGET, "rb") as f:
    got = set()
    while True:
        msg_id = eccodes.codes_grib_new_from_file(f)
        if msg_id is None:
            break
        got.add(eccodes.codes_get(msg_id, "shortName"))
        eccodes.codes_release(msg_id)

single_missing = set(SINGLE_PARAMS) - got
if single_missing:
    print(f"  Single-level vars missing: {single_missing}")
    print("  Falling back to two separate calls + merge ...")
    tmp1 = os.path.join(tempfile.gettempdir(), "tmp_aifs_single.grib2")
    tmp2 = os.path.join(tempfile.gettempdir(), "tmp_aifs_levels.grib2")
    client.retrieve(date="2026-05-02", time=0, type="fc", step=0, param=SINGLE_PARAMS, target=tmp1)
    client.retrieve(date="2026-05-02", time=0, type="fc", step=0, param=LEVEL_PARAMS, levelist=LEVELS, target=tmp2)
    with open(TARGET, "wb") as out:
        for t in (tmp1, tmp2):
            with open(t, "rb") as f:
                out.write(f.read())
    os.remove(tmp1)
    os.remove(tmp2)
    print("  Merged OK")
else:
    print("  All params included in single call")

print(f"\nSaved to {TARGET}\n")

all_expected = SINGLE_PARAMS + LEVEL_PARAMS
with open(TARGET, "rb") as f:
    actual = []
    while True:
        msg_id = eccodes.codes_grib_new_from_file(f)
        if msg_id is None:
            break
        name = eccodes.codes_get(msg_id, "shortName")
        level = eccodes.codes_get(msg_id, "level", ktype=str)
        size = eccodes.codes_get_message_size(msg_id)
        actual.append(name)
        print(f"  [{len(actual):2d}] {name} @ {level}: {size} bytes")
        eccodes.codes_release(msg_id)

missing = set(all_expected) - set(actual)
extra = set(actual) - set(all_expected)
print(f"\nExpected: {len(SINGLE_PARAMS)} single + {len(LEVEL_PARAMS)}x{len(LEVELS)} levels = {len(SINGLE_PARAMS) + len(LEVEL_PARAMS) * len(LEVELS)} messages")
print(f"Found:    {len(actual)}")
print(f"Missing:  {missing or 'None'}")
print(f"Extra:    {extra or 'None'}")
print("VERIFY: OK" if not missing else f"VERIFY: FAIL - missing {missing}")
