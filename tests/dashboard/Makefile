XBE_TITLE = Memory dashboard probe
NXDK_DIR ?= /usr/src/nxdk
ifeq ($(DVD_LAUNCH),1)
CFLAGS += -DDASHBOARD_LAUNCH_DVD
endif
SRCS = $(CURDIR)/main.c $(CURDIR)/tap.c
include $(NXDK_DIR)/Makefile
