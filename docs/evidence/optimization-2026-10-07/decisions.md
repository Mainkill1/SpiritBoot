# Review dispositions and controller decisions

The broad review covers product a8824776..52807f8 and public kernel
291ad975..87aba89a. The scoped documentation review covers 52807f8..f49e1406.
Both have no Critical or Important finding. M2's stale qualification wording
was corrected; M1's broader per-PFN fixture assertion remains a nonblocking
follow-up. Firmware, source patch, runtime inputs and samples are unchanged.

Controller rulings:

- Unknown-type registration rechecks duplicates when the locked registry count
  changed. Never-removed, distinct allocated nodes in a 32-bit address space
  bound the count below wrap; stable count proves no insertion. If that proof
  fails, duplicate registration could occur. Reentrant tests and source review
  cover the existing lifetime contract.
- Preserve the byte-exact broad review and its 159-file count at reviewed
  commit52807f8. The next scoped check covers all160files after adding that
  review. Counts in historical reviews refer to their reviewed stages; the
  current SHA256SUMS.txt covers the full current evidence directory. If misread,
  readers could confuse totals between stages. No evidence was omitted.
