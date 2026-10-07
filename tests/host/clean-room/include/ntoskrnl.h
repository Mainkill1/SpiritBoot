/* SPDX-License-Identifier: GPL-2.0-or-later
 * Minimal NT host shim: only persistence's pure bookkeeping is exercised. */
#pragma once
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <stdbool.h>
typedef uint8_t UCHAR, BOOLEAN, KIRQL;
typedef uint16_t USHORT;
typedef uint32_t ULONG, PFN_NUMBER, PFN_COUNT;
typedef int32_t LONG, NTSTATUS;
typedef uintptr_t ULONG_PTR;
typedef size_t SIZE_T, *PSIZE_T;
typedef void VOID, *PVOID;
typedef UCHAR *PUCHAR;
typedef ULONG *PULONG;
#define IN
#define OUT
#define NTAPI
#define TRUE 1
#define FALSE 0
#define PAGE_SIZE 4096UL
#define PAGE_SHIFT 12
#define C_ASSERT(c) _Static_assert(sizeof(void *) != 4 || (c), #c)
#define FIELD_OFFSET(t,f) offsetof(t,f)
#define CONTAINING_RECORD(p,t,f) ((t *)((char *)(p)-offsetof(t,f)))
#define RtlCopyMemory memcpy
#define RtlZeroMemory(p,n) memset(p,0,n)
#define KeMemoryBarrier() __sync_synchronize()
typedef struct _LIST_ENTRY { struct _LIST_ENTRY *Flink, *Blink; } LIST_ENTRY, *PLIST_ENTRY;
typedef enum { LoaderFree, LoaderFirmwarePermanent, LoaderMemoryData } TYPE_OF_MEMORY;
typedef struct { LIST_ENTRY ListEntry; TYPE_OF_MEMORY MemoryType; PFN_NUMBER BasePage, PageCount; } MEMORY_ALLOCATION_DESCRIPTOR, *PMEMORY_ALLOCATION_DESCRIPTOR;
typedef struct { LIST_ENTRY MemoryDescriptorListHead; } LOADER_PARAMETER_BLOCK, *PLOADER_PARAMETER_BLOCK;
extern UCHAR __ImageBase[];

#ifdef HOST_SHUTDOWN_SCHEDULING_HOOKS
VOID HostSchedulingHook(ULONG Phase);
#define HOST_BOUNDARY(phase) HostSchedulingHook(phase)
#else
#define HOST_BOUNDARY(phase) ((void)0)
#endif
typedef ULONG KSPIN_LOCK;
static inline void KeAcquireSpinLock(KSPIN_LOCK *l, KIRQL *i) { (void)l; *i=0; }
static inline void KeReleaseSpinLock(KSPIN_LOCK *l, KIRQL i) { (void)l; (void)i; HOST_BOUNDARY(1); }
static inline void InitializeListHead(LIST_ENTRY *h) { h->Flink=h->Blink=h; }
static inline bool IsListEmpty(LIST_ENTRY *h) { return h->Flink==h; }
static inline void RemoveEntryList(LIST_ENTRY *e) { e->Blink->Flink=e->Flink; e->Flink->Blink=e->Blink; }
static inline LIST_ENTRY *RemoveHeadList(LIST_ENTRY *h) { LIST_ENTRY *e=h->Flink; RemoveEntryList(e); return e; }
static inline void InsertTailList(LIST_ENTRY *h, LIST_ENTRY *e) { e->Flink=h; e->Blink=h->Blink; h->Blink->Flink=e; h->Blink=e; }

/* Model the kernel-owned SEH boundary for source-level callback tests. Guest
 * validation uses native PSEH/RTL and the public noreturn declaration. */
#include <setjmp.h>
#include <stdlib.h>
#define DECLSPEC_NORETURN __attribute__((noreturn))
typedef PVOID PETHREAD;
typedef struct { BOOLEAN Signaled; } KEVENT;
#define NotificationEvent 0
#define Executive 0
#define KernelMode 0
#define EXCEPTION_EXECUTE_HANDLER 1
#define EXCEPTION_CONTINUE_SEARCH 0
static PETHREAD HostCurrentThread = (PVOID)1;
static LONG HostCriticalDepth[3];
static inline ULONG HostThreadIndex(void) { return (ULONG)(ULONG_PTR)HostCurrentThread; }
static inline VOID KeEnterCriticalRegion(void) { ++HostCriticalDepth[HostThreadIndex()]; }
static inline VOID KeLeaveCriticalRegion(void) { --HostCriticalDepth[HostThreadIndex()]; HOST_BOUNDARY(4); }
static inline PETHREAD PsGetCurrentThread(void) { return HostCurrentThread; }
static inline VOID KeInitializeEvent(KEVENT *e,ULONG kind,BOOLEAN state)
{ (void)kind;e->Signaled=state; }
typedef struct _HOST_SEH { jmp_buf Jump; struct _HOST_SEH *Previous; NTSTATUS Code; } HOST_SEH;
static HOST_SEH *HostExceptionFrame;
static ULONG HostUnwinds;
static DECLSPEC_NORETURN inline VOID RtlRaiseStatus(NTSTATUS code)
{ if(!HostExceptionFrame) abort();HostExceptionFrame->Code=code;++HostUnwinds;
  longjmp(HostExceptionFrame->Jump,1); }
#define _SEH2_TRY do { HOST_SEH host_frame; BOOLEAN host_handled=FALSE; \
 host_frame.Previous=HostExceptionFrame; HOST_BOUNDARY(2); HostExceptionFrame=&host_frame; \
 int host_exception=setjmp(host_frame.Jump); if(host_exception==0)
#define _SEH2_EXCEPT(filter) else if((host_handled=((filter)==EXCEPTION_EXECUTE_HANDLER)))
#define _SEH2_FINALLY ;
#define _SEH2_GetExceptionCode() host_frame.Code
#define _SEH2_END HostExceptionFrame=host_frame.Previous; HOST_BOUNDARY(3); \
 if(host_exception&&!host_handled) RtlRaiseStatus(host_frame.Code); } while(0)
#ifdef HOST_SHUTDOWN_WAIT_STUB
NTSTATUS KeWaitForSingleObject(PVOID,ULONG,ULONG,BOOLEAN,PVOID);
#else
static inline NTSTATUS KeWaitForSingleObject(PVOID p,ULONG reason,ULONG mode,BOOLEAN alert,PVOID timeout)
{ (void)p;(void)reason;(void)mode;(void)alert;(void)timeout;abort(); }
#endif
