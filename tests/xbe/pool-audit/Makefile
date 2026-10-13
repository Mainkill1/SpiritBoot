XBE_TITLE = pool-allocation-audit
GEN_XISO = pool-audit.iso
NXDK_DIR ?= /usr/src/nxdk
SRCS = $(CURDIR)/main.c $(CURDIR)/tap.c
POOL_DIAGNOSTIC ?= 0
ifeq ($(POOL_DIAGNOSTIC),1)
ifndef ROSWELL_SOURCE
$(error ROSWELL_SOURCE must name the exact diagnostic build source)
endif
CFLAGS += -I$(ROSWELL_SOURCE)/ntoskrnl/xb/mm
endif
CFLAGS += -O2 -Wall -Wextra -Werror -DDIAGNOSTIC_POOL_AUDIT=$(POOL_DIAGNOSTIC)
include $(NXDK_DIR)/Makefile
