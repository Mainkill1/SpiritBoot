/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "native_packet.h"
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

typedef struct bench_fixture {
    IRP child;
    IO_STACK_LOCATION stack[3];
    SCSI_REQUEST_BLOCK srb;
    MDL mdl;
    uint32_t pfns[3];
    uint8_t sense[32];
    nx_packet_resources resources;
    nx_packet_command command;
    nx_packet_ticket ticket;
} bench_fixture;

static bench_fixture *active;
static volatile uint32_t checksum;

static NTSTATUS completion(void *device,PIRP irp,void *context)
{ (void)device;(void)irp;(void)context;return 0; }

VOID IoReuseIrp(PIRP irp,NTSTATUS status)
{
    int8_t count=irp->StackCount;
    memset(irp,0,sizeof(*irp));
    irp->StackCount=count;
    irp->CurrentLocation=count+1;
    irp->Tail.Overlay.CurrentStackLocation=active->stack+count;
    irp->IoStatus.Status=status;
}

static void init(bench_fixture *f)
{
    memset(f,0,sizeof(*f));active=f;
    f->child.StackCount=3;
    f->mdl.StartVa=0;f->mdl.ByteCount=8192;
    f->resources=(nx_packet_resources){&f->child,&f->srb,&f->mdl,f->sense,32,2,1,1};
    f->command=(nx_packet_command){.token={1,2,3},.mdl_virtual=0,.data_virtual=0,
        .bytes=4096,.direction=0x40,.function=0,.cdb_length=10,.cdb={0x28},
        .timeout_seconds=30,.timeout_limit_seconds=120,.max_bytes=65536,.max_pages=16,
        .alignment_mask=0,.lower_stack_count=2,.completion=completion,.completion_context=f};
}

static uint64_t now_ns(void)
{
    struct timespec t;
    if(clock_gettime(CLOCK_THREAD_CPUTIME_ID,&t)) abort();
    return (uint64_t)t.tv_sec*1000000000u+(uint64_t)t.tv_nsec;
}

int main(int argc,char **argv)
{
    unsigned loops=argc>1?(unsigned)strtoul(argv[1],0,0):500000u;
    bench_fixture f;init(&f);
    for(unsigned i=0;i<10000;++i) {
        f.command.cdb[9]=(uint8_t)i;
        if(nx_packet_prepare(&f.resources,&f.command,&f.ticket)!=NX_PACKET_OK) abort();
    }
    uint64_t start=now_ns();
    for(unsigned i=0;i<loops;++i) {
        f.command.cdb[9]=(uint8_t)i;
        if(nx_packet_prepare(&f.resources,&f.command,&f.ticket)!=NX_PACKET_OK) abort();
        checksum+=f.srb.Cdb[0]+f.srb.Cdb[9]+f.stack[2].MajorFunction;
    }
    uint64_t elapsed=now_ns()-start;
    printf("%llu %u %u\n",(unsigned long long)elapsed,loops,checksum);
    return 0;
}
