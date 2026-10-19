# Caller budget beginning before the initial alertable poll

**All three generated-fixture runs pass; this is not an overall Forza fix.**
This separate experiment moves the start of a synthetic caller budget before
its first zero-time alertable wait. It runs baseline SpiritBoot, candidate0168
and Complex on the same frozen release fixture, in that order. There is one
observation per variant; changes below are point estimates, not a repeated or
randomized game acceptance test.

The [fixture contract](../../../../../tests/xbe/forza-poll-budget/README.md)
keeps callbacks minimal: they record status/count and mark completion, never
issue reads. Caller code checks the deadline before every issue, including the
first. A poll that consumes the budget can produce a zero-issue frame. Every
read uses exported `NtUserIoApcDispatcher`; native read entry/return and both
initial/per-read polls have separate timing counters.

Sixteen persistent buffers provide up to eight prepared fresh reads while up
to eight earlier requests await the initial poll. At most eight requests are
outstanding and at most eight are issued per pump. A callback followed by a
later completed alertable call is required before a buffer can be retired;
full generated-byte and canary validation and preparation happen outside the
clock. Initial-poll completion cannot permit same-pump storage reuse. Each pump
is followed by a checked 33 ms non-alertable blocking interval; there is no
trailing alertable poll to drain the next initial wait's callbacks.

## Every case

Rates include outside-pump preparation and full byte checking, including final
retirement. All cases last at least ten seconds using their own reported
counter frequency. All submitted reads are verified and receive exactly one
successful callback with the requested byte count. The private generated file,
MM query canaries, QD cap, frame continuity and sampled deadline checks all pass.
Budgets 250/450/1000 µs and uncapped are experimental parameters, not established
title constants.

| Free pages | Budget µs | Baseline reads/s | 0168 reads/s | Complex reads/s | 0168 vs baseline | 0168 vs Complex |
| ---: | --- | ---: | ---: | ---: | ---: | ---: |
| 783 | 250 | 67.460 | 76.549 | 197.612 | +13.47% | -61.26% |
| 783 | 450 | 135.354 | 145.623 | 200.800 | +7.59% | -27.48% |
| 783 | 1000 | 198.289 | 199.463 | 199.584 | +0.59% | -0.06% |
| 783 | uncapped | 201.837 | 199.534 | 200.944 | -1.14% | -0.70% |
| 900 | 250 | 67.001 | 80.231 | 200.961 | +19.75% | -60.08% |
| 900 | 450 | 135.522 | 150.030 | 201.356 | +10.71% | -25.49% |
| 900 | 1000 | 200.416 | 198.224 | 201.376 | -1.09% | -1.56% |
| 900 | uncapped | 201.057 | 199.369 | 201.450 | -0.84% | -1.03% |

At 450 µs, candidate0168 improves over baseline by 7.6% / 10.7% but remains
27.5% / 25.5% below Complex at 783 / 900 pages. The longer-budget cases are
mixed, including small regressions; this is not a uniform speedup claim.

## Components at the synthetic 450 µs setting

Initial-poll time is per pump; native read and later poll times are per read.
These are differently weighted quantities, not additive columns. Read and poll
time are components inside the pump interval. The remaining pump time includes
caller bookkeeping and counter reads. No storage-completion timestamp or actual
rendering cost is measured.

| Free pages | Firmware | Initial poll µs/pump | Native read µs/read | Later poll µs/read | Issues/pump | Initial callbacks | Zero-issue pumps |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 783 | baseline | 12.541 | 86.212 | 3.657 | 5.222 | 675 | 0 |
| 783 | candidate | 12.617 | 77.670 | 4.100 | 5.682 | 691 | 0 |
| 783 | complex | 15.448 | 7.845 | 0.830 | 8.000 | 1990 | 0 |
| 900 | baseline | 13.260 | 87.830 | 2.829 | 5.211 | 632 | 0 |
| 900 | candidate | 12.551 | 75.633 | 3.625 | 5.864 | 724 | 0 |
| 900 | complex | 14.345 | 7.461 | 0.987 | 8.000 | 1995 | 0 |

In these runs the initial poll is roughly 12–15 µs. Complex delivers more
callbacks in that poll, so equal per-pump durations do not imply equal per-
callback cost. The much larger weighted native-read duration on SpiritBoot
persists after charging the initial poll. This identifies a measured component
of the synthetic budget gap, not the real title's complete bottleneck.

The complete aggregate counters, per-size means/maxima and representative
OP/FRAME samples are retained, including all zero-issue counts and initial-poll
maxima. Every initial poll is charged even when no request is issued. The
analyzer also requires continuity of outstanding requests across each sampled
non-alertable interval and rejects reuse of a slot completed inside that pump.

This is a new experimental contract. Besides starting the clock earlier, it
uses sixteen buffers, removes the first-read deadline exemption and tests
450 µs in place of the old 500 µs setting. Direct differences from the original
burst fixture cannot therefore be attributed solely to initial polling.
Comparisons within this table use the same new fixture. The blocking cadence,
private generated file, page target and caller loop do not reproduce title
rendering, allocator choices or game payloads.

## Identity and reproduction

The frozen release XISO is
`8d94b0c6fa4699de29959e0bdc5ddd63b6b518ea7c65fcf22cf4da9e1f9b4630`;
XBE `510c0706f2ad01ee76aede12e1fd5bc1999c346d0c7c35b98dafd9ddeae80e12`.
All three use published xemu executable
`5488be40bf3c1c444b507d084c8d964f8f7d73c2a912970495cf85a4f7239564`,
64 MiB, COM1 capture and the same launcher/arguments. Exact BIOS/configuration
hashes and run IDs are in the [manifest](capture-manifest.json). Baseline BIOS
is `add882b6f50e9c9ae49705bb8374be5646e44ed1b72f0e2eb4b77bdedeeaf296`;
0168 is `2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6`;
Complex is `1de4c87effe40d44f95581d204f9fa0600fbd5fe2171692316dcf97af0f4113f`.
The release identity file records the reviewed freeze-time source/analyzer
hashes and build flags; its “native runs pending” text describes freeze time.
The fixture powers off after ten TAP checks and `FORZA-PUMP-END failures=0`.

Runner receipts preserve execution completed, generic correctness/evidence not
evaluated and comparison ineligible. The independent frozen analyzer validates
the fixture oracle; no runner-framework acceptance is claimed. No host reboot,
BIOS rebuild or fixture change occurred between these three jobs. The existing
private BIOS-specific disks/EEPROM states were reused, not reset to independently
hashed matched initial states; generated-file reseeding is not a cold-cache
condition. Native trial order was baseline, 0168, Complex.

```sh
python3 docs/performance/evidence/forza-complex-cadence-20261017/initial-poll/reproduce.py
python3 -m unittest discover -s docs/performance/evidence/forza-complex-cadence-20261017/initial-poll -p test_analyze.py
```

Reproduction checks input/launch/run identity, parses all three owned logs,
requires exact equality with the archived summaries and emits
[comparison.json](comparison.json). All 24 analyzer tests pass. Root
`SHA256SUMS` binds this archive. Only owned serial, numeric summaries, sanitized
requests/receipts and reproduction code are included; no environment mappings,
private endpoints or BIOS/emulator/EEPROM/HDD/game/RAM/snapshot bytes are present.
The missing-world problem remains unqualified by this generated workload.
