# Independent static Xbox interrupt entry review

Reviewed 2026-10-13. No correctness blocker found in the proposed change. This is a source and owned-binary review, with independently rerun actual-function host tests. Native performance is recorded separately.

Exact candidate: source tree `6108cf4b697353bada1f9fa9df923db9d84054a8`, `irq-static-release64/work-uge0up8u/source`; ROM SHA256 `913293b4a86eac808313555867aa3099aba40903cc17a63c3c424b89a5c5dd77`. Parent patch: `irq-static-product/patches/roswell/10003-static-xbox-interrupt-entry.patch`. Exact comparison baseline is async4 tree `520914d4e614d185a00ca70d29b74b4d6fe58d76`, ROM `368495b92eb15be75b39adfb692285d8683066ed1a7ef5fd4e4792b9b26d1803`. This is not async3 or async5.

## Trap frame and routing

`ntoskrnl/ke/i386/trap.s:164` adds sixteen immutable entries. Independently inspected the compiled owned `xboxkrnl.unstripped.exe`: entries occupy `840023b0` through `840024a0`, exactly 16 bytes apart. Each pushes its own immediate index 0–15 and jumps to common `840024b0`. They do not alter incoming registers or EFLAGS before the normal save sequence.

The existing fake-error-code prologue reserves 0x68 bytes. The new entry pushes four bytes and its `KiEnterTrap 0` reserves 0x64, giving the same final frame address and existing offsets for saved EIP/CS/EFLAGS and any privilege-transition stack. The common macro saves all integer and segment registers before reusing EDX for the index. It loads DS/ES/FS normally and leaves the existing v86 segment handling intact. It consumes the index at frame+0x64, resets that slot to zero, loads the object from the fixed table, and jumps to the unchanged fastcall `KiInterruptTemplateHandler`. That handler's `KiEnterInterruptTrap` and final trap return are unchanged. No new allocator, wait, device operation, or C call was inserted into entry.

## Publication and lifetime

`ntoskrnl/ke/i386/irqobj.c:36` recognizes an object only when the actual IDT handler is the expected static entry for that vector. A foreign route becomes UnknownConnect without interpreting arbitrary executable bytes as a KINTERRUPT. The existing full-width 0x30–0x3f vector validation remains ahead of public connect/disconnect operations.

`irqobj.c:117` captures incoming IF, disables hardware interrupts, sets DispatchAddress, publishes the table pointer, writes both IDT address halves, and restores IF only when it was originally set. Independent compiled inspection confirms that order. Thus a hardware IRQ cannot observe an IDT route and object-table entry from different publications on this uniprocessor. NMI does not use these PIC entries. No SMP claim is made.

Existing connect/chain/disconnect operations are retained: first connect publishes an initialized self-linked object before enabling the line; sharing changes the head's dispatch mode; removing a head publishes the surviving object before unlinking; a two-object chain becomes normal; final disconnect disables the line and publishes the unexpected handler with a null table slot. A failed HAL enable rolls back through the existing disconnect path. Objects remain caller-owned and valid until disconnect returns. The patch introduces no asynchronous retention or new free path. Existing synchronization for chain list mutation is inherited; the UP dispatcher lock raises only to DISPATCH_LEVEL, so it must not be described as masking every hardware ISR. The new publication critical section itself explicitly masks IF.

The desktop path remains under the existing non-Xbox branch. KINTERRUPT layout, public Xbox shadow-object layout, ISR callback dispatch, DPC scheduling, PIC acknowledgement, spurious handling, and IRQL transitions are unchanged.

## Footprint and tests

Owned PE section comparison: .text `0x53c5c`→`0x53e60` (+516 bytes), .bss `0xacd0`→`0xad10` (+64 bytes). All loadable section virtual addresses and rounded page counts stay the same. The pointer table is at `84064820`. No extra pool allocation or permanently pinned page is introduced, and existing KINTERRUPT pool allocation sizes remain unchanged.

Independently reran the root actual-function host harness against this exact built source with ASan/UBSan: 2,236 checks, zero failures. It covers all 16 vectors with IF initially set/clear, first connect, duplicate, three-member chain, middle/head/tail removal, two-to-one transition, final disconnect, failed HAL enable, incompatible sharing, invalid vectors, and foreign routes. Its immutable-route assertion is a representation-specific regression check, not an independent behavioral oracle by itself; its lifecycle and rejection checks and the root public native oracle provide behavioral coverage. Parent reports the original-xemu public oracle passed 17/17, including real NV2A ISR/DPC/disconnect. The six-run world sequence supplies independent actual HDD interrupts and unchanged byte results.

Minor comment correction suggested, not a blocker: trap.s says no instruction is copied into mutable interrupt objects. KeInitializeInterrupt still copies the legacy template. The relevant property is that the dispatcher no longer executes the copied pool template. Keeping the copy avoids expanding this change's scope.

No proprietary instructions were inspected. Owned disassembly is saved as `irq-static-owned-disassembly.txt`; independent host output is reproducible with root `irq-static-host/check.py` and output `storage-cost-agent/irq-static-host-reviewed`.
