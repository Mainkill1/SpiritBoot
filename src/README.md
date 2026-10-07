# Source Layout

Source code will be split by responsibility:

- `boot/` — reset entry and earliest execution;
- `platform/` — original Xbox hardware/HAL code;
- `kernel/` — Xbox-compatible kernel/runtime behavior;
- `loader/` — XBE parsing, mapping, binding and launch;
- `trace/` — boot/kernel trace infrastructure.

Do not add implementation until its execution contract is understood well enough to place it in the correct layer.

Initial code should favor:
- freestanding C plus minimal assembly where necessary;
- fixed-width types and explicit physical/virtual address types;
- centralized register definitions;
- no dynamic allocation in earliest boot;
- deterministic failure paths;
- trace points around hardware state transitions;
- host-testable pure parsing/table logic where possible.
