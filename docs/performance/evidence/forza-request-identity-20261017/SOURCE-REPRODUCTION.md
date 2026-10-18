# Observer source reproduction

The complete observation source is now reproducible from the public Mainkill1/xemu fork commit
`f3c528eeec86db32c9f96a932267105e83f77375`, on
[fix/nv2a-bql-surface-deadlock](https://github.com/Mainkill1/xemu/tree/fix/nv2a-bql-surface-deadlock).
This is a fork commit, not an official upstream xemu commit. The cumulative patch covers exactly
`target/i386/helper.h`, `target/i386/tcg/misc_helper.c` and
`target/i386/tcg/translate.c`, including their earlier diagnostic dependencies.
No firmware or game implementation is embedded. Existing xemu file notices and
the upstream license apply to the patched files; the standalone independently
authored observer and verification scripts carry their SPDX notices.

Use an otherwise clean checkout, with `EVIDENCE` set to this archive directory:

```sh
git clone https://github.com/Mainkill1/xemu.git xemu-identity
cd xemu-identity
git checkout --detach f3c528eeec86db32c9f96a932267105e83f77375
git submodule update --init --recursive
git apply --check "$EVIDENCE/xemu-cumulative-observer.patch"
git apply "$EVIDENCE/xemu-cumulative-observer.patch"
python3 "$EVIDENCE/verify_clean_source.py" .
```

The verifier independently extracts the three original files from Git objects
into a temporary directory, checks their hashes, applies the cumulative patch,
and checks all three resulting hashes against the captured source. It neither
edits the supplied checkout nor rebuilds. The archived
`clean-source-verification.json` records a successful isolated application and
exact agreement, including the two source hashes in capture provenance.

The helper declaration and both translation and implementation bindings are
included, so this observer does not require any other diagnostic source patch.
The earlier incremental `stage.py` is retained for review history; it is not the
clean-checkout installation entry point.

The captured Windows build used container
`ghcr.io/xemu-project/xemu-win64-toolchain-gcc:sha-2881edd`, source mounted at
`/src`, an LTO cache at `/xemu-cache/lto`, and `/src/build` as its working
directory. `build-configuration.json` retains the exact configure and build
argument vectors from the existing configuration. For a new build, create those
mounts and the build directory, run the recorded configure argument vector in
that directory, then run `ninja -j8 qemu-system-i386w.exe`. The upstream checkout
and its submodules supply the normal emulator build prerequisites. No new clean
configure or build was performed as part of this source verification.

Enable only `XEMU_SPIRIT_MENU_TRACE=1`, `XEMU_FORZA_IDENTITY=1`, and
`XEMU_FORZA_IDENTITY_OUTPUT` set to a writable output filename for this capture.
Leave `XEMU_FORZA_CLOCK_TRACE` unset. The twelve-site identity path bypasses the
older probes included in the cumulative source. Use the exact owned baseline
and preserved snapshot identified in capture provenance; these addresses do not
apply to a newly built or changed firmware image. Normal emulator exit is
required to flush the scalar buffer. The archived receipt procedure describes
boot, restore, replay, pause verification and normal quit; firmware, game data
and the preserved disk must be supplied separately by their authorized owner.

This verifies observation-source reproduction, not bit-identical reproduction
of the captured executable. The capture worktree also had earlier IDE/texture
diagnostic changes, dirty ROM/submodule checkouts, and generated build state.
`xemu-source-provenance.json` records the other dirty paths at freeze. Those
unrelated patches and exact submodule states are not reconstructed here. Their
possible effect on timing is a limitation of the captured measurements. A new
clean build must therefore be treated as a new instrumented capture, with its
own executable hash and receipts, rather than substituted for this run.
