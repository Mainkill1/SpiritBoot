# Optical profile integration and remaining dependencies

Patch 0139 owns only the optical creation profile and resident dispatch
selection.  It deliberately has no `DriverEntry`, `AddDevice`, PnP handler,
device allocation, symbolic-link cleanup, child request, completion callback or
cancel callback.

The final composed stack has these exact dependencies:

1. Patch 0138 supplies the portable shared Disk/Cdrom policy and lifecycle
   state machine.  Its portable translation unit does not itself contain the
   target `CdromDriverEntry` wrapper.
2. Post-stack target glue must install `NxCdromInstallRuntimeDispatch`, install
   the owner's CREATE/CLOSE and bounded late-PnP routes, call
   `NxCdromBuildDeviceInit`, and pass that profile to exactly one
   `NxNativeCreateClassDevice` call.  It may advance 0138's owner state only
   after native creation succeeds.
3. Patch 0140 supplies `native_adapter.h`, `NX_NATIVE_DEVICE_INIT`,
   `NxNativeCreateClassDevice`, `NxNativeDispatchReadWrite`,
   `NxNativeDispatchControl`, and `NxNativeDispatchFlush`.  It exclusively owns
   READ(10), READ CAPACITY/media publication, TOC, TUR/check-verify, property
   forwarding, native child packets, completion, cancellation and rundown.
4. The product lock must order 0138, 0139, then 0140.  Patch 0139 adds its source
   with `target_sources(nxstorage PRIVATE nxcdrom_profile.c)` so the 0138
   `add_library` edit remains independent.
5. The complete-candidate class and kernel CMake selections must contain only
   `nxstorage`; patch 0139 removes the separate legacy `nxcdrom` archive from
   both locations.  ClassPnP and the old disk archive were already absent from
   this backend selection.
6. Final closure still requires the composed target compile/link, proof that
   the runtime dispatches remain resident after PnP sealing, and native
   boot/read/capacity/TOC/check-verify/cancel/teardown execution.  Host profile
   tests cannot satisfy those gates.

The 0139 optical object itself has exactly three undefined adapter symbols:
`NxNativeDispatchReadWrite`, `NxNativeDispatchControl`, and
`NxNativeDispatchFlush`.  The composition glue additionally needs the public
`NxNativeCreateClassDevice` entry point.  No private adapter structure is
required.
