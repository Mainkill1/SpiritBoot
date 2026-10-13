XBE_TITLE = extent-persist-contract
GEN_XISO = extent-persist-probe.iso
ifndef NXDK_DIR
$(error Set NXDK_DIR to a built nxdk checkout)
endif
SRCS = $(CURDIR)/main.c $(CURDIR)/tap.c
CFLAGS += -O2 -Wall -Wextra -Werror
include $(NXDK_DIR)/Makefile
