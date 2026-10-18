/* SPDX-License-Identifier: MIT */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <string.h>
enum {R_ESP,R_EAX,R_EBX,R_ECX,R_EDX,R_EDI,R_EBP,R_ESI};
typedef struct {uint32_t regs[8];} CPUX86State;
enum {QEMU_CLOCK_HOST,QEMU_CLOCK_VIRTUAL};
static uint32_t test_handle=0x2c0;
static void *env_cpu(CPUX86State *env){return env;}
static int cpu_memory_rw_debug(void *cpu,uint32_t address,uint8_t *bytes,unsigned count,bool write)
{
 (void)cpu;assert(count==4&&!write);uint32_t value=0;
 switch(address){case 0x1000:value=0x26741a;break;case 0x1004:value=test_handle;break;
 case 0x1010:value=0x1103e0;break;case 0x1014:value=0x2000;break;
 case 0x101c:value=512;break;case 0xffdff124:value=0xc1008c20;break;}
 memcpy(bytes,&value,4);return 0;
}
static uint32_t ldl_le_p(const uint8_t *p){uint32_t v;memcpy(&v,p,4);return v;}
static int64_t qemu_clock_get_ns(int clock){(void)clock;static int64_t tick;return ++tick;}
#include "actual-identity-fragment.c"
static void observe(CPUX86State *env,unsigned pc)
{
 unsigned old_count=fid_count,old_active=px_active;
 forza_prefix_identity_before();forza_identity_profile(env,pc);
 forza_prefix_identity_after(old_count,old_active);
}
int main(void)
{
 setenv("XEMU_FORZA_PREFIX","1",1);setenv("XEMU_FORZA_IDENTITY_OUTPUT","/dev/null",1);
 setenv("XEMU_FORZA_PREFIX_OUTPUT","/dev/null",1);
 CPUX86State env={0};env.regs[R_ESP]=0x1000;
 unsigned id=forza_prefix_allocate(0x84001000,0,0,0);
 for(unsigned i=0;i<2;i++)forza_prefix_instruction(id,0x84001000+i,0);
 forza_prefix_finish(id,2);
 observe(&env,0x8404cec4);assert(fid_count==0&&px_admitted==0); /* warmup */
 test_handle=0x42c;
 for(unsigned i=0;i<64;i++){
  px_tb_enter(id,PX_OWNED);px_progress[0]=id;px_progress[1]=0;px_progress[2]=0;px_progress[4]=0x84001000;px_progress[5]=PX_OWNED;
  env.regs[R_ESP]=0x1000;observe(&env,0x8404cec4);
  assert(fid_generation==i+1&&px_admitted==i+1&&px_active==1);
  px_progress[1]=1;
  if(i==63){
   /* Admission is sealed while the last admitted API remains open. */
   observe(&env,0x8404cec4);assert(fid_generation==64&&px_active==1&&!fid_reentry);
  }
  env.regs[R_ESP]=0x1024;observe(&env,0x26741a);assert(px_returned==i+1&&px_active==0);
 }
 unsigned before=fid_count;env.regs[R_ESP]=0x1000;observe(&env,0x8404cec4);
 assert(fid_count==before&&fid_generation==64&&px_admitted==64&&px_returned==64);
 /* Callback observations remain enabled after admission closes. */
 observe(&env,0x1103e0);assert(fid_count==before+1&&fid_events[fid_count-1].kind==FID_CALLBACK);
 assert(!px_invalid&&!px_overflow&&!px_thread_mismatch);
 return 0;
}
