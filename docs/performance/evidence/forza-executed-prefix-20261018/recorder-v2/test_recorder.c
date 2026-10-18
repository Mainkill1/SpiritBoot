/* SPDX-License-Identifier: MIT */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define PX_DESC_CAP 32u
#define PX_INSN_CAP 128u
#define PX_ROW_CAP 32u
#include "recorder.c"
static unsigned desc(unsigned pc,unsigned n,unsigned rep) {
 unsigned id=px_allocate(pc,0,0,0);
 for(unsigned i=0;i<n;i++)px_instruction(id,pc+i,i==rep);
 px_finish(id,n);return id;
}
static void enter(unsigned id) {
 px_tb_enter(id,PX_OWNED);px_progress[0]=id;px_progress[1]=0;px_progress[2]=0;px_progress[4]=px_desc[id].pc;
}
static void begun(unsigned n){px_progress[1]=n;}
static PxRow *row(unsigned api,unsigned first,unsigned last) {
 for(unsigned i=0;i<PX_ROW_CAP;i++)if(px_rows[i].api==api&&px_rows[i].first==first&&px_rows[i].last==last)return &px_rows[i];
 return NULL;
}
int main(int argc,char **argv) {
 assert(argc==2);assert(px_active==0);
 if(!strcmp(argv[1],"partial")) {
  unsigned a=desc(0x84001000,6,99);enter(a);begun(2);
  px_scope(1,10);begun(4);px_scope(0,11);begun(6);px_flush();
  assert(px_row_count==1&&row(1,3,4)->executions==1);
 } else if(!strcmp(argv[1],"fault")) {
  unsigned a=desc(0x84001000,6,99),b=desc(0x84002000,2,99);
  enter(a);px_scope(1,1);begun(3);enter(b);begun(2);px_scope(0,2);
  assert(row(1,1,3)&&row(1,1,2)&&px_row_count==2);
 } else if(!strcmp(argv[1],"rep")) {
  unsigned a=desc(0x84001000,3,1);enter(a);px_scope(1,1);
  begun(2);px_progress[2]=17;px_flush();
  assert(row(1,1,2)->rep_iterations==17);
  px_scope(0,2);assert(px_row_count==1);
 } else if(!strcmp(argv[1],"zero_rep")) {
  unsigned a=desc(0x84001000,1,0);enter(a);px_scope(1,1);begun(1);px_scope(0,2);
  assert(row(1,1,1)->rep_iterations==0);
 } else if(!strcmp(argv[1],"switch")) {
  unsigned a=desc(0x84001000,6,99);enter(a);px_scope(1,1);begun(2);
  px_scope(0,1);begun(4);px_scope(1,1);begun(6);px_scope(0,2);
  assert(row(1,1,2)&&row(1,5,6)&&px_row_count==2);
 } else if(!strcmp(argv[1],"same_pc")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,5);
  unsigned b=desc(0x84001000,2,99);assert(a!=b&&px_desc[b].born_api==1&&px_desc[b].born_seq==5);
  begun(1);enter(b);begun(2);px_scope(0,6);assert(px_row_count==2);
 } else if(!strcmp(argv[1],"exit_before_entry")) {
  unsigned a=desc(0x84001000,3,99);enter(a);px_scope(1,1);px_flush();
  assert(!px_row_count&&!px_invalid);
 } else if(!strcmp(argv[1],"aggregate")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,1);begun(2);
  enter(a);begun(2);px_scope(0,2);assert(px_row_count==1&&row(1,1,2)->executions==2);
 } else if(!strcmp(argv[1],"alias")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,1);begun(1);
  px_progress[4]=0x85001000;px_flush();assert(px_invalid);
 } else if(!strcmp(argv[1],"invalid")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,1);begun(3);px_flush();assert(px_invalid);
 } else if(!strcmp(argv[1],"unknown")) {
  px_tb_enter(999,PX_OWNED);assert(px_invalid);
 } else if(!strcmp(argv[1],"desc_overflow")) {
  for(unsigned i=0;i<PX_DESC_CAP+2;i++){desc(0x84001000+i,1,99);}assert(px_overflow);
 } else if(!strcmp(argv[1],"insn_overflow")) {
  desc(0x84001000,129,99);assert(px_overflow);
 } else if(!strcmp(argv[1],"row_overflow")) {
  unsigned a=desc(0x84001000,1,99);enter(a);
  for(unsigned i=0;i<PX_ROW_CAP+2;i++){px_scope(i+1,i+1);begun(1);px_scope(0,i+2);enter(a);}assert(px_overflow);
 } else if(!strcmp(argv[1],"decode_rollback")) {
  unsigned a=px_allocate(0x84001000,0,0,0);px_instruction(a,0x84001000,0);
  /* A decode rollback appends no metadata. */
  px_finish(a,1);assert(px_desc[a].count==1&&!px_invalid);
 } else if(!strcmp(argv[1],"wrong_count")) {
  unsigned a=px_allocate(0x84001000,0,0,0);px_instruction(a,0x84001000,0);px_finish(a,2);assert(px_invalid);
 } else if(!strcmp(argv[1],"excluded")) {
  assert(px_allocate(0x00400000,0,0,0)==0&&px_desc_count==0);
  px_tb_enter(0,PX_EXCLUDED);px_progress[0]=0;px_progress[4]=0x00400000;px_progress[5]=PX_EXCLUDED;
  px_scope(1,1);begun(3);px_progress[2]=4;px_scope(0,2);
  assert(px_excluded_count==1&&!px_row_count&&!px_invalid);
 } else if(!strcmp(argv[1],"excluded_transition")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,1);begun(2);
  px_tb_enter(0,PX_EXCLUDED);px_progress[0]=0;px_progress[1]=0;px_progress[2]=0;px_progress[4]=0x00400000;px_progress[5]=PX_EXCLUDED;
  begun(4);px_tb_enter(a,PX_OWNED);px_progress[0]=a;px_progress[1]=0;px_progress[2]=0;px_progress[4]=px_desc[a].pc;px_progress[5]=PX_OWNED;
  begun(2);px_scope(0,2);assert(px_excluded_count==1&&row(1,1,2)->executions==2&&!px_invalid);
 } else if(!strcmp(argv[1],"excluded_alias")) {
  px_tb_enter(0,PX_EXCLUDED);px_progress[0]=0;px_progress[4]=0x84001000;px_progress[5]=PX_EXCLUDED;
  px_scope(1,1);begun(1);px_flush();assert(px_reason[PX_I_EXCLUDED_ALIAS]==1);
 } else if(!strcmp(argv[1],"outside_instruction")) {
  unsigned a=px_allocate(0x840553ff,0,0,0);px_instruction(a,0x84055400,0);assert(px_reason[PX_I_OUTSIDE]);
 } else if(!strcmp(argv[1],"contiguity")) {
  unsigned a=px_allocate(0x84001000,0,0,0),b=px_allocate(0x84002000,0,0,0);
  px_instruction(b,0x84002000,0);px_instruction(a,0x84001000,0);assert(px_reason[PX_I_CONTIGUITY]);
 } else if(!strcmp(argv[1],"bad_instruction")) {
  px_instruction(99,0x84001000,0);assert(px_reason[PX_I_INSTRUCTION]);
 } else if(!strcmp(argv[1],"bad_segment")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,1);begun(1);px_segment_tb=0;px_flush();assert(px_reason[PX_I_SEGMENT]);
 } else if(!strcmp(argv[1],"unfinished")) {
  unsigned a=desc(0x84001000,2,99);enter(a);px_scope(1,1);begun(1);px_desc[a].finished=0;px_flush();assert(px_reason[PX_I_UNFINISHED]);
 } else if(!strcmp(argv[1],"rep_regression")) {
  unsigned a=desc(0x84001000,2,0);enter(a);px_scope(1,1);begun(1);px_rep_base=1;px_flush();assert(px_reason[PX_I_REP]);
 } else if(!strcmp(argv[1],"empty_rep")) {
  unsigned a=desc(0x84001000,2,0);enter(a);px_scope(1,1);px_progress[2]=1;px_flush();assert(px_reason[PX_I_EMPTY_REP]);
 } else if(!strcmp(argv[1],"bad_type")) {
  unsigned a=desc(0x84001000,2,0);enter(a);px_scope(1,1);px_progress[5]=2;px_flush();assert(px_reason[PX_I_TYPE]);
 } else if(!strcmp(argv[1],"unknown_flush")) {
  unsigned a=desc(0x84001000,2,0);enter(a);px_scope(1,1);px_progress[0]=px_segment_tb=999;
  px_flush();assert(px_reason[PX_I_UNKNOWN]);
 } else if(!strcmp(argv[1],"unfinished_output")) {
  unsigned a=desc(0x84001000,2,0);px_desc[a].used=1;px_desc[a].finished=0;
  FILE *f=tmpfile();assert(f);px_write(f,0,0,0);fclose(f);assert(px_reason[PX_I_OUTPUT]);
 } else if(!strcmp(argv[1],"bounded_samples")) {
  for(unsigned i=0;i<100;i++)px_fail(PX_I_ALIAS);
  assert(px_bad_count==2&&px_reason[PX_I_ALIAS]==100);
 } else if(!strcmp(argv[1],"output")) {
  unsigned a=desc(0x84001000,2,1);enter(a);px_scope(1,1);begun(2);px_progress[2]=7;px_scope(0,2);
  px_admitted=px_returned=1;px_write(stdout,0,0,0);
 } else assert(0);
 return 0;
}
