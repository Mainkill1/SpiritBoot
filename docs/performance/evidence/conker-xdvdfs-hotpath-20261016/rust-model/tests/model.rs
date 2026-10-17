// SPDX-License-Identifier: GPL-2.0-or-later
use optical_forwarding_model::{
    classify, estimate, normalize_completion, parse_trace_line, Completion,
    snapshot::{decode_dispatch, GuestMemory, Layout, SnapshotError}, Decision,
    MdlFacts, Purpose, Refusal, RequestFacts, Terminal,
};

struct Memory(Vec<u8>);

const BASE: u32 = 0x8000_0000;

impl Memory {
    fn put_u8(&mut self, address: u32, value: u8) {
        self.0[(address - BASE) as usize] = value;
    }

    fn put_u16(&mut self, address: u32, value: u16) {
        let start = (address - BASE) as usize;
        self.0[start..start + 2].copy_from_slice(&value.to_le_bytes());
    }

    fn put_u32(&mut self, address: u32, value: u32) {
        let start = (address - BASE) as usize;
        self.0[start..start + 4].copy_from_slice(&value.to_le_bytes());
    }

    fn put_u64(&mut self, address: u32, value: u64) {
        let start = (address - BASE) as usize;
        self.0[start..start + 8].copy_from_slice(&value.to_le_bytes());
    }
}

impl GuestMemory for Memory {
    fn read_exact(&self, address: u32, output: &mut [u8]) -> Result<(), SnapshotError> {
        let start = address
            .checked_sub(BASE)
            .ok_or(SnapshotError::Unreadable)? as usize;
        let end = start
            .checked_add(output.len())
            .ok_or(SnapshotError::Unreadable)?;
        let source = self.0.get(start..end).ok_or(SnapshotError::Unreadable)?;
        output.copy_from_slice(source);
        Ok(())
    }
}

fn dispatch_memory() -> (Memory, u32) {
    let mut memory = Memory(vec![0; 0x9000]);
    let esp = BASE + 0x1000;
    let irp = BASE + 0x2000;
    let stack = BASE + 0x3000;
    let file = BASE + 0x4000;
    let fcb = BASE + 0x5000;
    let vcb = BASE + 0x6000;
    let target = BASE + 0x7000;
    let mdl = BASE + 0x8000;
    memory.put_u32(esp + 8, irp);
    memory.put_u32(irp + 4, 0);
    memory.put_u8(irp + 0x18, 3);
    memory.put_u8(irp + 0x19, 2);
    memory.put_u32(irp + 0x5c, stack);
    memory.put_u32(irp + 0x6c, mdl);
    memory.put_u32(stack + 4, 4096);
    memory.put_u64(stack + 0x0c, 0);
    memory.put_u32(stack + 0x18, file);
    memory.put_u32(file + 8, fcb);
    memory.put_u32(fcb, vcb);
    memory.put_u32(fcb + 4, 32);
    memory.put_u32(fcb + 8, 8192);
    memory.put_u8(fcb + 0x0d, 0);
    memory.put_u32(vcb + 0x0c, target);
    memory.put_u32(target + 0x24, 3);
    memory.put_u32(mdl, 0);
    memory.put_u16(mdl + 4, 32);
    memory.put_u16(mdl + 6, 0x0002);
    memory.put_u32(mdl + 0x0c, 0);
    memory.put_u32(mdl + 0x10, 0x1000);
    memory.put_u32(mdl + 0x14, 4096);
    memory.put_u32(mdl + 0x18, 0);
    (memory, esp)
}

fn eligible() -> RequestFacts {
    RequestFacts {
        purpose: Purpose::FileData,
        file_offset: 0,
        requested: 4096,
        file_bytes: 8192,
        file_start_sector: 32,
        paging: false,
        associated: false,
        noncached: false,
        data_address: 0x1000,
        alignment_mask: 3,
        spare_stack: true,
        mdl: Some(MdlFacts {
            chained: false,
            locked_or_nonpaged: true,
            pfn_span_valid: true,
            byte_count: 4096,
        }),
    }
}

#[test]
fn cache_flag_does_not_disqualify_device_io() {
    let cached = eligible();
    let mut noncached = eligible();
    noncached.noncached = true;
    assert!(matches!(classify(cached), Decision::Forward { .. }));
    assert!(matches!(classify(noncached), Decision::Forward { .. }));
}

#[test]
fn forwards_only_a_fully_proved_aligned_file_read() {
    assert_eq!(
        classify(eligible()),
        Decision::Forward {
            absolute_offset: 32 * 2048,
            effective: 4096,
        }
    );
}

