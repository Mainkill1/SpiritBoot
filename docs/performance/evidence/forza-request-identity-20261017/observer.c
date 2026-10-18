/* SPDX-License-Identifier: MIT
 * Independently authored, baseline-add882 scalar identity observer.
 * No guest writes, allocations, formatting or file I/O during emulation.
 * This is an observation tool, not firmware code. */
#define FID_CAPACITY 131072u
#define FID_THREADS 16u
enum { FID_BEGIN=1, FID_RETURN, FID_BIND, FID_START, FID_COMPLETE,
       FID_CALLBACK, FID_QUEUE_RETURN, FID_FS_BIND, FID_MAP_BEGIN, FID_MAP_WALK, FID_MAP_END, FID_MAP_READY };
typedef struct {
    int64_t host_ns, virtual_ns;
    uint32_t seq,kind,thread,api,iosb,parent,child,srb,request,envelope;
    uint32_t bytes,status,info,value0,value1,flags;
} FidEvent;
typedef struct { uint32_t thread,api,esp,iosb; } FidCall;
typedef struct { uint32_t thread,api,frame,walk; } FidMap;
static FidMap fid_maps[FID_THREADS];
static unsigned fid_map_reentry,fid_map_lost;
static FidEvent fid_events[FID_CAPACITY];
static FidCall fid_calls[FID_THREADS];
static uint32_t fid_count,fid_overflow,fid_reentry,fid_lost,fid_read_fail;
static uint32_t fid_generation,fid_seen,fid_enabled;
static const char *fid_output;

static void forza_identity_flush(void)
{
    FILE *file;
    unsigned open=0,map_open=0;
    if(!fid_enabled)return;
    for(unsigned i=0;i<FID_THREADS;i++){open+=fid_calls[i].api!=0;map_open+=fid_maps[i].api!=0;}
    file=fid_output?fopen(fid_output,"w"):NULL;
    if(!file){fprintf(stderr,"forza identity output could not be opened\n");return;}
    fprintf(file,"identity_meta version=1 events=%u overflow=%u reentry=%u lost=%u read_fail=%u open_api=%u map_open=%u map_reentry=%u map_lost=%u\n",
            fid_count,fid_overflow,fid_reentry,fid_lost,fid_read_fail,open,map_open,fid_map_reentry,fid_map_lost);
    for(unsigned i=0;i<fid_count;i++){
        const FidEvent *r=&fid_events[i];
        fprintf(file,"identity_event seq=%u kind=%u host_ns=%" PRId64 " virtual_ns=%" PRId64
          " thread=%08x api=%u iosb=%08x parent=%08x child=%08x srb=%08x request=%08x envelope=%08x"
          " bytes=%u status=%08x info=%u value0=%08x value1=%08x flags=%u\n",
          r->seq,r->kind,r->host_ns,r->virtual_ns,r->thread,r->api,r->iosb,r->parent,r->child,
          r->srb,r->request,r->envelope,r->bytes,r->status,r->info,r->value0,r->value1,r->flags);
    }
    fprintf(file,"identity_end events=%u\n",fid_count);
    if(fclose(file))fprintf(stderr,"forza identity output close failed\n");
}

static uint32_t fid_read(CPUX86State *env,FidEvent *event,uint32_t address)
{
    uint8_t bytes[4];
    if(!address || cpu_memory_rw_debug(env_cpu(env),address,bytes,4,false)){
        event->flags|=1;fid_read_fail++;return 0;
    }
    return ldl_le_p(bytes);
}

static void fid_append(FidEvent *event)
{
    if(fid_count==FID_CAPACITY){fid_overflow++;return;}
    event->seq=fid_count+1;
    fid_events[fid_count++]=*event;
}

