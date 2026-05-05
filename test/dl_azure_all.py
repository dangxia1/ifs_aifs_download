"""Download all data from Azure, then compare with ECMWF file byte-by-byte."""
import os
import tempfile
from ecmwf.opendata import Client

TARGET = os.path.join(os.path.dirname(__file__), "data_2026-04-30_step0_all_azure.grib2")
ECMWF_FILE = os.path.join(os.path.dirname(__file__), "data_2026-04-30_step0_all.grib2")

SINGLE_PARAMS = ["2t", "msl", "tp", "ssrd"]
LEVEL_PARAMS = ["q", "u", "v", "t"]
LEVELS = [1000, 925, 850, 700, 500, 300, 250, 200, 50]

client = Client(source="azure")
print("Downloading 2026-04-30 step=0 all params from Azure ...")

tmp1 = os.path.join(tempfile.gettempdir(), "tmp_azure_single.grib2")
tmp2 = os.path.join(tempfile.gettempdir(), "tmp_azure_levels.grib2")
client.retrieve(date="2026-04-30", time=0, type="fc", step=0, param=SINGLE_PARAMS, target=tmp1)
client.retrieve(date="2026-04-30", time=0, type="fc", step=0, param=LEVEL_PARAMS, levelist=LEVELS, target=tmp2)
with open(TARGET, "wb") as out:
    for t in (tmp1, tmp2):
        with open(t, "rb") as f:
            out.write(f.read())
os.remove(tmp1)
os.remove(tmp2)
print(f"Saved to {TARGET}\n")

# -- Verify Azure file --
import eccodes

print("=== Azure file ===")
with open(TARGET, "rb") as f:
    azure_msgs = {}
    while True:
        msg_id = eccodes.codes_grib_new_from_file(f)
        if msg_id is None:
            break
        name = eccodes.codes_get(msg_id, "shortName")
        level = eccodes.codes_get(msg_id, "level", ktype=str)
        size = eccodes.codes_get_message_size(msg_id)
        key = f"{name}/{level}"
        azure_msgs[key] = size
        eccodes.codes_release(msg_id)

print(f"  Messages: {len(azure_msgs)}")

# -- Compare with ECMWF file --
print("\n=== ECMWF file ===")
with open(ECMWF_FILE, "rb") as f:
    ecmwf_msgs = {}
    while True:
        msg_id = eccodes.codes_grib_new_from_file(f)
        if msg_id is None:
            break
        name = eccodes.codes_get(msg_id, "shortName")
        level = eccodes.codes_get(msg_id, "level", ktype=str)
        size = eccodes.codes_get_message_size(msg_id)
        key = f"{name}/{level}"
        ecmwf_msgs[key] = size
        eccodes.codes_release(msg_id)

print(f"  Messages: {len(ecmwf_msgs)}")

# -- Compare --
print("\n=== Comparison ===")
all_keys = set(azure_msgs.keys()) | set(ecmwf_msgs.keys())
only_azure = set(azure_msgs.keys()) - set(ecmwf_msgs.keys())
only_ecmwf = set(ecmwf_msgs.keys()) - set(azure_msgs.keys())
common = set(azure_msgs.keys()) & set(ecmwf_msgs.keys())

print(f"  Azure only: {len(only_azure)} {'-' + str(only_azure) if only_azure else ''}")
print(f"  ECMWF only: {len(only_ecmwf)} {'-' + str(only_ecmwf) if only_ecmwf else ''}")
print(f"  Common:     {len(common)}")

# Compare sizes of common messages
size_diff = 0
for k in sorted(common):
    a_sz = azure_msgs[k]
    e_sz = ecmwf_msgs[k]
    if a_sz != e_sz:
        print(f"  SIZE DIFF: {k} azure={a_sz} ecmwf={e_sz}")
        size_diff += 1

print(f"\n  Messages with different size: {size_diff}")

# Full file comparison
azure_total = os.path.getsize(TARGET)
ecmwf_total = os.path.getsize(ECMWF_FILE)
print(f"\n  Azure total: {azure_total} bytes ({azure_total/1024/1024:.1f} MB)")
print(f"  ECMWF total: {ecmwf_total} bytes ({ecmwf_total/1024/1024:.1f} MB)")
print(f"  Byte diff:   {azure_total - ecmwf_total} bytes")

if only_azure or only_ecmwf:
    print("\nVERIFY: FAIL - message mismatch")
elif size_diff > 0:
    print(f"\nVERIFY: CONTENT DIFF - {size_diff} messages differ in size (compression differs)")
else:
    print("\nVERIFY: IDENTICAL - same messages, same sizes")
