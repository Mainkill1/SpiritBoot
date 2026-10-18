/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PX_DESC_CAP 128u
#define PX_INSN_CAP 2048u
#define PX_ROW_CAP 32u
#include "recorder.c"
#define FID_THREADS 16
#define FID_BEGIN 1
#define FID_RETURN 2
typedef struct {uint32_t thread,kind,flags;} FidEvent;
typedef struct {uint32_t thread,api;} FidCall;
typedef struct {uint32_t thread,fail;} CPUX86State;
static FidEvent fid_events[256];
static FidCall fid_calls[16];
static uint32_t fid_count,fid_reentry;
static uint32_t fid_read(CPUX86State *env,FidEvent *event,uint32_t address) {
 assert(address==0xffdff124);event->flags=env->fail;return env->thread;
}
#include "integration.c"
static void tb(void){
 unsigned id=px_allocate(0x84001000,0,0,0);
 for(unsigned i=0;i<8;i++)px_instruction(id,0x84001000+i,0);
 px_finish(id,8);px_tb_enter(id,PX_OWNED);px_progress[0]=id;px_progress[1]=0;px_progress[2]=0;px_progress[4]=px_desc[id].pc;
}
static void event(unsigned kind,unsigned thread,unsigned api) {
 unsigned old_count=fid_count,old_active=px_active;
 forza_prefix_identity_before();
 fid_events[fid_count++]=(FidEvent){thread,kind,0};
 fid_calls[0]=(FidCall){thread,api};
 forza_prefix_identity_after(old_count,old_active);
}
int main(int argc,char **argv) {
 assert(argc==2);tb();
 if(!strcmp(argv[1],"thread_switch")) {
  event(FID_BEGIN,100,1);assert(px_active==1&&px_api==1&&px_thread==100);
  px_progress[1]=2;CPUX86State env={200,0};helper_forza_prefix_switch(&env);
  assert(px_api==0&&px_active==1);px_progress[1]=4;env.thread=100;helper_forza_prefix_switch(&env);
  assert(px_api==1);px_progress[1]=8;event(FID_RETURN,100,0);
  assert(!px_thread_mismatch&&!px_active&&px_row_count==2);
 }else if(!strcmp(argv[1],"dpc_same_thread")) {
  event(FID_BEGIN,100,1);px_progress[1]=4;
  unsigned old_count=fid_count;forza_prefix_identity_before();
  fid_events[fid_count++]=(FidEvent){100,3,0};forza_prefix_identity_after(old_count,1);
  px_progress[1]=8;event(FID_RETURN,100,0);assert(px_row_count==2&&!px_thread_mismatch);
 }else if(!strcmp(argv[1],"mismatch")) {
  event(FID_BEGIN,100,1);px_progress[1]=2;event(3,200,1);assert(px_thread_mismatch==1&&px_thread==100);
 }else if(!strcmp(argv[1],"failed_switch_read")) {
  event(FID_BEGIN,100,1);CPUX86State env={0,1};helper_forza_prefix_switch(&env);
  assert(px_thread_mismatch&&px_thread==0&&px_api==0);
 }else if(!strcmp(argv[1],"inactive_reanchor")) {
  event(FID_BEGIN,100,1);px_progress[1]=2;event(FID_RETURN,100,0);
  px_progress[1]=4;event(FID_BEGIN,200,2);assert(px_thread==200&&px_api==2&&!px_thread_mismatch);
 }else if(!strcmp(argv[1],"admission")) {
  assert(!forza_prefix_admission_allowed(0x2c0)&&forza_prefix_admission_allowed(0x42c));
  for(unsigned i=0;i<64;i++){
   assert(forza_prefix_admission_allowed(0x42c));
   event(FID_BEGIN,100,i+1);px_progress[1]=1;
   if(i<63){event(FID_RETURN,100,0);tb();}
  }
  assert(px_admitted==64&&px_returned==63&&!forza_prefix_admission_allowed(0x42c));
  event(FID_RETURN,100,0);assert(px_returned==64&&px_active==0&&!px_api);
 }else if(!strcmp(argv[1],"slots")) {
  assert(forza_prefix_slot(0)==&px_progress[0]&&forza_prefix_slot(3)==&px_active);
  unsigned id=forza_prefix_allocate(0x84002000,1,2,3);forza_prefix_instruction(id,0x84002000,0);forza_prefix_finish(id,1);
  helper_forza_prefix_tb(NULL,id,PX_OWNED);
 }else assert(0);
 return 0;
}
