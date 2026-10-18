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

static bool forza_prefix_admission_allowed(uint32_t handle);
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
        if(getenv("XEMU_FORZA_PREFIX")&&!forza_prefix_admission_allowed(fid_read(env,&event,esp+4)))return;
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

/* SPDX-License-Identifier: MIT
 * Bounded kernel instruction-attempt recorder, single emulated Xbox CPU. */
#include <inttypes.h>
#ifndef PX_DESC_CAP
#define PX_DESC_CAP 65536u
#endif
#ifndef PX_INSN_CAP
#define PX_INSN_CAP 1048576u
#endif
#ifndef PX_ROW_CAP
#define PX_ROW_CAP 262144u
#endif
#ifndef PX_EXCLUDED_CAP
#define PX_EXCLUDED_CAP 16384u
#endif
#define PX_MAX_PROBE 128u
#define PX_PROFILE_HANDLE 0x42cu
#define PX_PROFILE_LIMIT 64u
#define PX_INVALID_REASONS 16u
#define PX_BAD_CAP 32u
enum { PX_OWNED=0,PX_EXCLUDED=1 };
enum { PX_I_INSTRUCTION=1,PX_I_CONTIGUITY,PX_I_FINISH,PX_I_UNKNOWN,
 PX_I_SEGMENT,PX_I_UNFINISHED,PX_I_ALIAS,PX_I_FRONTIER,PX_I_REP,
 PX_I_EMPTY_REP,PX_I_ENTER,PX_I_OUTPUT,PX_I_EXCLUDED_ALIAS,PX_I_OUTSIDE,
 PX_I_OUTPUT_PATH,PX_I_TYPE };
typedef struct {uint32_t pc,rep;} PxInsn;
typedef struct {uint32_t pc,count,start,flags,cflags,cs_base,born_api,born_seq,used,finished;} PxDesc;
typedef struct {uint32_t api,seq,tb,first,last;uint64_t executions,rep_iterations;} PxRow;
typedef struct {
 uint32_t reason,api,seq,tb,segment_tb,first,last,rep,rep_base,actual_pc,expected_pc,type,segment_type;
} PxBad;
static PxDesc px_desc[PX_DESC_CAP+1];
static PxInsn px_insns[PX_INSN_CAP];
static PxRow px_rows[PX_ROW_CAP],px_excluded[PX_EXCLUDED_CAP];
static PxBad px_bad[PX_BAD_CAP];
/* Host stores generated by TCG: descriptor, attempted ordinal, REP bodies,
 * unused(active has a separate slot), runtime entry PC, explicit type. */
