This owned guest checks boot, retained threads, IRPs, file reads, an 18-size
allocation ladder, full reported capacities, free/retype churn and warm pool
allocation/free batches. The normal guest uses public APIs and prints memory
ownership only. Use the identical ISO for baseline and candidate comparisons.

Build with the existing nxdk image:

```sh
docker run --rm -v "$PWD:/product" -w /product/tests/xbe/pool-audit \
  ghcr.io/xboxdev/nxdk:latest make -j4
```

For diagnostic census output, first build firmware with `--pool-audit` and run
`scripts/pool-audit-addresses.py BUILD_JSON tests/xbe/pool-audit/addresses.h`
inside the toolchain container. Then use `make clean` and build with
`POOL_DIAGNOSTIC=1 ROSWELL_SOURCE=EXACT_BUILD_SOURCE_DIRECTORY`. The generated
addresses and the included private header must come from that same build;
schema 4 records include nine classes and eighteen class/domain indices.
Diagnostics add resident state and are unsuitable for timing comparisons.

The serial reader validates the record's version, size, update sequence and
integrity counters before emitting values. The initial schema 3 fixture and
its exact source are retained separately in the provenance evidence directory.
