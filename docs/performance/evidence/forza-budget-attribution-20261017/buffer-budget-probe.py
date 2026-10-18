from pathlib import Path
p=Path('.scratch/xemu-halo-dma-trace-20261017/target/i386/tcg/misc_helper.c');s=p.read_text();start=s.index('/* Value-only budget attribution.');end=s.index('void helper_spirit_menu_trace',start)
new=r'''/* Local value-only observation: no allocation, formatting or host writes in
 * the title pump. Flush after emulation exits, outside every measurement. */
typedef struct {
    uint32_t thread,queue,active,reads,bytes,callbacks,checks,deadline,empty;
    uint32_t limit,outstanding,budget,read_open,wait_open,callback_open;
    int64_t begin,read_begin,wait_begin,callback_begin,read_ns,wait_ns,initial_ns,callback_ns;
    uint64_t elapsed,first_elapsed;
} ForzaBudget;
typedef struct {
    ForzaBudget data;
    int64_t end,host_end;
    uint32_t outstanding_end;
} ForzaBudgetRow;
static ForzaBudgetRow forza_budget_rows[16384];
static unsigned forza_budget_count,forza_budget_overflow,forza_budget_reentry;
static void forza_budget_flush(void)
{
    const char *path=getenv("XEMU_FORZA_BUDGET_OUTPUT");
    FILE *f=path?fopen(path,"w"):NULL;
    if(!f)return;
    fprintf(f,"forza_budget_meta rows=%u overflow=%u reentry=%u\n",forza_budget_count,forza_budget_overflow,forza_budget_reentry);
    for(unsigned i=0;i<forza_budget_count;i++){
        ForzaBudgetRow *row=&forza_budget_rows[i];ForzaBudget *p=&row->data;
        fprintf(f,"forza_budget host_ns=%" PRId64 " virtual_ns=%" PRId64 " thread=%08x queue=%08x budget=%u limit=%u outstanding_start=%u outstanding_end=%u reads=%u bytes=%u callbacks=%u checks=%u deadline_pc=%08x empty=%u first_elapsed_ticks=%" PRIu64 " elapsed_ticks=%" PRIu64 " total_ns=%" PRId64 " initial_ns=%" PRId64 " read_ns=%" PRId64 " wait_ns=%" PRId64 " callback_ns=%" PRId64 " read_open=%u wait_open=%u callback_open=%u\n",
          row->host_end,row->end,p->thread,p->queue,p->budget,p->limit,p->outstanding,row->outstanding_end,p->reads,p->bytes,p->callbacks,p->checks,p->deadline,p->empty,p->first_elapsed,p->elapsed,row->end-p->begin,p->initial_ns,p->read_ns,p->wait_ns,p->callback_ns,p->read_open,p->wait_open,p->callback_open);
    }
    fclose(f);
}
static void forza_budget_summary(CPUX86State *env,uint32_t pc)
{
    static ForzaBudget slots[16];
    static bool registered;
    if(!registered){atexit(forza_budget_flush);registered=true;}
    bool complex_profile=getenv("XEMU_FORZA_COMPLEX")!=NULL;
    uint32_t thread=spirit_read32(env,complex_profile?env->segs[R_FS].base+0x28:0xffdff124);
    ForzaBudget *p=NULL;
    for(unsigned i=0;i<16;i++)if(slots[i].thread==thread){p=&slots[i];break;}
    if(!p)for(unsigned i=0;i<16;i++)if(!slots[i].active){p=&slots[i];break;}
    if(!p || !thread)return;
    int64_t now=qemu_clock_get_ns(QEMU_CLOCK_VIRTUAL);
    if(pc==0x00110d20){
        if(p->active)forza_budget_reentry++;
        memset(p,0,sizeof(*p));p->thread=thread;p->queue=env->regs[R_ECX];p->active=1;p->begin=now;
        p->budget=spirit_read32(env,0x0059c414);p->limit=spirit_read32(env,p->queue+0x18);
        p->outstanding=spirit_read32(env,p->queue+0x1c);return;
    }
    if(!p->active || p->thread!=thread)return;
    if(pc==0x8404cec4 || pc==0x80017467){
        uint32_t esp=env->regs[R_ESP];
        if(spirit_read32(env,esp)==0x0026741a){p->reads++;p->bytes+=spirit_read32(env,esp+28);p->read_begin=now;p->read_open=1;}
    }
    if(pc==0x0026741a && p->read_open){p->read_ns+=now-p->read_begin;p->read_open=0;}
    if(pc==0x8401989c || pc==0x8001980a){p->wait_begin=now;p->wait_open=1;}
    if(pc==0x00264e84 && p->wait_open){p->wait_ns+=now-p->wait_begin;p->wait_open=0;}
    if(pc==0x001103e0){p->callbacks++;p->callback_begin=now;p->callback_open=1;}
    if(pc==0x00110422 && p->callback_open){p->callback_ns+=now-p->callback_begin;p->callback_open=0;}
    if(pc==0x00110d60)p->initial_ns=now-p->begin;
    if(pc==0x00110d9f || pc==0x00110dce){
        p->elapsed=((uint64_t)(uint32_t)env->regs[R_EDX]<<32)|(uint32_t)env->regs[R_EAX];
        if(!p->checks)p->first_elapsed=p->elapsed;
        p->checks++;
        if(p->elapsed>=p->budget)p->deadline=pc;
    }
    if(pc==0x00110ec0)p->empty=1;
    if(pc==0x00110ec6){
        if(forza_budget_count<16384){
            ForzaBudgetRow *row=&forza_budget_rows[forza_budget_count++];
            row->data=*p;row->end=now;row->host_end=qemu_clock_get_ns(QEMU_CLOCK_HOST);
            row->outstanding_end=spirit_read32(env,p->queue+0x1c);
        } else forza_budget_overflow++;
        p->active=0;
    }
}

'''
s=s[:start]+new+s[end:];p.write_text(s)
p=Path('.scratch/xemu-halo-dma-trace-20261017/target/i386/tcg/translate.c');s=p.read_text();needle='''        bool selected = true;''';insert='''        if(getenv("XEMU_FORZA_BUDGET_ONLY")) {
            switch(pc) {
            case 0x00110d20: case 0x00110d60: case 0x00110d9f: case 0x00110dce:
            case 0x00110ec0: case 0x00110ec6: case 0x001103e0: case 0x00110422:
            case 0x0026741a: case 0x00264e84:
            case 0x8404cec4: case 0x80017467: case 0x8401989c: case 0x8001980a:
                gen_helper_spirit_menu_trace(tcg_env,tcg_constant_i32(pc));
                break;
            }
            goto forza_instrumentation_done;
        }
''';assert needle in s;s=s.replace(needle,insert+needle,1);needle='''#ifdef TARGET_VSYSCALL_PAGE
    /*''';assert needle in s;s=s.replace(needle,'''forza_instrumentation_done:;

'''+needle,1);p.write_text(s)
