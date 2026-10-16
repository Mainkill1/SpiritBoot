// SPDX-License-Identifier: GPL-2.0-or-later
//! Executable behavior model for a possible aligned optical-read forwarding path.

use std::collections::BTreeMap;

pub mod snapshot {
    use super::{MdlFacts, Purpose, RequestFacts};

    const IRP_NOCACHE: u32 = 0x0000_0001;
    const IRP_PAGING_IO: u32 = 0x0000_0002;
    const IRP_ASSOCIATED_IRP: u32 = 0x0000_0008;
    const MDL_MAPPED_TO_SYSTEM_VA: u16 = 0x0001;
    const MDL_PAGES_LOCKED: u16 = 0x0002;
    const MDL_SOURCE_IS_NONPAGED_POOL: u16 = 0x0004;
    const MDL_HEADER_BYTES: u32 = 28;
    const PAGE_BYTES: u64 = 4096;

    #[derive(Clone, Copy, Debug, Eq, PartialEq)]
    pub enum SnapshotError {
        Unreadable,
        InvalidPointer,
        StackRelation,
        NotFile,
        AddressRange,
    }

    pub trait GuestMemory {
        fn read_exact(&self, address: u32, output: &mut [u8]) -> Result<(), SnapshotError>;
    }

    #[derive(Clone, Copy, Debug, Eq, PartialEq)]
    pub struct Layout {
        pub dispatch_irp_argument: u32,
        pub irp_flags: u32,
        pub irp_stack_count: u32,
        pub irp_current_location: u32,
        pub irp_current_stack: u32,
        pub irp_mdl: u32,
        pub stack_length: u32,
        pub stack_byte_offset: u32,
        pub stack_file_object: u32,
        pub file_fcb: u32,
        pub fcb_vcb: u32,
        pub fcb_data_sector: u32,
        pub fcb_data_size: u32,
        pub fcb_is_directory: u32,
        pub vcb_target: u32,
        pub target_alignment: u32,
    }

    impl Layout {
        pub const fn release_x86() -> Self {
            Self {
                dispatch_irp_argument: 8,
                irp_flags: 4,
                irp_stack_count: 0x18,
                irp_current_location: 0x19,
                irp_current_stack: 0x5c,
                irp_mdl: 0x6c,
                stack_length: 4,
                stack_byte_offset: 0x0c,
                stack_file_object: 0x18,
                file_fcb: 8,
                fcb_vcb: 0,
                fcb_data_sector: 4,
                fcb_data_size: 8,
                fcb_is_directory: 0x0d,
                vcb_target: 0x0c,
                target_alignment: 0x24,
            }
        }
    }

    fn address(base: u32, offset: u32) -> Result<u32, SnapshotError> {
        base.checked_add(offset).ok_or(SnapshotError::AddressRange)
    }

    fn pointer(value: u32) -> Result<u32, SnapshotError> {
        if value < 0x8000_0000 || value & 3 != 0 {
            Err(SnapshotError::InvalidPointer)
        } else {
            Ok(value)
        }
    }

    fn bytes<const N: usize>(
        memory: &impl GuestMemory,
        base: u32,
        offset: u32,
    ) -> Result<[u8; N], SnapshotError> {
        let mut result = [0; N];
        memory.read_exact(address(base, offset)?, &mut result)?;
        Ok(result)
    }

    fn u8_at(memory: &impl GuestMemory, base: u32, offset: u32) -> Result<u8, SnapshotError> {
        Ok(bytes::<1>(memory, base, offset)?[0])
    }

    fn u16_at(
        memory: &impl GuestMemory,
        base: u32,
        offset: u32,
    ) -> Result<u16, SnapshotError> {
        Ok(u16::from_le_bytes(bytes(memory, base, offset)?))
    }

    fn u32_at(
        memory: &impl GuestMemory,
        base: u32,
        offset: u32,
    ) -> Result<u32, SnapshotError> {
        Ok(u32::from_le_bytes(bytes(memory, base, offset)?))
    }

    fn u64_at(
        memory: &impl GuestMemory,
        base: u32,
        offset: u32,
    ) -> Result<u64, SnapshotError> {
        Ok(u64::from_le_bytes(bytes(memory, base, offset)?))
    }

