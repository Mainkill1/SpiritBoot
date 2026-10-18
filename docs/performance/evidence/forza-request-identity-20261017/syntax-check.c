/* SPDX-License-Identifier: MIT
 * Host syntax harness only. Not an emulator or firmware build. */
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <string.h>
enum {R_ESP,R_EAX,R_EBX,R_ECX,R_EDX,R_EDI,R_EBP,R_ESI};
typedef struct {uint32_t regs[8];} CPUX86State;
enum {QEMU_CLOCK_HOST,QEMU_CLOCK_VIRTUAL};
extern void *env_cpu(CPUX86State *);
extern int cpu_memory_rw_debug(void *,uint32_t,uint8_t *,unsigned,bool);
extern uint32_t ldl_le_p(const uint8_t *);
extern int64_t qemu_clock_get_ns(int);
#include "observer.c"
void syntax_entry(CPUX86State *env,uint32_t pc){forza_identity_profile(env,pc);}
