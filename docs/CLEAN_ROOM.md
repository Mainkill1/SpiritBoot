# Clean-room and provenance policy

SpiritBoot is intended to be redistributable. The project distinguishes public open-source implementation work, black-box observations, and proprietary material.

## Allowed inputs

- Public open-source projects used according to their licenses.
- Public hardware documentation and public Xbox-development research.
- Purpose-built tests against documented or independently observed interfaces.
- Measurements from legally obtained hardware and software.
- Black-box traces of behavior, return values, timing, state transitions, register activity, or API call sequences.
- Facts such as ABI names, ordinals, structure sizes, constants, and independently established hardware behavior.

## Not accepted

Do not add or derive implementation code from:
- leaked Microsoft Xbox source code
- proprietary Microsoft BIOS/kernel source
- unauthorized SDK source or headers
- copyrighted ROM, flash, dashboard, EEPROM, game, or key material
- copied proprietary disassembly used as implementation source

Do not commit binary dumps or secrets.

## Open-source reuse

Before moving code into SpiritBoot:
1. Record repository, path, revision, copyright header, and license.
2. Verify destination-license compatibility.
3. Preserve required notices.
4. Prefer an upstream fork for large bodies of imported code instead of vendoring them here.

Roswell's combined kernel is GPL-2.0, so SpiritBoot uses GPL-2.0 as the umbrella license. Per-file upstream headers remain authoritative.

## Proprietary-reference workflow

```text
question
  -> purpose-built test
  -> run on hardware/reference environment
  -> record observable result
  -> write behavioral specification
  -> implement from specification
  -> validate on hardware + emulator
```

Research notes should record the question, test revision, environment, inputs, outputs, invariants, uncertainty, date, and provenance. They should not contain copied proprietary implementation text.

## Differential testing

Comparing SpiritBoot, Cxbx-Reloaded, Roswell, and an original kernel is encouraged, but agreement between emulators is not proof of Xbox behavior.

## Contributor disclosure

A contributor who has consulted leaked proprietary Xbox source for the same component should disclose that conflict before contributing implementation code to that component. Independently collected test results and high-level behavioral observations can still be useful when provenance is clear.

## External test-suite licensing

The current `Cxbx-Reloaded/xbox_kernel_test_suite` repository carries a GPL-3.0 `LICENSE`. SpiritBoot's correlation tooling therefore treats it as an external test/reference project: it may inspect paths, classify coverage, execute the suite, and import behavioral results/metadata. Do not directly copy its GPL-3.0 test implementations into GPL-2.0-only SpiritBoot source without first resolving license compatibility. Behavioral observations and independently written conformance tests should retain clear provenance.
