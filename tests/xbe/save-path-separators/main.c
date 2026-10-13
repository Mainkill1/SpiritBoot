/* SPDX-License-Identifier: GPL-2.0-or-later
 * Public file API replay of DOA's doubled save-path separator. Synthetic data only. */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <stdio.h>
#include <string.h>
#include "regression.h"
static unsigned char payload[11176], actual[11176];
static NTSTATUS open_file(const char *path, HANDLE root, unsigned api, ULONG disposition,
                          ULONG options, HANDLE *handle)
{
    ANSI_STRING name;
    OBJECT_ATTRIBUTES oa;
    IO_STATUS_BLOCK io={0};
    RtlInitAnsiString(&name,path);
    if(!root && path[0] && path[1]==':')root=(HANDLE)-3;
    InitializeObjectAttributes(&oa,&name,OBJ_CASE_INSENSITIVE,root,NULL);
    *handle=NULL;
    if(api==1) return NtOpenFile(handle,GENERIC_READ|GENERIC_WRITE|SYNCHRONIZE,&oa,&io,
        FILE_SHARE_READ|FILE_SHARE_WRITE,options);
    if(api==2) return IoCreateFile(handle,GENERIC_READ|GENERIC_WRITE|SYNCHRONIZE,&oa,&io,
        NULL,FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ|FILE_SHARE_WRITE,disposition,options,0);
    return NtCreateFile(handle,GENERIC_READ|GENERIC_WRITE|SYNCHRONIZE,&oa,&io,NULL,
        FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ|FILE_SHARE_WRITE,disposition,options);
}
int main(void)
{
    HANDLE dir=NULL,h=NULL;IO_STATUS_BLOCK io;NTSTATUS s;LARGE_INTEGER off={.QuadPart=0};
    const ULONG opts=FILE_SYNCHRONOUS_IO_NONALERT|FILE_NON_DIRECTORY_FILE;
    static const char *paths[]={
      "E:\\SpiritBootSavePathProbe\\doaxuser.dat",
      "E:\\SpiritBootSavePathProbe\\\\doaxuser.dat",
      "E:\\SpiritBootSavePathProbe\\\\\\doaxuser.dat",
      "E:\\\\SpiritBootSavePathProbe\\doaxuser.dat",
      "\\Device\\Harddisk0\\Partition1\\SpiritBootSavePathProbe\\\\doaxuser.dat"
    };
    regression_begin();
    {ANSI_STRING link,target;RtlInitAnsiString(&link,"\\??\\E:");RtlInitAnsiString(&target,"\\Device\\Harddisk0\\Partition1");
     s=IoCreateSymbolicLink(&link,&target);tap_comment("map E status=%08lx",(ULONG)s);}
    for(unsigned i=0;i<sizeof(payload);i++)payload[i]=(unsigned char)(i*37+11);
    s=open_file("E:\\SpiritBootSavePathProbe",NULL,0,FILE_OPEN_IF,
        FILE_DIRECTORY_FILE|FILE_SYNCHRONOUS_IO_NONALERT,&dir);
    tap_comment("directory status=%08lx",(ULONG)s);
    regression_require(NT_SUCCESS(s),"create isolated probe directory");
    for(unsigned a=0;a<3;a++)for(unsigned p=0;p<sizeof(paths)/sizeof(paths[0]);p++){
      s=open_file(paths[p],NULL,a,FILE_OPEN_IF,opts,&h);
      tap_comment("api=%u path=%u status=%08lx",a,p,(ULONG)s);
      regression_check((p==2||p==3)?s==(NTSTATUS)0xc0000033:NT_SUCCESS(s),"separator spelling matches reference status");
      if(!NT_SUCCESS(s))continue;
      if(a==0 && p==0){
        s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off);
        regression_check(NT_SUCCESS(s)&&io.Information==sizeof(payload),"write synthetic save payload");
        s=NtFlushBuffersFile(h,&io);regression_check(NT_SUCCESS(s),"flush synthetic save payload");
      }
      memset(actual,0,sizeof(actual));
      s=NtReadFile(h,NULL,NULL,NULL,&io,actual,sizeof(actual),&off);
      regression_check(NT_SUCCESS(s)&&io.Information==sizeof(actual)&&!memcmp(payload,actual,sizeof(actual)),
        "reopen alias reads exact saved bytes");
      NtClose(h);
    }
    for(unsigned a=0;a<3;a++){
      s=open_file("doaxuser.dat",dir,a,FILE_OPEN_IF,opts,&h);
      regression_check(NT_SUCCESS(s),"directory-relative control opens");if(NT_SUCCESS(s))NtClose(h);
    }
    /* The observed create, before any data exists under this name. */
    s=open_file("E:\\SpiritBootSavePathProbe\\\\newsave.dat",NULL,0,FILE_OPEN_IF,opts,&h);
    regression_check(NT_SUCCESS(s),"double separator creates a new save file");
    if(NT_SUCCESS(s)){
      s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off);
      regression_check(NT_SUCCESS(s)&&io.Information==sizeof(payload),"new save write succeeds");NtClose(h);
      s=open_file("E:\\SpiritBootSavePathProbe\\newsave.dat",NULL,1,FILE_OPEN,opts,&h);
      regression_check(NT_SUCCESS(s),"canonical spelling reopens newly created save");
      if(NT_SUCCESS(s)){
        memset(actual,0,sizeof(actual));s=NtReadFile(h,NULL,NULL,NULL,&io,actual,sizeof(actual),&off);
        regression_check(NT_SUCCESS(s)&&io.Information==sizeof(actual)&&!memcmp(payload,actual,sizeof(actual)),"new save survives close and reopen");NtClose(h);
      }
    }

    { static const char *extra[]={
      "E:\\SpiritBootSavePathProbe\\",
      "E:\\SpiritBootSavePathProbe\\\\",
      "E:\\SpiritBootSavePathProbe\\\\\\",
      "E:\\SpiritBootSavePathProbe\\doaxuser.dat\\",
      "E:\\SpiritBootSavePathProbe\\doaxuser.dat\\\\",
      "\\Device\\Harddisk0\\Partition1\\\\SpiritBootSavePathProbe\\doaxuser.dat",
      "E:\\SpiritBootSavePathProbe\\\\doaxuser.dat\\",
      "E:\\SpiritBootSavePathProbe\\\\doaxuser.dat\\\\"
      };
      for(unsigned i=0;i<sizeof(extra)/sizeof(extra[0]);i++){
       s=open_file(extra[i],NULL,0,FILE_OPEN,FILE_SYNCHRONOUS_IO_NONALERT,&h);
       tap_comment("survey=%u status=%08lx",i,(ULONG)s);if(NT_SUCCESS(s))NtClose(h);
      }
    }
    NtClose(dir);regression_finish();
}