    pub fn decode_dispatch(
        memory: &impl GuestMemory,
        esp: u32,
        layout: Layout,
    ) -> Result<RequestFacts, SnapshotError> {
        pointer(esp)?;
        let irp = pointer(u32_at(memory, esp, layout.dispatch_irp_argument)?)?;
        let flags = u32_at(memory, irp, layout.irp_flags)?;
        let stack_count = u8_at(memory, irp, layout.irp_stack_count)?;
        let current_location = u8_at(memory, irp, layout.irp_current_location)?;
        if stack_count == 0 || current_location == 0 || current_location > stack_count {
            return Err(SnapshotError::StackRelation);
        }
        let stack = pointer(u32_at(memory, irp, layout.irp_current_stack)?)?;
        let file = pointer(u32_at(memory, stack, layout.stack_file_object)?)?;
        let fcb = pointer(u32_at(memory, file, layout.file_fcb)?)?;
        if u8_at(memory, fcb, layout.fcb_is_directory)? != 0 {
            return Err(SnapshotError::NotFile);
        }
        let vcb = pointer(u32_at(memory, fcb, layout.fcb_vcb)?)?;
        let target = pointer(u32_at(memory, vcb, layout.vcb_target)?)?;

        let mdl_pointer = u32_at(memory, irp, layout.irp_mdl)?;
        let mdl = if mdl_pointer == 0 {
            None
        } else {
            let mdl = pointer(mdl_pointer)?;
            let next = u32_at(memory, mdl, 0)?;
            let size = u16_at(memory, mdl, 4)? as u32;
            let mdl_flags = u16_at(memory, mdl, 6)?;
            let mapped = u32_at(memory, mdl, 0x0c)?;
            let start = u32_at(memory, mdl, 0x10)?;
            let byte_count = u32_at(memory, mdl, 0x14)? as u64;
            let byte_offset = u32_at(memory, mdl, 0x18)? as u64;
            let span = byte_offset
                .checked_add(byte_count)
                .ok_or(SnapshotError::AddressRange)?;
            let pages = span
                .checked_add(PAGE_BYTES - 1)
                .ok_or(SnapshotError::AddressRange)?
                / PAGE_BYTES;
            let pfn_bytes = pages.checked_mul(4).ok_or(SnapshotError::AddressRange)?;
            let required_size = u64::from(MDL_HEADER_BYTES)
                .checked_add(pfn_bytes)
                .ok_or(SnapshotError::AddressRange)?;
            let use_mapped = mdl_flags
                & (MDL_MAPPED_TO_SYSTEM_VA | MDL_SOURCE_IS_NONPAGED_POOL)
                != 0;
            let data_address = if use_mapped {
                mapped
            } else {
                start
                    .checked_add(u32::try_from(byte_offset).map_err(|_| SnapshotError::AddressRange)?)
                    .ok_or(SnapshotError::AddressRange)?
            };
            Some((
                MdlFacts {
                    chained: next != 0,
                    locked_or_nonpaged: mdl_flags
                        & (MDL_PAGES_LOCKED | MDL_SOURCE_IS_NONPAGED_POOL)
                        != 0,
                    pfn_span_valid: u64::from(size) >= required_size,
                    byte_count,
                },
                u64::from(data_address),
            ))
        };

        Ok(RequestFacts {
            purpose: Purpose::FileData,
            file_offset: i64::from_le_bytes(
                u64_at(memory, stack, layout.stack_byte_offset)?.to_le_bytes(),
            ),
            requested: u64::from(u32_at(memory, stack, layout.stack_length)?),
            file_bytes: u64::from(u32_at(memory, fcb, layout.fcb_data_size)?),
            file_start_sector: u64::from(u32_at(memory, fcb, layout.fcb_data_sector)?),
            paging: flags & IRP_PAGING_IO != 0,
            associated: flags & IRP_ASSOCIATED_IRP != 0,
            noncached: flags & IRP_NOCACHE != 0,
            data_address: mdl.map_or(0, |(_, data_address)| data_address),
            alignment_mask: u64::from(u32_at(memory, target, layout.target_alignment)?),
            spare_stack: current_location > 1,
            mdl: mdl.map(|(facts, _)| facts),
        })
    }
}

