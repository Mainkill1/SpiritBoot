# Public interrupt ABI probe

This independently authored XBE checks the 112-byte Xbox interrupt object, public initialization fields, Connected transitions, bounds guards, and actual NV2A IRQ3 callback identity/context. It does not inspect reference implementation instructions. A real vblank triggers the handler, which queues an owned DPC to signal the event at DISPATCH_LEVEL. A two-second wait bounds delivery. The probe masks the source, disconnects, removes its queued DPC, restores the saved PMC/PCRTC enables, prints its 17 numbered TAP checks, and requests power-off.

Build with the pinned nxdk container from `sources/firmware-lock.json` and run on a fresh 64 MiB xemu session with COM1 capture. The original test payload is frozen in the accompanying provenance evidence. See `docs/provenance/TITLE_INTERRUPT_PUBLIC_ABI.md` for controls and limits.

This checks cold-boot interrupt behavior. Hardware testing, live connected reinitialization, and title-generated public dispatch code are outside this probe.

The historical V2 payload signaled the event directly from DIRQL. It passed the released/reference/candidate release comparison, but checked-firmware CI caught the event routine's IRQL assertion after check 11. The maintained V3 probe defers that signal and requires actual DPC delivery at DISPATCH_LEVEL within check 12. Historical payloads and failed CI receipts remain evidence; they are not substitutes for complete V3 TAP on checked profiles.
