XBE_TITLE = forza-map-stream
GEN_XISO = forza-map-stream.iso
NXDK_DIR ?= /home/codex/src/nxdk
RECORDER = $(CURDIR)/../../../tools/storage_io_long16
SRCS = $(CURDIR)/main.c $(RECORDER)/recorder.c $(RECORDER)/tap.c
CFLAGS += -Wall -Wextra -I$(RECORDER)
include $(NXDK_DIR)/Makefile
