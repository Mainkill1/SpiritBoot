# Reviewed clean-room kernel patch

`0001-clean-room-kernel.patch` is the complete binary-capable, full-index Git
diff from the public Roswell base `1569e2e89fb47cc72b9c704a8884f98200432bd4`
to the independently implemented and reviewed source commit
`f67f2b1d21f249e1dec8efa652f8747551fae844`. Its resulting Git tree is
`8ba32f2153b4716c8cac269bad06a78553f98ded`.

The export includes production changes, host fixtures, and guest tests. File
license notices are retained verbatim; Roswell's existing license continues
to apply to the integrated source. The integration code reads the ordered
patch path and SHA-256 from `sources/firmware-lock.json`, leaving the public
base revision unchanged. Source review approval does not replace independent
patched-build and runtime verification.

Export command (against the reviewed public-source checkout):

```sh
git diff --binary --full-index --no-ext-diff --no-textconv \
  1569e2e89fb47cc72b9c704a8884f98200432bd4 \
  f67f2b1d21f249e1dec8efa652f8747551fae844 -- \
  > 0001-clean-room-kernel.patch
```