static uint32_t px_progress[6],px_active;
static uint32_t px_desc_count,px_insn_count,px_row_count,px_excluded_count;
static uint32_t px_overflow,px_invalid,px_reason[PX_INVALID_REASONS+1],px_bad_count;
static uint32_t px_desc_overflow,px_insn_overflow,px_row_overflow,px_excluded_overflow;
static uint32_t px_max_probe,px_max_excluded_probe;
static uint32_t px_api,px_seq,px_segment_tb,px_segment_type,px_first,px_rep_base;
static uint32_t px_admitted,px_returned;
static int px_owned_pc(uint32_t pc)
{return (pc>=0x84001000u&&pc<0x84055400u)||(pc>=0x84069000u&&pc<0x84069b08u);}
static void px_fail(uint32_t reason)
{
 px_invalid++;px_reason[reason]++;
 if(px_reason[reason]<=2&&px_bad_count<PX_BAD_CAP){
  uint32_t id=px_progress[0];
  px_bad[px_bad_count++]=(PxBad){reason,px_api,px_seq,id,px_segment_tb,
   px_first,px_progress[1],px_progress[2],px_rep_base,px_progress[4],
   id&&id<=px_desc_count?px_desc[id].pc:0,px_progress[5],px_segment_type};
 }
}
static uint32_t px_allocate(uint32_t pc,uint32_t flags,uint32_t cflags,uint32_t cs_base)
{
 if(!px_owned_pc(pc))return 0;
 if(px_desc_count==PX_DESC_CAP){px_overflow++;px_desc_overflow++;return 0;}
 uint32_t id=++px_desc_count;
 px_desc[id]=(PxDesc){.pc=pc,.start=px_insn_count,.flags=flags,.cflags=cflags,
 .cs_base=cs_base,.born_api=px_api,.born_seq=px_api?px_seq:0};return id;
}
static void px_instruction(uint32_t id,uint32_t pc,uint32_t rep)
{
 if(!id)return;
 if(id>px_desc_count||px_desc[id].finished||rep>1){px_fail(PX_I_INSTRUCTION);return;}
 if(!px_owned_pc(pc)){px_fail(PX_I_OUTSIDE);return;}
 if(px_insn_count==PX_INSN_CAP){px_overflow++;px_insn_overflow++;return;}
 PxDesc *d=&px_desc[id];
 if(d->start+d->count!=px_insn_count){px_fail(PX_I_CONTIGUITY);return;}
 px_insns[px_insn_count++]=(PxInsn){pc,rep};d->count++;
}
static void px_finish(uint32_t id,uint32_t count)
{
 if(!id)return;
 if(id>px_desc_count||px_desc[id].finished||!count||count>512||px_desc[id].count!=count){px_fail(PX_I_FINISH);return;}
 px_desc[id].finished=1;
}
static void px_flush(void)
{
 if(!px_api)return;
 uint32_t id=px_progress[0],last=px_progress[1],rep=px_progress[2],type=px_progress[5];
 if(type>PX_EXCLUDED){px_fail(PX_I_TYPE);return;}
 if(type!=px_segment_type||id!=px_segment_tb){px_fail(PX_I_SEGMENT);return;}
 uint32_t maximum=512,key=id;
 if(type==PX_OWNED){
  if(!id||id>px_desc_count){px_fail(PX_I_UNKNOWN);return;}
  if(!px_desc[id].finished){px_fail(PX_I_UNFINISHED);return;}
  if(px_progress[4]!=px_desc[id].pc){px_fail(PX_I_ALIAS);return;}
  maximum=px_desc[id].count;
 }else{
  if(id){px_fail(PX_I_TYPE);return;}
  if(px_owned_pc(px_progress[4])){px_fail(PX_I_EXCLUDED_ALIAS);return;}
  key=px_progress[4];
 }
 if(last>maximum||!px_first||last+1<px_first){px_fail(PX_I_FRONTIER);return;}
 if(rep<px_rep_base){px_fail(PX_I_REP);return;}
 if(last+1==px_first){if(rep!=px_rep_base)px_fail(PX_I_EMPTY_REP);return;}
 PxRow *table=type==PX_OWNED?px_rows:px_excluded;
 unsigned capacity=type==PX_OWNED?PX_ROW_CAP:PX_EXCLUDED_CAP;
 uint32_t h=(px_api*2654435761u)^(px_seq*2246822519u)^(key*3266489917u)^(px_first*668265263u)^last;
 for(unsigned n=0;n<PX_MAX_PROBE&&n<capacity;n++){
  uint32_t *maximum_probe=type==PX_OWNED?&px_max_probe:&px_max_excluded_probe;
  if(n+1>*maximum_probe)*maximum_probe=n+1;
  PxRow *r=&table[(h+n)%capacity];
  if(!r->api){
   *r=(PxRow){.api=px_api,.seq=px_seq,.tb=key,.first=px_first,.last=last};
   if(type==PX_OWNED)px_row_count++;else px_excluded_count++;
  }
  if(r->api==px_api&&r->seq==px_seq&&r->tb==key&&r->first==px_first&&r->last==last){
   r->executions++;r->rep_iterations+=rep-px_rep_base;
   if(type==PX_OWNED)px_desc[id].used=1;
   px_first=last+1;px_rep_base=rep;return;
  }
 }
 px_overflow++;if(type==PX_OWNED)px_row_overflow++;else px_excluded_overflow++;
 /* Do not repeatedly rescan the same failed segment at another boundary. */
 px_first=last+1;px_rep_base=rep;
}
static void px_scope(uint32_t api,uint32_t seq)
{
 px_flush();px_api=api;px_seq=seq;px_segment_tb=px_progress[0];px_segment_type=px_progress[5];
 px_first=px_progress[1]+1;px_rep_base=px_progress[2];
}
static void px_tb_enter(uint32_t id,uint32_t type)
{
 px_flush();
 if(type>PX_EXCLUDED||(type==PX_EXCLUDED&&id)||
   (type==PX_OWNED&&(!id||id>px_desc_count||!px_desc[id].finished)))px_fail(PX_I_ENTER);
 px_segment_tb=id;px_segment_type=type;px_first=1;px_rep_base=0;
}
static void px_write(FILE *file,uint32_t reentry,uint32_t mismatch,uint32_t open)
{
 uint32_t descriptors=0,translations=0;px_flush();
 for(unsigned i=1;i<=px_desc_count;i++)if(px_desc[i].used||px_desc[i].born_api){
  descriptors++;translations+=px_desc[i].born_api!=0;
  if(!px_desc[i].finished)px_fail(PX_I_OUTPUT);
 }
 fprintf(file,"prefix_meta version=2 descriptors=%u rows=%u excluded_rows=%u translations=%u overflow=%u reentry=%u thread_mismatch=%u invalid_prefix=%u open_api=%u\n",
 descriptors,px_row_count,px_excluded_count,translations,px_overflow,reentry,mismatch,px_invalid,open);
 fprintf(file,"prefix_limits handle=%08x max_api=%u admitted=%u returned=%u admission_closed=%u range_count=2\n",PX_PROFILE_HANDLE,PX_PROFILE_LIMIT,px_admitted,px_returned,px_admitted==PX_PROFILE_LIMIT);
 fprintf(file,"prefix_range id=1 start=84001000 end=84055400\nprefix_range id=2 start=84069000 end=84069b08\n");
 fprintf(file,"prefix_health allocated_descriptors=%u allocated_instructions=%u descriptor_overflow=%u instruction_overflow=%u row_overflow=%u excluded_overflow=%u max_probe=%u max_excluded_probe=%u\n",
 px_desc_count,px_insn_count,px_desc_overflow,px_insn_overflow,px_row_overflow,px_excluded_overflow,px_max_probe,px_max_excluded_probe);
 for(unsigned i=1;i<=PX_INVALID_REASONS;i++)if(px_reason[i])fprintf(file,"prefix_invalid reason=%u count=%u\n",i,px_reason[i]);
 for(unsigned i=0;i<px_bad_count;i++){
  const PxBad *b=&px_bad[i];
  fprintf(file,"prefix_bad index=%u reason=%u api=%u identity_seq=%u tb=%u segment_tb=%u first=%u last=%u rep=%u rep_base=%u actual_pc=%08x expected_pc=%08x type=%u segment_type=%u\n",
   i+1,b->reason,b->api,b->seq,b->tb,b->segment_tb,b->first,b->last,b->rep,b->rep_base,b->actual_pc,b->expected_pc,b->type,b->segment_type);
 }
 for(unsigned i=1;i<=px_desc_count;i++){
  const PxDesc *d=&px_desc[i];if(!d->used&&!d->born_api)continue;
  fprintf(file,"prefix_tb id=%u pc=%08x count=%u generation=%u born_api=%u born_identity_seq=%u flags=%08x cflags=%08x cs_base=%08x\n",
  i,d->pc,d->count,i,d->born_api,d->born_seq,d->flags,d->cflags,d->cs_base);
  for(unsigned n=0;n<d->count;n++){
   const PxInsn *p=&px_insns[d->start+n];
   fprintf(file,"prefix_insn tb=%u ordinal=%u pc=%08x rep=%u\n",i,n+1,p->pc,p->rep);
  }
  if(d->born_api)fprintf(file,"prefix_translation api=%u identity_seq=%u tb=%u\n",d->born_api,d->born_seq,i);
 }
 for(unsigned type=PX_OWNED;type<=PX_EXCLUDED;type++){
  const PxRow *table=type==PX_OWNED?px_rows:px_excluded;
  unsigned capacity=type==PX_OWNED?PX_ROW_CAP:PX_EXCLUDED_CAP;
  for(unsigned i=0;i<capacity;i++){
   const PxRow *r=&table[i];if(!r->api)continue;
   fprintf(file,type==PX_OWNED?"prefix_row api=%u identity_seq=%u tb=%u":"prefix_excluded api=%u identity_seq=%u pc=%08x",r->api,r->seq,r->tb);
   fprintf(file," first=%u last=%u executions=%" PRIu64 " begun=%" PRIu64 " rep_iterations=%" PRIu64 "\n",r->first,r->last,r->executions,r->executions*(r->last-r->first+1),r->rep_iterations);
  }
 }
 fprintf(file,"prefix_end rows=%u excluded_rows=%u\n",px_row_count,px_excluded_count);
}

