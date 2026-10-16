XBE_TITLE = forza-map-stream-profile
GEN_XISO = forza-map-stream-profile.iso
NXDK_DIR ?= /home/codex/src/nxdk
RECORDER = $(CURDIR)/tools/storage_io_long16
SRCS = $(CURDIR)/main.c $(RECORDER)/recorder.c $(RECORDER)/tap.c
CFLAGS += -O2 -Wall -Wextra -I$(RECORDER)
LDFLAGS += /map:profile.map
include $(NXDK_DIR)/Makefile
