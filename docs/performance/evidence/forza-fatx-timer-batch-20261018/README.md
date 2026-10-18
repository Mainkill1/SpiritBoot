# Rejected FATX three-read batch candidate, 2026-10-18

## Decision

Patch 0185 is rejected and absent from the firmware lock. The bounded revision
was correct in four automated Forza runs, but it did not improve the measured
map-load interval. The two controls averaged 38.3950 seconds and the two
candidates averaged 38.7405 seconds, making the candidate 0.3455 seconds or
0.90% slower.

The experiment deferred marked asynchronous noncached FATX reads until a
third marked read, an ordinary data/flush boundary, or a 2 ms timer. The third
submission then admitted the full preceding cohort synchronously. That design
reduced no work on the submission that opened the batch and did not increase
end-to-end Forza progress.

## Exact rejected build

| Field | Value |
| --- | --- |
| Assembled source tree | `db688cb9904450b6a1c513a87f3233877b01f543` |
| Patch SHA-256 | `c76e7fc8507c9d1d15cfe93a6178fe85afdc4fd03563f9e57d707346239fed36` |
| Release64 firmware SHA-256 | `368df6a4f9683d1af8eb9f659fffd7f867a4d149346b1406827b2205d188f91a` |
| Selected-0168 control SHA-256 | `2d43d91ca5a4474a365e308b2117a642a94a2d7c7da6a3004409c267173680e6` |
| Firmware size | 524,288 bytes |

The exact tree passed 564 host tests with no failures and 26
environment-dependent skips, plus 53 native-adapter groups in plain and
ASan/UBSan builds. Those results establish the tested ownership and completion
contracts. They do not establish a performance benefit.

## Automated Forza result

The gate used release xemu processes, private HDD overlays, the same automated
route, and an A/B/A/B order:

| Cell | Run ID | Load interval |
| --- | --- | ---: |
| Control A | `20261018-153709620-b7e4102142c64b47b9d95bfcc9d08ae6` | 37.941 s |
| Candidate A | `20261018-154105577-dd181669df614404b8d5f559f9baab4f` | 38.125 s |
| Control B | `20261018-154506042-f0e330727f0a4f11a25dadea8620c6fd` | 38.849 s |
| Candidate B | `20261018-154902926-7958c5e9369f4d299df4046cf8db96da` | 39.356 s |

All four routes completed with zero failed or invalid block reads. The
30-second streamed checkpoint averaged 30.292 seconds for controls and 30.121
seconds for candidates, a 0.56% difference accompanied by different route
positions and read counts. It is below run variation and cannot qualify the
candidate. Release serial logs contained no productive-pump counters, so no
internal performance claim is inferred from them.

The follow-up PGR2 control
`20261018-155317909-b9b5676c1eeb4f24a516948f816335af` passed. A candidate
PGR2 process had already started before the stop decision and also completed,
but it is excluded because Forza had already failed the benefit gate.

[`r3-comparison.json`](r3-comparison.json) contains the raw phase and device
aggregates. [`r3-rejection.json`](r3-rejection.json) records the disposition
and exact run identities. The 504-file runner manifest remains in the private
evidence workspace with SHA-256
`2e74d311fa04dfe5964408e727179ef065bfc8450d093c7769a7b8fddb7a2570`;
game images, HDDs, saves, firmware binaries, and screenshots are not committed.

## Superseded unbounded revision

The first 0185 build (`1d26f69e...`) could retain an arbitrary number of MDLs
and FATX resource leases for 2 ms, delay an ordinary FIFO barrier, and admit as
many as 64 requests from one DPC. It was rejected before the bounded revision.
Its second candidate Forza run
`20261018-152332494-4146d1a340494b7aa6aea593c2339ddb` became unresponsive
after race start and produced no final streamed-scene capture.

The next experiment must keep the established request lifecycle and return a
complete title submission window before beginning transport admission. It
inherits no qualification from either 0185 revision.