/* SPDX-License-Identifier: MIT
 * Glue to the existing scalar identity observer. */
int forza_prefix_owned_pc(uint32_t);
uint32_t forza_prefix_allocate(uint32_t,uint32_t,uint32_t,uint32_t);
void forza_prefix_instruction(uint32_t,uint32_t,uint32_t);
void forza_prefix_finish(uint32_t,uint32_t);
void *forza_prefix_slot(unsigned);
static uint32_t px_thread,px_thread_mismatch;
static const char *px_output;
static void forza_prefix_write(void)
{
 if(!px_output)return;
 FILE *file=fopen(px_output,"w");
 if(!file){fprintf(stderr,"forza prefix output could not be opened\n");return;}
 unsigned open=0;for(unsigned i=0;i<FID_THREADS;i++)open+=fid_calls[i].api!=0;
 px_write(file,fid_reentry,px_thread_mismatch,open);
 if(fclose(file))fprintf(stderr,"forza prefix output close failed\n");
}
static void forza_prefix_initialize(void)
{
 static bool initialized;
 if(initialized)return;
 initialized=true;px_output=getenv("XEMU_FORZA_PREFIX_OUTPUT");
 if(!px_output||!*px_output){px_output=NULL;px_fail(PX_I_OUTPUT_PATH);return;}
 atexit(forza_prefix_write);
}
int forza_prefix_owned_pc(uint32_t pc){return px_owned_pc(pc);}
static bool forza_prefix_admission_allowed(uint32_t handle)
{return handle==PX_PROFILE_HANDLE&&px_admitted<PX_PROFILE_LIMIT;}
uint32_t forza_prefix_allocate(uint32_t pc,uint32_t flags,uint32_t cflags,uint32_t cs_base)
{
 forza_prefix_initialize();return px_allocate(pc,flags,cflags,cs_base);
}
void forza_prefix_instruction(uint32_t id,uint32_t pc,uint32_t rep){px_instruction(id,pc,rep);}
void forza_prefix_finish(uint32_t id,uint32_t count){px_finish(id,count);}
void *forza_prefix_slot(unsigned slot)
{
 return slot==3?&px_active:&px_progress[slot];
}
static void forza_prefix_sync(void)
{
 uint32_t api=0;px_active=0;
 for(unsigned i=0;i<FID_THREADS;i++)if(fid_calls[i].api){
  px_active++;
  if(fid_calls[i].thread==px_thread)api=fid_calls[i].api;
 }
 px_scope(api,fid_count);
}
static void forza_prefix_identity_before(void){px_flush();}
static void forza_prefix_identity_after(uint32_t old_count,uint32_t old_active)
{
 if(fid_count!=old_count){
  const FidEvent *event=&fid_events[fid_count-1];
  if(event->kind==FID_BEGIN)px_admitted++;
  if(event->kind==FID_RETURN)px_returned++;
  if(!old_active&&event->kind==FID_BEGIN)px_thread=event->thread;
  if(event->thread&&px_active&&px_thread!=event->thread)px_thread_mismatch++;
 }
 forza_prefix_sync();
}
void helper_forza_prefix_tb(CPUX86State *env,uint32_t id,uint32_t type)
{
 (void)env;px_tb_enter(id,type);
}
void helper_forza_prefix_switch(CPUX86State *env)
{
 FidEvent event={0};
 px_flush();px_thread=fid_read(env,&event,0xffdff124);
 if(!px_thread||event.flags)px_thread_mismatch++;
 forza_prefix_sync();
}

