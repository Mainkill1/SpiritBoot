/* SPDX-License-Identifier: GPL-2.0-or-later
 * Host-only text demonstration. No Xbox hardware or persistent EEPROM writes.
 */
#include "boot_setup.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct { SbSettings saved; unsigned writes; bool stopped; } Demo;
static SbCommitResult commit(void *context, const SbSettings *old,
                             const SbSettings *next, uint32_t changed)
{
    Demo *d=context;
    if (memcmp(old,&d->saved,sizeof(*old)) || !changed) return SB_COMMIT_REJECTED;
    d->saved=*next;
    ++d->writes;
    return SB_COMMIT_OK; /* This is an in-memory backend, not real durability. */
}
static bool quiesce(void *context, void *base, size_t bytes)
{
    Demo *d=context; (void)base; (void)bytes;
    d->stopped=true;
    return true; /* No devices exist in the host demo. Native adapter must fence. */
}
static bool release_arena(void *context, void *base, size_t bytes)
{
    Demo *d=context;
    const unsigned char *p=base;
    if (!d->stopped) return false;
    for (size_t i=0;i<bytes;++i) if (p[i]) return false;
    free(base);
    return true;
}
static void draw(const SbSetup *s)
{
    char value[48];
    puts("\nSPIRITBOOT - boot setup (HOST DEMO)");
    puts("w/s: row   a/d: value   e: A/select   x: save   b: discard");
    puts("Type one command and Enter. EEPROM is simulated in memory.");
    if (s->state==SB_MENU_CONFIRM_SAVE) {
        puts("Save changed settings and reboot? e: confirm   b: return"); return;
    }
    if (s->state==SB_MENU_CONFIRM_DISCARD) {
        puts("Discard staged changes and continue? e: confirm   b: return"); return;
    }
    if (s->state==SB_MENU_RECOVERY) {
        puts("Persistence not verified. e: retry; normal boot blocked."); return;
    }
    for (unsigned i=0;i<SB_ROW_COUNT;++i) {
        sb_setup_field_value(s,(SbSetupRow)i,value,sizeof(value));
        printf("%c %-23s %s\n",s->row==(SbSetupRow)i ? '>' : ' ',
               sb_setup_field_label((SbSetupRow)i),value);
    }
    printf("Changed setting words: 0x%x\n",sb_setup_changed(s));
}
int main(void)
{
    SbBootGate gate;
    SbGateResult result=SB_GATE_WAIT;
    char line[64];
    Demo demo={.saved={1,0,0}};
    SbSettingsStore store={&demo,commit};
    SbArenaOps ops={&demo,quiesce,release_arena};
    SbMenuState action;
    SbBootArena arena;
    SbSetup *setup;
    puts("HOST DEMO: h simulates holding controller Start for 600 ms at boot.");
    puts("Any other input simulates no-button boot. No real controller is accessed.");
    sb_boot_gate_init(&gate,0);
    if (!fgets(line,sizeof(line),stdin) || line[0]!='h') {
        result=sb_boot_gate_poll(&gate,(SbInput){SB_WINDOW_MS,1,0,false});
    } else {
        for (unsigned ms=0;ms<=SB_HOLD_MS;ms+=50)
            result=sb_boot_gate_poll(&gate,(SbInput){ms,1,SB_START,true});
    }
    if (result!=SB_GATE_ENTER) {
        puts("Normal boot: setup arena never allocated."); return 0;
    }
    arena=(SbBootArena){aligned_alloc(SB_PAGE_SIZE,2u*SB_PAGE_SIZE),
                        2u*SB_PAGE_SIZE,SB_ARENA_LIVE};
    if (!arena.base) { fputs("Setup allocation failed.\n",stderr); return 1; }
    memset(arena.base,0xa5,arena.bytes);
    setup=arena.base;
    sb_setup_open(setup,demo.saved,SB_ALL_FIELDS);
    while (setup->state!=SB_MENU_CONTINUE && setup->state!=SB_MENU_REBOOT) {
        uint32_t key=0;
        draw(setup);
        if (!fgets(line,sizeof(line),stdin)) break;
        switch (line[0]) {
        case 'w': key=SB_UP; break; case 's': key=SB_DOWN; break;
        case 'a': key=SB_LEFT; break; case 'd': key=SB_RIGHT; break;
        case 'e': key=SB_A; break; case 'b': key=SB_B; break;
        case 'x': key=SB_X; break; default: continue;
        }
        sb_setup_input(setup,(SbInput){0,1,0,true},&store);
        sb_setup_input(setup,(SbInput){0,1,key,true},&store);
    }
    action=setup->state; /* Copy out before releasing all session state. */
    if (!sb_boot_arena_retire(&arena,&ops)) {
        fputs("Teardown failed; title launch blocked.\n",stderr); return 2;
    }
    printf("Arena scrubbed and freed; remaining owned bytes=%zu; simulated commits=%u\n",
           arena.bytes,demo.writes);
    if (action==SB_MENU_REBOOT) puts("Requested action: reboot (simulated).");
    else if (action==SB_MENU_CONTINUE) puts("Requested action: continue boot (simulated).");
    else { puts("Demo input ended; no title launch requested."); return 2; }
    return 0;
}