static void forza_identity_profile(CPUX86State *env,uint32_t pc)
{
    static bool registered;
    FidEvent event={0};
    FidCall *call=NULL;
    uint32_t esp=env->regs[R_ESP];
    if(!registered){
        fid_output=getenv("XEMU_FORZA_IDENTITY_OUTPUT");
        fid_enabled=fid_output&&*fid_output;
        if(fid_enabled)atexit(forza_identity_flush);
        registered=true;
    }
    if(!fid_enabled)return;
    event.host_ns=qemu_clock_get_ns(QEMU_CLOCK_HOST);
    event.virtual_ns=qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL);
    if(pc==0x8404cec4){
        /* NtReadFile stdcall: return address, then eight arguments. APC
         * context (not APC routine) selects the title's world callback. */
        if(fid_read(env,&event,esp)!=0x0026741a ||
           fid_read(env,&event,esp+16)!=0x001103e0)return;
        event.thread=fid_read(env,&event,0xffdff124);
        for(unsigned i=0;i<FID_THREADS;i++)
            if(fid_calls[i].api&&fid_calls[i].thread==event.thread){call=&fid_calls[i];break;}
        if(call){fid_reentry++;event.flags|=4;}
        if(!call)for(unsigned i=0;i<FID_THREADS;i++)
            if(!fid_calls[i].api){call=&fid_calls[i];break;}
        if(!call||!event.thread){fid_lost++;return;}
        event.kind=FID_BEGIN;event.api=++fid_generation;
        event.iosb=fid_read(env,&event,esp+20);
        event.bytes=fid_read(env,&event,esp+28);
        event.value0=fid_read(env,&event,esp+4); /* file handle */
        event.status=fid_read(env,&event,event.iosb);
        event.info=fid_read(env,&event,event.iosb+4);
        *call=(FidCall){event.thread,event.api,esp+36,event.iosb};
        fid_seen=1;fid_append(&event);return;
    }
    if(!fid_seen)return;
    event.thread=fid_read(env,&event,0xffdff124);
    for(unsigned i=0;i<FID_THREADS;i++)
        if(fid_calls[i].api&&fid_calls[i].thread==event.thread){call=&fid_calls[i];break;}
    if(call)event.api=call->api; /* execution context, not request ownership */
    if(pc==0x84043eac || pc==0x84044030 || pc==0x8404429c){
        FidMap *map=NULL;
        for(unsigned i=0;i<FID_THREADS;i++)
            if(fid_maps[i].api&&fid_maps[i].thread==event.thread){map=&fid_maps[i];break;}
        if(pc==0x84043eac){
            if(!call || fid_read(env,&event,esp)!=0x84041e06)return;
            if(map){fid_map_reentry++;return;}
            for(unsigned i=0;i<FID_THREADS;i++)if(!fid_maps[i].api){map=&fid_maps[i];break;}
            if(!map){fid_map_lost++;return;}
            *map=(FidMap){event.thread,call->api,esp-4,0};
            event.kind=FID_MAP_BEGIN;event.request=map->frame;
            /* EBX still holds the caller's VFAT_IRP_CONTEXT at this entry. */
            event.parent=fid_read(env,&event,env->regs[R_EBX]);
            event.iosb=fid_read(env,&event,event.parent+0x1c);
            event.bytes=fid_read(env,&event,esp+4);
        }else{
            if(!map)return;
            if(map->frame!=(uint32_t)env->regs[R_EBP]){fid_map_lost++;return;}
            event.api=map->api;event.request=map->frame;
            if(pc==0x84044030){
                if(map->walk){fid_map_reentry++;return;}
                map->walk=1;event.kind=FID_MAP_WALK;
                event.value0=fid_read(env,&event,map->frame-0x6c); /* Skip */
                event.bytes=fid_read(env,&event,map->frame-0x70); /* Steps */
                event.info=fid_read(env,&event,map->frame-0x58); /* initialized Step */
            }else{
                event.kind=FID_MAP_END;event.value0=map->walk;
                event.status=fid_read(env,&event,map->frame-0x5d)&0xff;
                if(map->walk){
                    event.value1=fid_read(env,&event,map->frame-0x6c);
                    event.bytes=fid_read(env,&event,map->frame-0x70);
                    event.info=fid_read(env,&event,map->frame-0x58);
                }
                map->api=0;
            }
        }
        fid_append(&event);return;
    }
    switch(pc){
    case 0x8403fa83:
        event.kind=FID_MAP_READY;event.request=env->regs[R_EBX];
        event.parent=fid_read(env,&event,event.request);
        event.iosb=fid_read(env,&event,event.parent+0x1c);
        event.value0=env->regs[R_ESI]; /* extent hit flag, before it is repurposed */
        if(event.value0>1)event.flags|=2;
        break;
    case 0x0026741a:
        if(!call || call->esp!=esp)return;
        event.kind=FID_RETURN;event.iosb=call->iosb;
        event.status=env->regs[R_EAX]; /* native return status */
        event.value0=fid_read(env,&event,event.iosb); /* sampled IOSB status */
        event.info=fid_read(env,&event,event.iosb+4);
        call->api=0;
        break;
    case 0x840435e1:
        /* VFAT fallback partial IRP: the separate IRP has no UserIosb or
         * MasterIrp. Capture the owned context's original-parent edge. */
        event.kind=FID_FS_BIND;event.request=env->regs[R_EBX];
        event.parent=fid_read(env,&event,event.request);
        event.child=env->regs[R_EDX];
        event.iosb=fid_read(env,&event,event.parent+0x1c);
        event.value0=env->regs[R_ECX];
        if(event.child!=(uint32_t)env->regs[R_EDI])event.flags|=2;
        break;
    case 0x840517ab:
        /* Immediately before the owned port's IofCallDriver instruction. */
        event.kind=FID_BIND;event.envelope=env->regs[R_EBX];
        event.parent=fid_read(env,&event,event.envelope+4);
        event.child=env->regs[R_EDX];event.srb=event.envelope+12;
        event.iosb=fid_read(env,&event,event.parent+0x1c);
        event.bytes=fid_read(env,&event,event.srb+0x10);
        if(event.child!=fid_read(env,&event,event.envelope+8) ||
           event.child!=fid_read(env,&event,event.srb+0x24))event.flags|=2;
        event.value0=env->regs[R_ECX]; /* lower device */
        break;
    case 0x840347e4:
        /* cdecl PataStartIo(ChannelContext, Request), at function entry. */
        event.kind=FID_START;event.request=fid_read(env,&event,esp+8);
        event.child=fid_read(env,&event,event.request+0x34);
        event.srb=fid_read(env,&event,event.request+0x38);
        event.bytes=fid_read(env,&event,event.request+0x28);
        event.value0=fid_read(env,&event,event.request+0x44); /* tag */
        event.value1=fid_read(env,&event,event.request+0x48); /* slot */
        if(event.srb && event.child!=fid_read(env,&event,event.srb+0x24))event.flags|=2;
        break;
    case 0x840083b4:
        /* Queue helper common epilogue, before EBX is restored. A pending
         * result identifies this path, not proof that cancellation is absent. */
        event.kind=FID_QUEUE_RETURN;event.srb=env->regs[R_EBX];
        event.child=fid_read(env,&event,event.srb+0x24);
        event.status=env->regs[R_EAX];
        break;
    case 0x840159f0:
        /* IofCompleteRequest fastcall entry, before any retained request reuse. */
        event.kind=FID_COMPLETE;event.child=env->regs[R_ECX];
        event.iosb=fid_read(env,&event,event.child+0x1c);
        event.status=fid_read(env,&event,event.child+0x10);
        event.info=fid_read(env,&event,event.child+0x14);
        break;
    case 0x001103e0:
        event.kind=FID_CALLBACK;
        event.iosb=fid_read(env,&event,esp+12);
        event.status=fid_read(env,&event,esp+4);
        event.info=fid_read(env,&event,esp+8);
        break;
    default:return;
    }
    fid_append(&event);
}
