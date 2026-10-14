XBE_TITLE = storage-perf
MODE ?= pilot
GEN_XISO = $(XBE_TITLE)-$(MODE).iso
ifeq ($(MODE),dvd)
OUTPUT_DIR = bin-dvd
endif
NXDK_DIR ?= /home/codex/src/nxdk
ifeq ($(MODE),suite)
SRCS = $(CURDIR)/suite.c $(CURDIR)/pilot.c $(CURDIR)/replay.c $(CURDIR)/families.c $(CURDIR)/tap.c
CFLAGS += -DSTORAGE_SUITE
else
SRCS = $(CURDIR)/$(MODE).c $(CURDIR)/$(if $(filter pilot,$(MODE)),pilot-tap.c,tap.c)
endif
include $(NXDK_DIR)/Makefile

# NXDK object names are source-based; rebuild these small owned objects so a
# change between standalone and STORAGE_SUITE cannot reuse wrong CFLAGS.
.PHONY: FORCE
FORCE:
$(OBJS): FORCE

ifneq ($(filter $(MODE),suite replay),)
$(OBJS): $(CURDIR)/replay-requests.h
endif
$(CURDIR)/replay-requests.h: $(CURDIR)/replay-requests.csv $(CURDIR)/make-replay-requests.py
	python3 $(CURDIR)/make-replay-requests.py --input $(CURDIR)/replay-requests.csv --output $@

ifeq ($(MODE),dvd)
ifeq ($(strip $(DVD_CLEAN_ISO)),)
$(error MODE=dvd requires DVD_CLEAN_ISO with the pinned released clean ISO)
endif
ifeq ($(strip $(DVD_PERFORMANCE_ISO)),)
$(error MODE=dvd requires DVD_PERFORMANCE_ISO with the pinned released performance ISO)
endif
ifeq ($(strip $(DVD_EXTRACTOR)),)
$(error MODE=dvd requires DVD_EXTRACTOR)
endif
ifeq ($(strip $(DVD_EXTRACTOR_SHA256)),)
$(error MODE=dvd requires DVD_EXTRACTOR_SHA256)
endif
$(OBJS): $(CURDIR)/dvd-metadata-reference.h
# Recheck input pins even when a generated header already exists.
$(CURDIR)/dvd-metadata-reference.h: FORCE $(CURDIR)/make-dvd-references.py $(DVD_CLEAN_ISO) $(DVD_PERFORMANCE_ISO) $(DVD_EXTRACTOR)
	python3 $(CURDIR)/make-dvd-references.py --clean-iso "$(DVD_CLEAN_ISO)" --performance-iso "$(DVD_PERFORMANCE_ISO)" --extractor "$(DVD_EXTRACTOR)" --extractor-sha256 "$(DVD_EXTRACTOR_SHA256)" --output "$@" --manifest "$(CURDIR)/dvd-reference-manifest.json"
endif

.PHONY: native-host-launchers
native-host-launchers:
	mkdir -p host-bin
	python3 make-pipe-header.py
	cc -O2 -Wall -Wextra linux-launch.c -o host-bin/native-launch
	llvm-dlltool-19 -m i386:x86-64 -d kernel32.def -l host-bin/kernel32.lib
	llvm-dlltool-19 -m i386:x86-64 -d user32.def -l host-bin/user32.lib
	clang-19 --target=x86_64-pc-windows-msvc -fno-builtin -fno-stack-protector -O2 -c windows-launch.c -o host-bin/windows-launch.obj
	lld-link /entry:mainCRTStartup /subsystem:console /nodefaultlib /out:host-bin/native-launch.exe host-bin/windows-launch.obj host-bin/kernel32.lib host-bin/user32.lib