#[test]
fn zero_and_eof_reads_complete_without_lower_work() {
    let mut r = eligible();
    r.requested = 0;
    assert_eq!(classify(r), Decision::CompleteZero);
    r = eligible();
    r.file_offset = r.file_bytes as i64;
    assert_eq!(classify(r), Decision::CompleteZero);
}

#[test]
fn eof_truncation_precedes_alignment_and_coverage() {
    let mut r = eligible();
    r.file_offset = 4096;
    r.requested = 8192;
    r.file_bytes = 8192;
    r.mdl.as_mut().unwrap().byte_count = 4096;
    assert_eq!(
        classify(r),
        Decision::Forward {
            absolute_offset: 32 * 2048 + 4096,
            effective: 4096,
        }
    );
}

#[test]
fn unaligned_eof_tail_uses_existing_path() {
    let mut r = eligible();
    r.file_offset = 4096;
    r.file_bytes = 4096 + 17;
    assert_eq!(classify(r), Decision::ExistingPath(Refusal::SectorShape));
}

#[test]
fn refuses_every_unproved_ownership_shape() {
    let cases: &[(fn(&mut RequestFacts), Refusal)] = &[
        (|r| r.purpose = Purpose::Metadata, Refusal::Metadata),
        (|r| r.file_offset = -1, Refusal::NegativeOffset),
        (|r| r.paging = true, Refusal::Paging),
        (|r| r.associated = true, Refusal::Associated),
        (|r| r.spare_stack = false, Refusal::NoLowerStack),
        (|r| r.mdl = None, Refusal::MissingMdl),
        (|r| r.mdl.as_mut().unwrap().chained = true, Refusal::ChainedMdl),
        (
            |r| r.mdl.as_mut().unwrap().locked_or_nonpaged = false,
            Refusal::UnprovedResidency,
        ),
        (
            |r| r.mdl.as_mut().unwrap().pfn_span_valid = false,
            Refusal::InvalidPfnSpan,
        ),
        (|r| r.mdl.as_mut().unwrap().byte_count = 2048, Refusal::MdlTooShort),
        (|r| r.data_address = 0x1001, Refusal::BufferAlignment),
    ];
    for (mutate, expected) in cases {
        let mut r = eligible();
        mutate(&mut r);
        assert_eq!(classify(r), Decision::ExistingPath(*expected));
    }
}

#[test]
fn refuses_checked_arithmetic_overflow() {
    let mut r = eligible();
    r.file_start_sector = u64::MAX;
    assert_eq!(classify(r), Decision::ExistingPath(Refusal::DiscRange));
    r = eligible();
    r.data_address = u64::MAX - 1024;
    assert_eq!(classify(r), Decision::ExistingPath(Refusal::BufferRange));
}

#[test]
fn does_not_impose_a_transport_chunk_limit() {
    let mut r = eligible();
    r.requested = 512 * 1024;
    r.file_bytes = r.requested;
    r.mdl.as_mut().unwrap().byte_count = r.requested;
    assert!(matches!(classify(r), Decision::Forward { effective, .. } if effective == 512 * 1024));
}

#[test]
fn normalizes_terminal_results_without_leaking_partial_bytes() {
    assert_eq!(
        normalize_completion(4096, Terminal::Success { bytes: 4096 }, true),
        Completion::Success { information: 4096, offset_advance: 4096, pending: true }
    );
    assert_eq!(
        normalize_completion(4096, Terminal::Success { bytes: 2048 }, false),
        Completion::EndOfFile { information: 0, offset_advance: 0, pending: false }
    );
    assert_eq!(
        normalize_completion(4096, Terminal::Failure, true),
        Completion::Failure { information: 0, offset_advance: 0, pending: true }
    );
    assert_eq!(
        normalize_completion(4096, Terminal::Cancelled, false),
        Completion::Cancelled { information: 0, offset_advance: 0, pending: false }
    );
    assert_eq!(
        normalize_completion(4096, Terminal::Success { bytes: 4097 }, false),
        Completion::ProtocolError { information: 0, offset_advance: 0, pending: false }
    );
}

