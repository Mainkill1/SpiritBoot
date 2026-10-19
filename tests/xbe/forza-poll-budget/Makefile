XBE_TITLE = forza-poll-budget
GEN_XISO = forza-poll-budget.iso
NXDK_DIR ?= /home/codex/src/nxdk
SRCS = $(CURDIR)/main.c $(CURDIR)/../../../tools/storage_io_long16/tap.c
CFLAGS += -I$(CURDIR)/../../../tools/storage_io_long16 -O2 -Wall -Wextra -mno-sse -mno-sse2
include $(NXDK_DIR)/Makefile
$(CURDIR)/main.obj: CFLAGS += -Werror
