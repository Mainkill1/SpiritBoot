# Scoped input-manifest history

The hash-named JSON files preserve available earlier approval-manifest bytes.
`fe9c8f587f041249cd121f27828c6608b94c098a6af285a65f2d178aabbe84fc`
is the previously committed 29-file packet;
`2e0f4c9f682278199bd952e4e91c69fe4c9b07f85f16425747cc8b48e78758b6`
is the 44-file packet before the five nested geometry constants were added.

Stage receipts may pin an earlier manifest hash. The cache primitive's historical
receipt pins `6aa09c68ec10ae48e681cb4f11d277b407c9252f316d9fdf1a430f0bbcc3a144`;
its exact manifest bytes are not yet archived here. The individually pinned ABI
input files are present. Do not substitute the current manifest for that earlier
hash or describe this directory as complete historical input reconstruction.

The current manifest and per-file ledger remain the authority for new scoped
input use. Neither manifest grants permission for unlisted implementation bodies
or completes the final compiled-source/license gate.
