/*
 * PROJECT:         ReactOS Kernel
 * LICENSE:         GPL - See COPYING in the top level directory
 * FILE:            ntoskrnl/io/iomgr/irp.c
 * PURPOSE:         IRP Handling Functions
 * PROGRAMMERS:     Alex Ionescu (alex.ionescu@reactos.org)
 *                  Gunnar Dalsnes
 *                  Filip Navara (navaraf@reactos.org)
 *                  Pierre Schweitzer (pierre@reactos.org)
 */

typedef __SIZE_TYPE__ size_t;
typedef __UINTPTR_TYPE__ uintptr_t;
typedef __INT32_TYPE__ int32_t;
typedef __UINT32_TYPE__ uint32_t;
#define assert(x) ((void)0)
void *memset(void *, int, __SIZE_TYPE__);

#define VOID void
#define NTAPI
#define IN
#define OUT
#define ASSERT assert
#define IOTRACE(...) ((void)0)
#define RtlZeroMemory(p,n) memset((p),0,(n))
#define IO_TYPE_IRP 6
typedef size_t SIZE_T;
typedef void *PVOID;
typedef uint32_t ULONG;
typedef uintptr_t ULONG_PTR;
typedef unsigned char *PUCHAR;
typedef unsigned char UCHAR;
typedef unsigned short USHORT;
typedef signed char CCHAR;
typedef int32_t NTSTATUS;
typedef struct LIST_ENTRY { struct LIST_ENTRY *Flink,*Blink; } LIST_ENTRY;
typedef struct IO_STACK_LOCATION { unsigned char opaque[36]; } IO_STACK_LOCATION,*PIO_STACK_LOCATION;
typedef struct IRP {
    USHORT Type,Size;
    unsigned char untouched_a[13];
    LIST_ENTRY ThreadListEntry;
    struct { NTSTATUS Status; uintptr_t Information; } IoStatus;
    CCHAR StackCount,CurrentLocation;
    unsigned char ApcEnvironment,AllocationFlags;
    void *CancelRoutine;
    unsigned char untouched_b[23];
    struct { struct { PIO_STACK_LOCATION CurrentStackLocation; } Overlay; } Tail;
} IRP,*PIRP;
extern struct { UCHAR ApcStateIndex; } current_thread;
#define KeGetCurrentThread() (&current_thread)
#define InitializeListHead(p) ((p)->Flink=(p)->Blink=(p))
#define IsListEmpty(p) ((p)->Flink==(p))
VOID NTAPI IoInitializeIrp(IN PIRP Irp,
                IN USHORT PacketSize,
                IN CCHAR StackSize)
{
    /* Clear it */
    IOTRACE(IO_IRP_DEBUG,
            "%s - Initializing IRP %p\n",
            __FUNCTION__,
            Irp);
    RtlZeroMemory(Irp, PacketSize);

    /* Set the Header and other data */
    Irp->Type = IO_TYPE_IRP;
    Irp->Size = PacketSize;
    Irp->StackCount = StackSize;
    Irp->CurrentLocation = StackSize + 1;
    Irp->ApcEnvironment =  KeGetCurrentThread()->ApcStateIndex;
    Irp->Tail.Overlay.CurrentStackLocation = (PIO_STACK_LOCATION)(Irp + 1) + StackSize;

    /* Initialize the Thread List */
    InitializeListHead(&Irp->ThreadListEntry);
}
VOID NTAPI IoReuseIrp(IN OUT PIRP Irp,
           IN NTSTATUS Status)
{
    UCHAR AllocationFlags;
    IOTRACE(IO_IRP_DEBUG,
            "%s - Reusing IRP %p\n",
            __FUNCTION__,
            Irp);

    /* Make sure it's OK to reuse it */
    ASSERT(!Irp->CancelRoutine);
    ASSERT(IsListEmpty(&Irp->ThreadListEntry));

    /* Get the old flags */
    AllocationFlags = Irp->AllocationFlags;

    /* Reinitialize the IRP */
    IoInitializeIrp(Irp, Irp->Size, Irp->StackCount);

    /* Duplicate the data */
    Irp->IoStatus.Status = Status;
    Irp->AllocationFlags = AllocationFlags;
}
