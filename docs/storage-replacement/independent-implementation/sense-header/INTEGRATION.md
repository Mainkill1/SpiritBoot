# Unlinked sense-header normalizer

Patch 0135 adds independently authored fixed/descriptor sense-header decoding and tests. It uses only copied bytes, their bounds and autosense provenance. It returns scalar key/ASC/ASCQ facts, explicit unavailable reasons, current/deferred identity and a separate truncated-tail flag. Available header facts do not validate optional descriptors or establish retry/status policy.

The fresh implementer had only the recorded public declarations and behavioral contract. Independent review found no critical or important issues and reran production tests, exact patch application and freestanding i386 compilation with no undefined helpers. Plain and ASan/UBSan tests cover all four formats, every short prefix, extent disagreements, unsupported response codes, invalid bounds, ignored flags, canaries and returned values after input poisoning/freeing.

Root mechanically integrated the exact reviewed patch SHA256 `c5c013180471c6d6adc0128476956c9fbfa4774124706a44473df6da84c1692e`. The product host test verifies the lock and executes these production functions; it passed after integration, including the existing owned primitives and both sense-test builds. The previous 148-patch tree `99a90b8f4f59f8f907fa41f1e9dd6a23f5441687` was independently recomposed before applying this patch; the 149-patch tree is `3c91ce69a469086dfdc76f5d0c3eeb6895a8baaf`.

CMake, driver registration, dispatch and native linkage are unchanged. This primitive adds no installed behavior or memory/performance claim. Native lifecycle wiring, error policy, complete replacement, P1 and final provenance review remain open.
