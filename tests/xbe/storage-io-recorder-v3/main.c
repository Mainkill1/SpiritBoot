/* SPDX-License-Identifier: GPL-2.0-or-later
 * Select one existing public FATX request-metadata case from the runner's
 * private prepared configuration. No network or kernel-private entry points.
 */
#include <xboxkrnl/xboxkrnl.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include "tap.h"
int recorder_execute(ULONG dataset,ULONG depth,ULONG pressure_target,bool warm);
static char configuration[131073];
static bool string_value(const char *start,const char *key,char *out,ULONG size){
 char token[80];snprintf(token,sizeof(token),"\"%s\"",key);const char *p=strstr(start,token);if(!p)return false;p=strchr(p+strlen(token),':');if(!p)return false;
 ++p;while(*p==' '||*p=='\r'||*p=='\n'||*p=='\t')++p;if(*p++!='"')return false;
 ULONG n=0;while(*p&&*p!='"'){if(n+1>=size||*p=='\\')return false;out[n++]=*p++;}if(*p!='"')return false;out[n]=0;return true;
}
static bool select_case(ULONG *dataset,ULONG *depth,ULONG *pressure,bool *warm,char *selected,ULONG capacity){
 const char *path="\\Device\\Harddisk0\\Partition1\\xemu_perf_tests\\xemu_perf_tests_config.json";ANSI_STRING name={(USHORT)strlen(path),(USHORT)(strlen(path)+1),(PCHAR)path};OBJECT_ATTRIBUTES a={0};IO_STATUS_BLOCK io;memset(&io,0x5a,sizeof(io));HANDLE h=NULL;a.ObjectName=&name;a.Attributes=OBJ_CASE_INSENSITIVE;
 NTSTATUS s=NtCreateFile(&h,GENERIC_READ|SYNCHRONIZE,&a,&io,NULL,0,FILE_SHARE_READ,FILE_OPEN,FILE_SYNCHRONOUS_IO_NONALERT|FILE_NON_DIRECTORY_FILE);if(s!=0||io.Status!=0)return false;
 LARGE_INTEGER at={0};memset(&io,0x5a,sizeof(io));s=NtReadFile(h,NULL,NULL,NULL,&io,configuration,sizeof(configuration)-1,&at);NTSTATUS close=NtClose(h);if(s!=0||io.Status!=0||close!=0||io.Information==0||io.Information>=sizeof(configuration))return false;configuration[io.Information]=0;
 const char *plan=strstr(configuration,"\"resolved_plan\"");const char *tests=plan?strstr(plan,"\"tests\""):NULL;if(!tests||!string_value(tests,"id",selected,capacity))return false;
 const char *first=strstr(tests,"\"id\"");if(!first||strstr(first+4,"\"id\""))return false;
 unsigned d,q,p;char cache[16],canonical[96];int end=0;
 if(sscanf(selected,"fatx-d%u-q%u-p%u-synthetic.%15s%n",&d,&q,&p,cache,&end)!=4||selected[end]!=0)return false;
 if(d>1||(q!=1&&q!=4&&q!=12)||(p!=0&&p!=900)||(strcmp(cache,"warm")&&strcmp(cache,"cold-ish")))return false;
 snprintf(canonical,sizeof(canonical),"fatx-d%u-q%u-p%u-synthetic.%s",d,q,p,cache);if(strcmp(canonical,selected))return false;
 *dataset=d;*depth=q;*pressure=p;*warm=!strcmp(cache,"warm");return true;
}
static __attribute__((noreturn)) void finish(void){tap_drain();LARGE_INTEGER delay={.QuadPart=-5000000};KeDelayExecutionThread(KernelMode,FALSE,&delay);HalWriteSMBusValue(0x20,0x02,FALSE,0x80);for(;;)__asm__ __volatile__("hlt");}
int main(void){
 tap_version(13);tap_plan(1);ULONG dataset,depth,pressure;bool warm;char selected[96];
 if(!select_case(&dataset,&depth,&pressure,&warm,selected,sizeof(selected))){tap_comment("STORAGE-IO-V3-ERROR stage=case-selection");tap_not_ok(1,"generation3 private configuration selection");finish();}
 tap_comment("STORAGE-IO-V3-SELECTION id=%s protocol_version=3",selected);
 int failed=recorder_execute(dataset,depth,pressure,warm);
 if(failed)tap_not_ok(1,"generation3 public IO status and post-batch complete byte oracle");else tap_ok(1,"generation3 public IO status and post-batch complete byte oracle");finish();
}
