# Preserve the desktop server error on pipe EOF

The Windows V23 lifetime probe reached its intentional 120-second graphical
child deadline. The server killed its exact child, and the wrapper's owned job
reported zero remaining descendants. Qualification nevertheless failed because
the specific server deadline error was absent.

The server disposed its pipe in `finally` before PowerShell finished emitting
the terminating exception. The client's asynchronous read returned EOF, and
`$done.Result.Split('|')` raised on null. Client cleanup then killed the server
while it was still unwinding, leaving its stderr empty. The original failed
run is retained as `20261014-162325708-a52e392832b24f58ae9aaee08b090691`.

The client now waits for that exact server to exit and drains and saves both
output streams before interpreting the completion message. EOF then produces
an explicit error pointing to the saved server output. The existing 5-second
exit wait, 3-second stream waits, 120-second child deadline, 170-second wrapper
deadline, private state and process ownership rules remain in effect. Cleanup
still stops only processes owned by this job.

A clean source build produced launcher SHA256
`a61757b17e2da594607e82d3f8595b1faba61c3ed4d1b6276373e39b15613b79`.
The new Windows-only V27 plan retains the original strict V23 grading and uses
fresh declared test identities. The V23 freeze and failed result are unchanged.
Independent review verified all 43 frozen files, clean-build closure and actual
embedded PowerShell bytes. All four real Windows V27 runs then passed strict
grading through the Codex desktop pipe: normal reads, 210 public queries, the
intentional deadline, and normal reads afterward. The deadline run preserved
the exact error and confirmed zero owned descendants. The recovery run verified
another 1,024 reads/4 MiB. See the retained
[native receipt](windows-v27-native-receipt.json) and
[Windows qualification](WINDOWS-NATIVE-QUALIFICATION.md).

This is a test-launcher error-retention fix. It makes no change to the BIOS or
the replacement driver's qualification status.
