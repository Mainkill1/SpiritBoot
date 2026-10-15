# Advanced experiment controls

SpiritBoot keeps reference-compatible behavior unless a tester explicitly enables an experiment for the current boot. Hold **X** during the three-second boot prompt, select the experiment in the setup menu, and choose **Discard and continue**. Experimental choices are held in RAM, are never written to EEPROM, and return to off after a reboot.

## Contiguous cache alias

`Advanced: contig cache` tests an alternate return address for `MmAllocateContiguousMemoryEx` calls made with `PAGE_WRITECOMBINE` or `PAGE_NOCACHE`.

- **Off (default):** return the cached `0x83xxxxxx` KSEG0 alias, matching the observed Complex behavior.
- **On:** return the `0xF3xxxxxx` aperture alias for write-combined and no-cache requests. `MmGetPhysicalAddress` translates RAM addresses in this aperture back to their physical address while preserving device MMIO addresses.

The toggle exists to isolate game graphics and streaming behavior without changing the release default. The boot log records `SpiritBoot experimental flags: 00000001` when this experiment is active and `00000000` when it is not.

## Evidence required for a comparison

Record the BIOS SHA-256, RAM size, xemu build, title and exact game location, whether the toggle was on, and the result after a cold boot. Compare the same title state with the toggle off before drawing a conclusion. A useful result includes visible correctness, time to reach gameplay, missing or delayed resources, and whether the game remains stable through save and reset.

Host coverage verifies that the default remains the cached KSEG0 alias, the opt-in path returns the F3 alias, RAM aliases round-trip through `MmGetPhysicalAddress`, MMIO identity remains unchanged, and changing the experiment does not request an EEPROM write.
