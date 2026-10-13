# Independent warm-persistence probe

Set `NXDK_DIR` and add its `bin` directory to `PATH`, then run `make` here.
Boot the resulting `extent-persist-probe.iso` in a disposable 64 MiB xemu
fixture. It reboots once through public launch data and powers off.

Successful output has three setup checks before reset and four checks in a
second TAP stream. The generic single-stream CI grader cannot grade this
combined log; both stages must be checked. Earlier SpiritBoot builds report
an incorrect initial size and fail restored ownership.

The exact main source is the native qualification input. Helper files come
from the owned regression harness. The Makefile only makes its nxdk path
portable. No game assets are included.
