/* Optional interoperability declaration, pending root admission.
 * Needed only for an independently owned mapped descriptor lifecycle.
 * No MmPrepareMdlForReuse/header helper body is supplied.
 * Requires separately admitted VOID/NTAPI/PVOID/PMDL declarations.
 */
#pragma once
VOID NTAPI MmUnmapLockedPages(PVOID BaseAddress, PMDL MemoryDescriptorList);
