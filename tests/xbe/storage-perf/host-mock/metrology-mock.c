/* Synthetic QPC advances independently of the host's real RDTSC domain. */
#include <xboxkrnl/xboxkrnl.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include "tap.h"
static ULONGLONG qpc;
ULONGLONG KeQueryPerformanceFrequency(void){return 1000000;}
ULONGLONG KeQueryPerformanceCounter(void){return qpc++;}
NTSTATUS KeDelayExecutionThread(int mode,int alert,LARGE_INTEGER *delay){
    (void)mode;(void)alert;if(delay->QuadPart<0)qpc+=(ULONGLONG)(-delay->QuadPart)/10;return 0;
}
void HalWriteSMBusValue(int a,int b,int c,int d){(void)a;(void)b;(void)c;(void)d;exit(0);}
void tap_version(unsigned v){(void)v;}void tap_plan(unsigned n){(void)n;}
void tap_ok(unsigned n,const char *text){(void)n;(void)text;}
void tap_not_ok(unsigned n,const char *text){(void)n;(void)text;}
void tap_puts(const char *text){fputs(text,stdout);}void tap_drain(void){}
void tap_comment(const char *fmt,...){
 char text[512];va_list args;va_start(args,fmt);vsnprintf(text,sizeof(text),fmt,args);va_end(args);puts(text);
 unsigned index;
 if(sscanf(text,"STORAGE-CAUSAL-MARKER index=%u",&index)==1){
  unsigned a,d;__asm__ __volatile__("rdtsc":"=a"(a),"=d"(d)::"memory");
  printf("MOCK-CAUSAL-EMISSION index=%u qpc=%llu rdtsc=%llu\n",index,qpc,((ULONGLONG)d<<32)|a);
 }
}
