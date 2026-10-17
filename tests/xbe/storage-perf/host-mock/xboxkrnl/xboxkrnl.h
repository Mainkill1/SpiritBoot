/* Synthetic host API surface for actual owned fixture fault tests, not firmware. */
#pragma once
#include <stdint.h>
#include <stddef.h>
typedef uint8_t UCHAR;typedef uint32_t ULONG;typedef uint16_t USHORT;typedef int32_t NTSTATUS;typedef unsigned long long ULONGLONG;typedef void *PVOID;typedef char *PCHAR;typedef void *HANDLE;
typedef long long LONGLONG;
typedef ULONG ACCESS_MASK;
typedef union {long long QuadPart;} LARGE_INTEGER;
typedef struct {USHORT Length,MaximumLength;PCHAR Buffer;} ANSI_STRING;
typedef struct {ANSI_STRING *ObjectName;ULONG Attributes;} OBJECT_ATTRIBUTES;
typedef struct {NTSTATUS Status;ULONG Information;} IO_STATUS_BLOCK;
typedef struct {ULONG Length,AvailablePages;} MM_STATISTICS;
typedef struct {LARGE_INTEGER AllocationSize,EndOfFile;ULONG NumberOfLinks;UCHAR DeletePending,Directory;} FILE_STANDARD_INFORMATION;
typedef union {PVOID Buffer;ULONGLONG Alignment;} FILE_SEGMENT_ELEMENT;
#define OBJ_CASE_INSENSITIVE 64
#define GENERIC_READ 1
#define GENERIC_WRITE 2
#define SYNCHRONIZE 4
#define FILE_ATTRIBUTE_NORMAL 0
#define FILE_SHARE_READ 1
#define FILE_SHARE_WRITE 2
#define FILE_OPEN 1
#define FILE_SUPERSEDE 0
#define FILE_SYNCHRONOUS_IO_NONALERT 1
#define FILE_NON_DIRECTORY_FILE 2
#define FILE_NO_INTERMEDIATE_BUFFERING 4
#define STATUS_UNSUCCESSFUL ((NTSTATUS)0xc0000001)
#define KernelMode 0
#define FALSE 0
#define FileStandardInformation 5
#define METHOD_BUFFERED 0
#define FILE_ANY_ACCESS 0
#define FILE_READ_ACCESS 1
#define CTL_CODE(device,function,method,access) (((device)<<16)|((access)<<14)|((function)<<2)|(method))
#define IOCTL_DISK_GET_DRIVE_GEOMETRY CTL_CODE(7,0,METHOD_BUFFERED,FILE_ANY_ACCESS)
#define IOCTL_DISK_GET_PARTITION_INFO CTL_CODE(7,1,METHOD_BUFFERED,FILE_READ_ACCESS)
void *MmAllocateContiguousMemory(ULONG);void MmFreeContiguousMemory(PVOID);NTSTATUS MmQueryStatistics(MM_STATISTICS *);
NTSTATUS NtCreateFile(HANDLE *,ULONG,OBJECT_ATTRIBUTES *,IO_STATUS_BLOCK *,PVOID,ULONG,ULONG,ULONG,ULONG);
NTSTATUS NtReadFile(HANDLE,PVOID,PVOID,PVOID,IO_STATUS_BLOCK *,PVOID,ULONG,LARGE_INTEGER *);
NTSTATUS NtWriteFile(HANDLE,PVOID,PVOID,PVOID,IO_STATUS_BLOCK *,PVOID,ULONG,LARGE_INTEGER *);
NTSTATUS NtReadFileScatter(HANDLE,PVOID,PVOID,PVOID,IO_STATUS_BLOCK *,FILE_SEGMENT_ELEMENT *,ULONG,LARGE_INTEGER *);
NTSTATUS NtFlushBuffersFile(HANDLE,IO_STATUS_BLOCK *);NTSTATUS NtClose(HANDLE);
NTSTATUS NtQueryInformationFile(HANDLE,IO_STATUS_BLOCK *,PVOID,ULONG,ULONG);
NTSTATUS IoDismountVolumeByName(ANSI_STRING *);
NTSTATUS NtDeviceIoControlFile(HANDLE,PVOID,PVOID,PVOID,IO_STATUS_BLOCK *,ULONG,PVOID,ULONG,PVOID,ULONG);
ULONGLONG KeQueryPerformanceCounter(void);ULONGLONG KeQueryPerformanceFrequency(void);NTSTATUS KeDelayExecutionThread(int,int,LARGE_INTEGER *);
void HalWriteSMBusValue(int,int,int,int);
