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