#[test]
fn estimate_conserves_samples_and_bounds_removed_work() {
    let mut unaligned = eligible();
    unaligned.requested = 17;
    let report = estimate([eligible(), unaligned]);
    assert_eq!(report.samples, 2);
    assert_eq!(report.forwarded, 1);
    assert_eq!(report.existing, 1);
    assert_eq!(report.complete_zero, 0);
    assert_eq!(report.removed_child_requests, 1);
    assert_eq!(report.removed_mdl_pairs, 1);
    assert_eq!(report.removed_internal_waits, 1);
    assert_eq!(report.refusals.get(&Refusal::SectorShape), Some(&1));
}

#[test]
fn boundary_facts_never_panic_or_wrap_into_forwarding() {
    let values = [0, 1, 2047, 2048, 4096, u64::MAX - 1, u64::MAX];
    for sector in values {
        for requested in values {
            for bytes in values {
                let mut r = eligible();
                r.file_start_sector = sector;
                r.requested = requested;
                r.file_bytes = bytes;
                let decision = classify(r);
                if let Decision::Forward { absolute_offset, effective } = decision {
                    assert_eq!(absolute_offset % 2048, 0);
                    assert_eq!(effective % 2048, 0);
                    assert!(effective <= requested);
                    assert!(absolute_offset.checked_add(effective).is_some());
                }
            }
        }
    }
}

#[test]
fn parses_a_complete_scalar_trace_record() {
    let request = parse_trace_line(
        "file\t0\t4096\t8192\t32\t0\t0\t0\t4096\t3\t1\t1\t0\t1\t1\t4096",
    )
    .unwrap();
    assert_eq!(request, eligible());
    assert!(matches!(classify(request), Decision::Forward { .. }));
}

#[test]
fn trace_parser_rejects_missing_or_ambiguous_facts() {
    let valid = "file\t0\t4096\t8192\t32\t0\t0\t0\t4096\t3\t1\t1\t0\t1\t1\t4096";
    assert!(parse_trace_line("file\t0").is_err());
    assert!(parse_trace_line(&valid.replace("file", "unknown")).is_err());
    assert!(parse_trace_line(&valid.replacen("\t0\t", "\tmaybe\t", 1)).is_err());
    assert!(parse_trace_line(&valid.replace("\t4096", "\tnan")).is_err());
}

#[test]
fn decodes_a_complete_release_dispatch_snapshot() {
    let (memory, esp) = dispatch_memory();
    assert_eq!(decode_dispatch(&memory, esp, Layout::release_x86()).unwrap(), eligible());
}

#[test]
fn dispatch_snapshot_preserves_flags_and_mdl_shape() {
    let (mut memory, esp) = dispatch_memory();
    memory.put_u32(BASE + 0x2000 + 4, 0x0b);
    memory.put_u32(BASE + 0x8000, BASE + 0x8100);
    let decoded = decode_dispatch(&memory, esp, Layout::release_x86()).unwrap();
    assert!(decoded.paging);
    assert!(decoded.associated);
    assert!(decoded.noncached);
    assert!(decoded.mdl.unwrap().chained);
}

#[test]
fn dispatch_snapshot_rejects_unproved_or_inconsistent_memory() {
    let (mut memory, esp) = dispatch_memory();
    memory.put_u32(esp + 8, 0);
    assert_eq!(
        decode_dispatch(&memory, esp, Layout::release_x86()),
        Err(SnapshotError::InvalidPointer)
    );

    let (mut memory, esp) = dispatch_memory();
    memory.put_u8(BASE + 0x2000 + 0x19, 4);
    assert_eq!(
        decode_dispatch(&memory, esp, Layout::release_x86()),
        Err(SnapshotError::StackRelation)
    );

    let (mut memory, esp) = dispatch_memory();
    memory.put_u16(BASE + 0x8000 + 4, 28);
    let decoded = decode_dispatch(&memory, esp, Layout::release_x86()).unwrap();
    assert!(!decoded.mdl.unwrap().pfn_span_valid);
}

#[test]
fn dispatch_snapshot_uses_checked_virtual_address_rules() {
    let (mut memory, esp) = dispatch_memory();
    memory.put_u16(BASE + 0x8000 + 6, 0x0004);
    memory.put_u32(BASE + 0x8000 + 0x0c, 0x9000);
    assert_eq!(
        decode_dispatch(&memory, esp, Layout::release_x86())
            .unwrap()
            .data_address,
        0x9000
    );

    let (mut memory, esp) = dispatch_memory();
    memory.put_u32(BASE + 0x8000 + 0x10, u32::MAX);
    memory.put_u32(BASE + 0x8000 + 0x18, 1);
    assert_eq!(
        decode_dispatch(&memory, esp, Layout::release_x86()),
        Err(SnapshotError::AddressRange)
    );
}
