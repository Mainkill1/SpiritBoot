# Gather write comparison

Public nxdk fixture: 72 exact-byte/status/count/source-canary/EOF checks across
five nonadjacent page lists and matched flat write controls. Seven samples per
size include a first-use sample; subsequent six are warm. File extension and
verification stay outside each QPC interval. Both synchronous write paths share
the file, offset and bytes. No proprietary title data is included.

Build using the locked nxdk container and `make NXDK_DIR=/usr/src/nxdk`.
An optimization is accepted only after matched native runs retain all controls,
including regressions. The fixture powers off after draining serial output.
