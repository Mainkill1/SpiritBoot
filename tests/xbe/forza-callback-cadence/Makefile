XBE_TITLE = forza-callback-cadence
GEN_XISO = forza-callback-cadence.iso
NXDK_DIR ?= /home/codex/src/nxdk
SRCS = $(CURDIR)/main.c $(CURDIR)/../../../tools/storage_io_long16/tap.c
CFLAGS += -O2 -Wall -Wextra -mno-sse -mno-sse2 -I$(CURDIR)/../../../tools/storage_io_long16
include $(NXDK_DIR)/Makefile
$(CURDIR)/main.obj: CFLAGS += -Werror
