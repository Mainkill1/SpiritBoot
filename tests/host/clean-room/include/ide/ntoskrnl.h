/* SPDX-License-Identifier: GPL-2.0-or-later */
#pragma once
#include "../ntoskrnl.h"
#include <assert.h>
typedef char CHAR, *PCHAR;
typedef ULONG *PKSPIN_LOCK;
typedef enum { LevelSensitive, Latched } KINTERRUPT_MODE;
typedef struct _KINTERRUPT { BOOLEAN Connected; KIRQL Irql; ULONG Vector;
 BOOLEAN ShareVector; KINTERRUPT_MODE Mode; BOOLEAN Initialized; } KINTERRUPT, *PKINTERRUPT;
typedef BOOLEAN (*PKSERVICE_ROUTINE)(PKINTERRUPT, PVOID);
typedef BOOLEAN (*PKSYNCHRONIZE_ROUTINE)(PVOID);
typedef struct { ULONG unused; } DEVICE_OBJECT, *PDEVICE_OBJECT;
typedef struct { ULONG unused; } IRP, *PIRP;
typedef struct { int64_t QuadPart; } LARGE_INTEGER;
typedef struct _KDPC KDPC, *PKDPC;
typedef VOID (*PKDEFERRED_ROUTINE)(PKDPC, PVOID, PVOID, PVOID);
struct _KDPC { PKDEFERRED_ROUTINE Routine; PVOID Context; };
typedef struct { BOOLEAN Armed; } KTIMER;
typedef struct { BOOLEAN Busy; } KDEVICE_QUEUE;
typedef VOID (*PIO_TIMER_ROUTINE)(PDEVICE_OBJECT, PVOID);
#define __declspec(x)
#define NTKERNELAPI
#define _In_
#define _In_opt_
#define DISPATCH_LEVEL 2
#define HIGH_LEVEL 31
#define UNREFERENCED_PARAMETER(x) (void)(x)
#define min(a,b) ((a)<(b)?(a):(b))
static KIRQL current_irql;
static inline KIRQL KeGetCurrentIrql(void) { return current_irql; }
static inline void KeRaiseIrql(KIRQL level,KIRQL *old) { assert(level>=current_irql); *old=current_irql;current_irql=level; }
static inline void KeLowerIrql(KIRQL old) { assert(old<=current_irql); current_irql=old; }
static inline void KeInitializeDeviceQueue(KDEVICE_QUEUE *q) { q->Busy=FALSE; }
static inline void KeInitializeDpc(PKDPC d,PKDEFERRED_ROUTINE r,PVOID c) { d->Routine=r;d->Context=c; }
static inline void KeInitializeTimer(KTIMER *t) { t->Armed=FALSE; }
static inline void KeSetTimerEx(KTIMER *t,LARGE_INTEGER due,ULONG period,PKDPC d) { (void)due;(void)period;(void)d;t->Armed=TRUE; }
static inline void KeCancelTimer(KTIMER *t) { t->Armed=FALSE; }
static inline void KeRemoveQueueDpc(PKDPC d) { (void)d; }
BOOLEAN NTAPI KeSynchronizeExecution(PKINTERRUPT,PKSYNCHRONIZE_ROUTINE,PVOID);
