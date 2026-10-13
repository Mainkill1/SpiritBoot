/* SPDX-License-Identifier: GPL-2.0-or-later */
#include <windows.h>
#include <xboxkrnl/xboxkrnl.h>
#include <string.h>
#include "regression.h"

static unsigned char payload[512], actual[512];
static NTSTATUS open_path(const char *path, ACCESS_MASK access, ULONG disposition,
                          ULONG options, HANDLE *handle)
{
    ANSI_STRING name; OBJECT_ATTRIBUTES oa; IO_STATUS_BLOCK io;
    RtlInitAnsiString(&name,path);
    InitializeObjectAttributes(&oa,&name,OBJ_CASE_INSENSITIVE,NULL,NULL);
    return NtCreateFile(handle,access|SYNCHRONIZE,&oa,&io,NULL,
        FILE_ATTRIBUTE_NORMAL,FILE_SHARE_READ|FILE_SHARE_WRITE|FILE_SHARE_DELETE,
        disposition,options|FILE_SYNCHRONOUS_IO_NONALERT);
}
static void unchanged(HANDLE h, const FILE_FS_SIZE_INFORMATION *before)
{
    IO_STATUS_BLOCK io; FILE_NETWORK_OPEN_INFORMATION info; FILE_FS_SIZE_INFORMATION fs;
    LARGE_INTEGER off={.QuadPart=0}; NTSTATUS s;
    memset(&info,0x5a,sizeof(info));
    s=NtQueryInformationFile(h,&io,&info,sizeof(info),FileNetworkOpenInformation);
    tap_comment("EOF after status=%08lx info=%lu eof=%08lx:%08lx allocation=%08lx:%08lx",(ULONG)s,io.Information,(ULONG)info.EndOfFile.HighPart,info.EndOfFile.LowPart,(ULONG)info.AllocationSize.HighPart,info.AllocationSize.LowPart);
    regression_check(NT_SUCCESS(s)&&info.EndOfFile.QuadPart==sizeof(payload),"failed resize preserves EOF");
    memset(actual,0,sizeof(actual));
    s=NtReadFile(h,NULL,NULL,NULL,&io,actual,sizeof(actual),&off);
    regression_check(NT_SUCCESS(s)&&io.Information==sizeof(actual)&&!memcmp(actual,payload,sizeof(actual)),"failed resize preserves bytes");
    s=NtQueryVolumeInformationFile(h,&io,&fs,sizeof(fs),FileFsSizeInformation);
    regression_check(NT_SUCCESS(s)&&fs.AvailableAllocationUnits.QuadPart==before->AvailableAllocationUnits.QuadPart,"failed resize preserves free clusters");
}
static void resize_case(HANDLE h, LONGLONG size, const char *name, int survey)
{
    FILE_END_OF_FILE_INFORMATION eof={.EndOfFile={.QuadPart=size}};
    FILE_FS_SIZE_INFORMATION before; FILE_NETWORK_OPEN_INFORMATION info; IO_STATUS_BLOCK io; NTSTATUS s;
    memset(&info,0x5a,sizeof(info));
    s=NtQueryInformationFile(h,&io,&info,sizeof(info),FileNetworkOpenInformation);
    tap_comment("EOF before %s status=%08lx info=%lu eof=%08lx:%08lx allocation=%08lx:%08lx",name,(ULONG)s,io.Information,(ULONG)info.EndOfFile.HighPart,info.EndOfFile.LowPart,(ULONG)info.AllocationSize.HighPart,info.AllocationSize.LowPart);
    regression_check(NT_SUCCESS(s)&&info.EndOfFile.QuadPart==sizeof(payload),"seed EOF is 512 bytes");
    s=NtQueryVolumeInformationFile(h,&io,&before,sizeof(before),FileFsSizeInformation);
    regression_require(NT_SUCCESS(s),"query pre-resize space");
    tap_comment("resize begin %s high=%08lx low=%08lx",name,(ULONG)eof.EndOfFile.HighPart,eof.EndOfFile.LowPart);
    tap_drain(); memset(&io,0x5a,sizeof(io));
    s=NtSetInformationFile(h,&io,&eof,sizeof(eof),FileEndOfFileInformation);
    tap_comment("resize result %s status=%08lx iosb=%08lx info=%lu",name,(ULONG)s,(ULONG)io.Status,io.Information);
    if(survey)regression_check(s==(NTSTATUS)0xc000000d,"negative file size returns INVALID_PARAMETER");
    else regression_check(s==(NTSTATUS)0xc000007f,"unrepresentable or unavailable file size returns DISK_FULL");
    unchanged(h,&before);
}
int main(void)
{
    HANDLE h=NULL, ro=NULL; IO_STATUS_BLOCK io; NTSTATUS s;
    const char *path="\\Device\\Harddisk0\\Partition1\\SpiritBootStorageContract.tmp";
    LARGE_INTEGER off={.QuadPart=0}; FILE_FS_SIZE_INFORMATION fs;
    regression_begin();
    for(unsigned i=0;i<sizeof(payload);i++)payload[i]=(unsigned char)(i*37+11);
    s=open_path("\\Device\\Harddisk0\\Partition1",GENERIC_READ,FILE_OPEN,0,&h);
    regression_require(NT_SUCCESS(s),"open readonly volume");
    memset(&io,0x5a,sizeof(io)); s=NtFlushBuffersFile(h,&io);
    tap_comment("flush readonly-volume status=%08lx iosb=%08lx info=%lu",(ULONG)s,(ULONG)io.Status,io.Information);
    regression_check(s==0&&io.Status==0,"readonly volume flush succeeds"); NtClose(h);
    s=open_path(path,GENERIC_READ|GENERIC_WRITE|DELETE,FILE_OVERWRITE_IF,FILE_NON_DIRECTORY_FILE,&h);
    regression_require(NT_SUCCESS(s),"create disposable data file");
    s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off);
    regression_require(NT_SUCCESS(s)&&io.Information==sizeof(payload),"seed exact payload");
    s=NtFlushBuffersFile(h,&io); regression_check(s==0,"writable file flush succeeds");
    s=open_path(path,GENERIC_READ,FILE_OPEN,FILE_NON_DIRECTORY_FILE,&ro);
    regression_require(NT_SUCCESS(s),"open readonly regular file");
    memset(&io,0x5a,sizeof(io)); s=NtFlushBuffersFile(ro,&io);
    tap_comment("flush readonly-file status=%08lx iosb=%08lx info=%lu",(ULONG)s,(ULONG)io.Status,io.Information);
    regression_check(s==0&&io.Status==0,"readonly regular file flush succeeds"); NtClose(ro);
    s=NtQueryVolumeInformationFile(h,&io,&fs,sizeof(fs),FileFsSizeInformation);
    regression_require(NT_SUCCESS(s),"query large partition space");
    tap_comment("large free units=%lu:%lu cluster=%lu",(ULONG)fs.AvailableAllocationUnits.HighPart,fs.AvailableAllocationUnits.LowPart,fs.SectorsPerAllocationUnit*fs.BytesPerSector);
    resize_case(h,0x100000000LL,"exact-4GiB",0);
    NtClose(h); s=open_path(path,GENERIC_READ|GENERIC_WRITE|DELETE,FILE_OVERWRITE_IF,FILE_NON_DIRECTORY_FILE,&h);
    regression_require(NT_SUCCESS(s),"recreate independent case file");
    s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off); regression_require(NT_SUCCESS(s),"seed independent case");
    resize_case(h,0x100000200LL,"4GiB-plus-512",0);
    NtClose(h); s=open_path(path,GENERIC_READ|GENERIC_WRITE|DELETE,FILE_OVERWRITE_IF,FILE_NON_DIRECTORY_FILE,&h);
    regression_require(NT_SUCCESS(s),"recreate independent case file");
    s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off); regression_require(NT_SUCCESS(s),"seed independent case");
    resize_case(h,((ULONGLONG)fs.AvailableAllocationUnits.QuadPart+16)*fs.SectorsPerAllocationUnit*fs.BytesPerSector,"beyond-free-large",0);
    /* LowPart equals the seeded EOF, so even a truncating implementation cannot
     * allocate gigabytes or destroy the payload during this signedness survey. */
    NtClose(h); s=open_path(path,GENERIC_READ|GENERIC_WRITE|DELETE,FILE_OVERWRITE_IF,FILE_NON_DIRECTORY_FILE,&h);
    regression_require(NT_SUCCESS(s),"recreate independent case file");
    s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off); regression_require(NT_SUCCESS(s),"seed independent case");
    resize_case(h,-0x100000000LL+512,"negative-lowpart-512",1);
    NtClose(h);
    s=open_path("\\Device\\Harddisk0\\Partition3\\SpiritBootStorageContract.tmp",GENERIC_READ|GENERIC_WRITE|DELETE,FILE_OVERWRITE_IF,FILE_NON_DIRECTORY_FILE,&h);
    regression_require(NT_SUCCESS(s),"create cache-partition data file");
    s=NtWriteFile(h,NULL,NULL,NULL,&io,payload,sizeof(payload),&off);
    regression_require(NT_SUCCESS(s)&&io.Information==sizeof(payload),"seed cache-partition payload");
    s=NtQueryVolumeInformationFile(h,&io,&fs,sizeof(fs),FileFsSizeInformation);
    regression_require(NT_SUCCESS(s),"query cache partition space");
    LONGLONG bytes=((ULONGLONG)fs.AvailableAllocationUnits.QuadPart+16)*fs.SectorsPerAllocationUnit*fs.BytesPerSector;
    regression_require(bytes>512&&bytes<0x100000000LL,"free-space case lies below file-size cap");
    resize_case(h,bytes,"beyond-free-small",0);
    NtClose(h); regression_finish();
}
