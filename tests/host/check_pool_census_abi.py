#!/usr/bin/env python3
"""Decode a record emitted by the compiled production census fixture.

Run after the kernel's tests/host/pool-census/check.py. Its generated unit
contains the real header and counter bodies with only lock/time/type shims.
The record header is written by NxPoolCensusInitialize, never by Python.
"""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "read_pool_census", ROOT / "tools/read_pool_census.py")
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)

PRODUCER = r'''
#undef main
int main(void) {
    PVOID short_lived = (PVOID)(uintptr_t)0x10000;
    PVOID large = (PVOID)(uintptr_t)0x20000;
    NxPoolCensusInitialize();
    NxPoolCensusPageAcquire();
    NxPoolCensusPageAttach(2, NXP_POOL_CENSUS_DOMAIN_SHARED, FALSE);
    NxPoolCensusPageAcquire();
    NxPoolCensusPageAttach(2, NXP_POOL_CENSUS_DOMAIN_SHARED, FALSE);
    NxPoolCensusPageAcquire();
    NxPoolCensusPageAttach(2, NXP_POOL_CENSUS_DOMAIN_SHARED, FALSE);
    NxPoolCensusPageBecameEmpty(2, NXP_POOL_CENSUS_DOMAIN_SHARED);
    NxPoolCensusPageDetach(2, NXP_POOL_CENSUS_DOMAIN_SHARED);
    NxPoolCensusPageRelease();
    NxPoolCensusPageBecameEmpty(2, NXP_POOL_CENSUS_DOMAIN_SHARED);
    NxPoolCensusPageDetach(2, NXP_POOL_CENSUS_DOMAIN_SHARED);
    NxPoolCensusPageAttach(4, NXP_POOL_CENSUS_DOMAIN_SHARED, TRUE);

    NxpPoolCensusData.AllocationSequence = 63;
    assert(NxPoolCensusAllocate(short_lived, 0x41424344, 64,
                               NXP_POOL_CENSUS_DOMAIN_KERNEL, FALSE));
    FakeInterruptTime += 5000000;
    NxPoolCensusFree(short_lived, 0x41424344, NxPoolCensusBinForSize(64),
                     NXP_POOL_CENSUS_DOMAIN_KERNEL, TRUE);
    NxPoolCensusAllocate((PVOID)(uintptr_t)0x10010, 0x41424344, 64,
                         NXP_POOL_CENSUS_DOMAIN_KERNEL, FALSE);
    NxPoolCensusAllocate((PVOID)(uintptr_t)0x10020, 0x41424344, 64,
                         NXP_POOL_CENSUS_DOMAIN_KERNEL, FALSE);
    NxPoolCensusAllocate(large, 0x5449544c, 2041,
                         NXP_POOL_CENSUS_DOMAIN_TITLE, TRUE);
    NxPoolCensusFreeLarge(large);
    NxPoolCensusAllocate((PVOID)(uintptr_t)0x30000, 0x4c415247, 65537,
                         NXP_POOL_CENSUS_DOMAIN_KERNEL, TRUE);
    NxpPoolCensusData.AllocationSequence = 127;
    assert(NxPoolCensusAllocate((PVOID)(uintptr_t)0x10030, 0x53414d50, 80,
                               NXP_POOL_CENSUS_DOMAIN_TITLE, FALSE));
    return fwrite(&NxpPoolCensusData, sizeof NxpPoolCensusData, 1, stdout) != 1;
}
'''


def main():
    unit, output = (Path(value).resolve() for value in sys.argv[1:])
    output.mkdir(parents=True, exist_ok=True)
    source = output / "producer.c"
    source.write_text("#define main original_fixture_main\n#include " +
                      json.dumps(str(unit)) + "\n" + PRODUCER)
    for reserve in (0, 1):
        binary = output / f"producer-{reserve}"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-O2",
                        f"-DXBOX_RESERVE_UPPER_RAM={reserve}", str(source),
                        "-o", str(binary)], check=True)
        raw = subprocess.check_output([str(binary)])
        (output / f"record-{reserve}.bin").write_bytes(raw)
        result = READER.decode_census(raw)
        assert result["incomplete"] is False, result["error_counters"]
        assert result["totals"] == {
            "allocations": 6, "frees": 2, "allocation_sequence": 128,
            "active_lifetime_samples": 1, "peak_lifetime_samples": 1}
        assert result["physical_bucket_backing"] == {
            "current": 2, "peak": 3, "class_domain_current_sum": 2,
            "current_mismatch": False}
        assert result["bins"] == [
            {"bin": 8, "request_bytes": "57-64", "allocations": 3,
             "live": 2, "peak_live": 2},
            {"bin": 10, "request_bytes": "73-80", "allocations": 1,
             "live": 1, "peak_live": 1},
            {"bin": 256, "request_bytes": "2041-2056", "allocations": 1,
             "live": 0, "peak_live": 1},
            {"bin": 4225, "request_bytes": ">65536", "allocations": 1,
             "live": 1, "peak_live": 1}]
        assert result["attached_class_pages"] == [
            {"domain": "shared", "class_index": 2,
             "block_bytes_including_header": 128,
             "fresh_refills": 3, "empty_page_reuses": 0, "detaches": 2,
             "active_pages": 1, "peak_active_pages": 3,
             "empty_pages": 0, "peak_empty_pages": 1},
            {"domain": "shared", "class_index": 4,
             "block_bytes_including_header": 512,
             "fresh_refills": 0, "empty_page_reuses": 1, "detaches": 0,
             "active_pages": 1, "peak_active_pages": 1,
             "empty_pages": 0, "peak_empty_pages": 0}]
        tag = next(row for row in result["tags"] if row["tag"] == "0x41424344")
        assert tag == {"tag": "0x41424344", "bin": 8, "domain": "kernel",
                       "allocations": 3, "frees": 1, "live": 2, "peak_live": 2,
                       "completed_lifetimes": {
                           "under_1s": 1, "1_to_30s": 0, "30s_or_more": 0}}
        (output / f"decoded-{reserve}.json").write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n")
        print(f"production census ABI: reserve={reserve}, producer-to-reader PASS")


if __name__ == "__main__":
    main()