pub const OPTICAL_SECTOR_BYTES: u64 = 2048;

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Purpose {
    FileData,
    Metadata,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct MdlFacts {
    pub chained: bool,
    pub locked_or_nonpaged: bool,
    pub pfn_span_valid: bool,
    pub byte_count: u64,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub struct RequestFacts {
    pub purpose: Purpose,
    pub file_offset: i64,
    pub requested: u64,
    pub file_bytes: u64,
    pub file_start_sector: u64,
    pub paging: bool,
    pub associated: bool,
    pub noncached: bool,
    pub data_address: u64,
    pub alignment_mask: u64,
    pub spare_stack: bool,
    pub mdl: Option<MdlFacts>,
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub enum TraceError {
    FieldCount { actual: usize },
    Purpose,
    Integer { field: usize },
    Boolean { field: usize },
}

pub fn parse_trace_line(line: &str) -> Result<RequestFacts, TraceError> {
    let fields: Vec<&str> = line.trim_end().split('\t').collect();
    if fields.len() != 16 {
        return Err(TraceError::FieldCount {
            actual: fields.len(),
        });
    }
    let purpose = match fields[0] {
        "file" => Purpose::FileData,
        "metadata" => Purpose::Metadata,
        _ => return Err(TraceError::Purpose),
    };
    let i64_at = |field: usize| {
        fields[field]
            .parse::<i64>()
            .map_err(|_| TraceError::Integer { field })
    };
    let u64_at = |field: usize| {
        fields[field]
            .parse::<u64>()
            .map_err(|_| TraceError::Integer { field })
    };
    let bool_at = |field: usize| match fields[field] {
        "0" => Ok(false),
        "1" => Ok(true),
        _ => Err(TraceError::Boolean { field }),
    };

    let mdl_present = bool_at(11)?;
    let mdl = MdlFacts {
        chained: bool_at(12)?,
        locked_or_nonpaged: bool_at(13)?,
        pfn_span_valid: bool_at(14)?,
        byte_count: u64_at(15)?,
    };
    Ok(RequestFacts {
        purpose,
        file_offset: i64_at(1)?,
        requested: u64_at(2)?,
        file_bytes: u64_at(3)?,
        file_start_sector: u64_at(4)?,
        paging: bool_at(5)?,
        associated: bool_at(6)?,
        noncached: bool_at(7)?,
        data_address: u64_at(8)?,
        alignment_mask: u64_at(9)?,
        spare_stack: bool_at(10)?,
        mdl: mdl_present.then_some(mdl),
    })
}

#[derive(Clone, Copy, Debug, Eq, PartialEq, Ord, PartialOrd)]
pub enum Refusal {
    Metadata,
    NegativeOffset,
    DiscRange,
    SectorShape,
    Paging,
    Associated,
    NoLowerStack,
    MissingMdl,
    ChainedMdl,
    UnprovedResidency,
    InvalidPfnSpan,
    MdlTooShort,
    BufferRange,
    BufferAlignment,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Decision {
    CompleteZero,
    ExistingPath(Refusal),
    Forward {
        absolute_offset: u64,
        effective: u64,
    },
}

pub fn classify(request: RequestFacts) -> Decision {
    if request.purpose == Purpose::Metadata {
        return Decision::ExistingPath(Refusal::Metadata);
    }
    let Ok(file_offset) = u64::try_from(request.file_offset) else {
        return Decision::ExistingPath(Refusal::NegativeOffset);
    };
    if request.requested == 0 || file_offset >= request.file_bytes {
        return Decision::CompleteZero;
    }

    let effective = request.requested.min(request.file_bytes - file_offset);
    let Some(file_base) = request.file_start_sector.checked_mul(OPTICAL_SECTOR_BYTES) else {
        return Decision::ExistingPath(Refusal::DiscRange);
    };
    let Some(absolute_offset) = file_base.checked_add(file_offset) else {
        return Decision::ExistingPath(Refusal::DiscRange);
    };
    if absolute_offset.checked_add(effective).is_none() {
        return Decision::ExistingPath(Refusal::DiscRange);
    }
    if absolute_offset % OPTICAL_SECTOR_BYTES != 0
        || effective % OPTICAL_SECTOR_BYTES != 0
    {
        return Decision::ExistingPath(Refusal::SectorShape);
    }
    if request.paging {
        return Decision::ExistingPath(Refusal::Paging);
    }
    if request.associated {
        return Decision::ExistingPath(Refusal::Associated);
    }
    if !request.spare_stack {
        return Decision::ExistingPath(Refusal::NoLowerStack);
    }

    let Some(mdl) = request.mdl else {
        return Decision::ExistingPath(Refusal::MissingMdl);
    };
    if mdl.chained {
        return Decision::ExistingPath(Refusal::ChainedMdl);
    }
    if !mdl.locked_or_nonpaged {
        return Decision::ExistingPath(Refusal::UnprovedResidency);
    }
    if !mdl.pfn_span_valid {
        return Decision::ExistingPath(Refusal::InvalidPfnSpan);
    }
    if mdl.byte_count < effective {
        return Decision::ExistingPath(Refusal::MdlTooShort);
    }
    if request.data_address.checked_add(effective).is_none() {
        return Decision::ExistingPath(Refusal::BufferRange);
    }
    if request.data_address & request.alignment_mask != 0 {
        return Decision::ExistingPath(Refusal::BufferAlignment);
    }

    Decision::Forward {
        absolute_offset,
        effective,
    }
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Terminal {
    Success { bytes: u64 },
    Failure,
    Cancelled,
}

#[derive(Clone, Copy, Debug, Eq, PartialEq)]
pub enum Completion {
    Success {
        information: u64,
        offset_advance: u64,
        pending: bool,
    },
    EndOfFile {
        information: u64,
        offset_advance: u64,
        pending: bool,
    },
    Failure {
        information: u64,
        offset_advance: u64,
        pending: bool,
    },
    Cancelled {
        information: u64,
        offset_advance: u64,
        pending: bool,
    },
    ProtocolError {
        information: u64,
        offset_advance: u64,
        pending: bool,
    },
}

pub fn normalize_completion(effective: u64, terminal: Terminal, pending: bool) -> Completion {
    match terminal {
        Terminal::Success { bytes } if bytes == effective => Completion::Success {
            information: bytes,
            offset_advance: bytes,
            pending,
        },
        Terminal::Success { bytes } if bytes < effective => Completion::EndOfFile {
            information: 0,
            offset_advance: 0,
            pending,
        },
        Terminal::Success { .. } => Completion::ProtocolError {
            information: 0,
            offset_advance: 0,
            pending,
        },
        Terminal::Failure => Completion::Failure {
            information: 0,
            offset_advance: 0,
            pending,
        },
        Terminal::Cancelled => Completion::Cancelled {
            information: 0,
            offset_advance: 0,
            pending,
        },
    }
}

#[derive(Clone, Debug, Eq, PartialEq)]
pub struct Estimate {
    pub samples: u64,
    pub forwarded: u64,
    pub existing: u64,
    pub complete_zero: u64,
    pub removed_child_requests: u64,
    pub removed_mdl_pairs: u64,
    pub removed_internal_waits: u64,
    pub refusals: BTreeMap<Refusal, u64>,
}

pub fn estimate<I>(requests: I) -> Estimate
where
    I: IntoIterator<Item = RequestFacts>,
{
    let mut result = Estimate {
        samples: 0,
        forwarded: 0,
        existing: 0,
        complete_zero: 0,
        removed_child_requests: 0,
        removed_mdl_pairs: 0,
        removed_internal_waits: 0,
        refusals: BTreeMap::new(),
    };

    for request in requests {
        result.samples += 1;
        match classify(request) {
            Decision::CompleteZero => result.complete_zero += 1,
            Decision::ExistingPath(reason) => {
                result.existing += 1;
                *result.refusals.entry(reason).or_insert(0) += 1;
            }
            Decision::Forward { .. } => {
                result.forwarded += 1;
                result.removed_child_requests += 1;
                result.removed_mdl_pairs += 1;
                result.removed_internal_waits += 1;
            }
        }
    }
    result
}
