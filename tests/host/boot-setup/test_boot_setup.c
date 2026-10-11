/* SPDX-License-Identifier: GPL-2.0-or-later */
#include "boot_setup.h"
#include <assert.h>
#include <stdio.h>
#include <string.h>

static unsigned tests;
#define RUN(f) do { f(); printf("ok %u - %s\n", ++tests, #f); } while (0)
static SbInput input(uint32_t ms, uint32_t source, uint32_t keys, bool valid)
{ return (SbInput){ms,source,keys,valid}; }
static SbGateResult hold(SbBootGate *g, uint32_t start, unsigned duration, uint32_t source)
{
    SbGateResult r=SB_GATE_WAIT;
    for (unsigned t=0; t<=duration; t+=50)
        r=sb_boot_gate_poll(g,input(start+t,source,SB_START,true));
    return r;
}
static void held_at_boot(void) {
    SbBootGate g; sb_boot_gate_init(&g,100);
    assert(hold(&g,100,550,3)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(700,3,SB_START,true))==SB_GATE_ENTER);
    assert(sb_boot_gate_poll(&g,input(9999,0,0,false))==SB_GATE_ENTER);
}
static void short_presses_do_not_accumulate(void) {
    SbBootGate g; sb_boot_gate_init(&g,0);
    assert(hold(&g,0,400,1)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(450,1,0,true))==SB_GATE_WAIT);
    assert(hold(&g,500,550,1)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(1100,1,SB_START,true))==SB_GATE_ENTER);
}
static void disconnected_input_restarts_hold(void) {
    SbBootGate g; sb_boot_gate_init(&g,0); hold(&g,0,500,1);
    sb_boot_gate_poll(&g,input(550,1,SB_START,false));
    assert(hold(&g,600,550,1)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(1200,1,SB_START,true))==SB_GATE_ENTER);
}
static void different_controllers_cannot_share_hold(void) {
    SbBootGate g; sb_boot_gate_init(&g,0); hold(&g,0,500,1);
    assert(hold(&g,550,550,2)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(1150,2,SB_START,true))==SB_GATE_ENTER);
}
static void stale_report_gap_restarts_hold(void) {
    SbBootGate g; sb_boot_gate_init(&g,0); hold(&g,0,500,1);
    assert(hold(&g,601,550,1)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(1201,1,SB_START,true))==SB_GATE_ENTER);
}
static void missing_input_has_bounded_timeout(void) {
    SbBootGate g; sb_boot_gate_init(&g,0);
    assert(sb_boot_gate_poll(&g,input(1999,1,0,false))==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(2000,1,SB_START,true))==SB_GATE_BOOT);
    assert(hold(&g,0,650,1)==SB_GATE_BOOT);
}
static void late_hold_cannot_extend_boot_window(void) {
    SbBootGate g; sb_boot_gate_init(&g,0);
    assert(hold(&g,1500,450,1)==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(2000,1,SB_START,true))==SB_GATE_BOOT);
}
static void gate_clock_wrap_is_supported(void) {
    SbBootGate g; uint32_t start=UINT32_MAX-300u;
    sb_boot_gate_init(&g,start);
    assert(hold(&g,start,600,1)==SB_GATE_ENTER);
}
static void backward_clock_does_not_enter_menu(void) {
    SbBootGate g; sb_boot_gate_init(&g,0); hold(&g,0,400,1);
    assert(sb_boot_gate_poll(&g,input(350,1,SB_START,true))==SB_GATE_BOOT);
}
static void exact_sample_gap_is_allowed(void) {
    SbBootGate g; sb_boot_gate_init(&g,0);
    for (unsigned t=0;t<600;t+=100)
        assert(sb_boot_gate_poll(&g,input(t,1,SB_START,true))==SB_GATE_WAIT);
    assert(sb_boot_gate_poll(&g,input(600,1,SB_START,true))==SB_GATE_ENTER);
}

typedef struct {
    SbSettings initial, wanted, hardware;
    uint32_t changed;
    unsigned calls;
    SbCommitResult result;
} Store;
static SbCommitResult commit(void *ctx, const SbSettings *old,
                             const SbSettings *value, uint32_t changed) {
    Store *f=ctx; ++f->calls; f->initial=*old; f->wanted=*value; f->changed=changed;
    if (f->result==SB_COMMIT_OK) f->hardware=*value;
    if (f->result==SB_COMMIT_UNCERTAIN) f->hardware.video=value->video ^ 1u;
    return f->result;
}
static SbSettings initial(void) { return (SbSettings){1,0x80000010u,0x40000000u}; }
static void sample(SbSetup *s, uint32_t keys, uint32_t source, bool valid,
                   const SbSettingsStore *store) {
    sb_setup_input(s,input(0,source,keys,valid),store);
}
static void press(SbSetup *s, uint32_t keys, const SbSettingsStore *store) {
    sample(s,0,1,true,store); sample(s,keys,1,true,store);
}
static void row(SbSetup *s, SbSetupRow target) {
    for (unsigned i=0;s->row!=target && i<SB_ROW_COUNT;i++) press(s,SB_DOWN,NULL);
    assert(s->row==target);
}
static void menu_starts_without_mutation(void) {
    SbSetup s; SbSettings v={0,0xdeadbeef,0xbaadf00d};
    sb_setup_open(&s,v,SB_ALL_FIELDS);
    assert(sb_setup_changed(&s)==0 && s.state==SB_MENU_EDIT);
    assert(memcmp(&s.edited,&v,sizeof(v))==0);
}
static void entry_button_must_be_released(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    sample(&s,SB_A,1,true,NULL); sample(&s,SB_A,1,true,NULL);
    assert(sb_setup_changed(&s)==0);
    press(&s,SB_A,NULL); assert(s.edited.language==2);
    sample(&s,SB_A,1,true,NULL); assert(s.edited.language==2);
}
static void reconnect_requires_neutral_report(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    press(&s,SB_A,NULL); assert(s.edited.language==2);
    sample(&s,0,1,false,NULL); sample(&s,SB_A,2,true,NULL);
    assert(s.edited.language==2);
    sample(&s,0,2,true,NULL); sample(&s,SB_A,2,true,NULL);
    assert(s.edited.language==3);
}
static void changing_device_without_disconnect_requires_release(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    press(&s,SB_A,NULL); sample(&s,SB_A,2,true,NULL);
    assert(s.edited.language==2);
}
static void language_wrap_and_unknown_value(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    press(&s,SB_LEFT,NULL); assert(s.edited.language==9);
    press(&s,SB_RIGHT,NULL); assert(s.edited.language==1);
    sb_setup_open(&s,(SbSettings){999,0,0},SB_ALL_FIELDS);
    press(&s,SB_RIGHT,NULL); assert(s.edited.language==1);
}
static void video_edit_preserves_unknown_bits(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    row(&s,SB_480P); press(&s,SB_RIGHT,NULL);
    assert(s.edited.video==(initial().video|0x00080000u));
    assert(sb_setup_changed(&s)==SB_VIDEO_WORD);
    press(&s,SB_LEFT,NULL); assert(sb_setup_changed(&s)==0);
}
static void aspect_modes_are_mutually_exclusive(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS); row(&s,SB_ASPECT);
    press(&s,SB_A,NULL); assert(s.edited.video==(initial().video|0x10000u));
    press(&s,SB_A,NULL); assert(s.edited.video==(initial().video|0x100000u));
    press(&s,SB_A,NULL); assert(s.edited.video==initial().video);
}
static void audio_edit_preserves_unknown_bits(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS); row(&s,SB_AUDIO_MODE);
    press(&s,SB_LEFT,NULL); assert(s.edited.audio==(initial().audio|2u));
    row(&s,SB_AC3); press(&s,SB_A,NULL);
    assert(s.edited.audio==(initial().audio|2u|0x10000u));
    row(&s,SB_DTS); press(&s,SB_A,NULL);
    assert(s.edited.audio==(initial().audio|2u|0x30000u));
    assert(sb_setup_changed(&s)==SB_AUDIO_WORD);
}
static void unavailable_fields_cannot_be_changed(void) {
    SbSetup s; char text[32]; sb_setup_open(&s,initial(),0);
    for (unsigned i=0;i<SB_FIELD_COUNT;i++) {
        row(&s,(SbSetupRow)i); press(&s,SB_A,NULL);
        assert(sb_setup_changed(&s)==0);
        sb_setup_field_value(&s,(SbSetupRow)i,text,sizeof(text));
        assert(strcmp(text,"Unavailable")==0);
    }
}
static void conflicting_buttons_are_ignored(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    press(&s,SB_RIGHT|SB_LEFT,NULL); assert(sb_setup_changed(&s)==0);
    press(&s,SB_A|SB_X,NULL); assert(s.state==SB_MENU_EDIT && sb_setup_changed(&s)==0);
}
static void clean_continue_never_calls_writer(void) {
    Store f={0}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_B,&io);
    assert(s.state==SB_MENU_CONTINUE && f.calls==0);
}
static void dirty_discard_needs_confirmation_and_never_writes(void) {
    Store f={0}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_A,&io);
    press(&s,SB_B,&io); assert(s.state==SB_MENU_CONFIRM_DISCARD && f.calls==0);
    press(&s,SB_B,&io); assert(s.state==SB_MENU_EDIT);
    press(&s,SB_B,&io); press(&s,SB_A,&io);
    assert(s.state==SB_MENU_CONTINUE && f.calls==0);
}
static void save_requires_second_press_and_verified_result(void) {
    Store f={0}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_A,&io);
    row(&s,SB_SAVE); press(&s,SB_A,&io);
    assert(s.state==SB_MENU_CONFIRM_SAVE && f.calls==0);
    sample(&s,SB_A,1,true,&io); assert(f.calls==0);
    press(&s,SB_A,&io);
    assert(s.state==SB_MENU_REBOOT && f.calls==1 && f.changed==SB_LANGUAGE_WORD);
    assert(f.initial.language==1 && f.wanted.language==2 && f.hardware.language==2);
    press(&s,SB_A,&io); assert(f.calls==1);
}
static void no_change_save_performs_no_write(void) {
    Store f={0}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_X,&io);
    assert(s.state==SB_MENU_CONTINUE && f.calls==0);
}
static void rejected_commit_can_be_cancelled(void) {
    Store f={.result=SB_COMMIT_REJECTED}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_A,&io);
    press(&s,SB_X,&io); press(&s,SB_A,&io);
    assert(s.state==SB_MENU_EDIT && s.last_save==SB_COMMIT_REJECTED && f.calls==1);
    press(&s,SB_B,&io); press(&s,SB_A,&io); assert(s.state==SB_MENU_CONTINUE);
}
static void uncertain_commit_blocks_continue_and_edits(void) {
    Store f={.result=SB_COMMIT_UNCERTAIN}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_A,&io);
    press(&s,SB_X,&io); press(&s,SB_A,&io);
    assert(s.state==SB_MENU_RECOVERY && f.calls==1);
    press(&s,SB_B,&io); press(&s,SB_RIGHT,&io);
    assert(s.state==SB_MENU_RECOVERY && s.edited.language==2);
    f.result=SB_COMMIT_OK; press(&s,SB_A,&io);
    assert(s.state==SB_MENU_REBOOT && f.calls==2);
}
static void rejected_retry_cannot_clear_prior_uncertainty(void) {
    Store f={.result=SB_COMMIT_UNCERTAIN}; SbSettingsStore io={&f,commit}; SbSetup s;
    sb_setup_open(&s,initial(),SB_ALL_FIELDS); press(&s,SB_A,&io);
    press(&s,SB_X,&io); press(&s,SB_A,&io);
    f.result=SB_COMMIT_REJECTED; press(&s,SB_A,&io);
    assert(s.state==SB_MENU_RECOVERY && s.last_save==SB_COMMIT_UNCERTAIN);
    press(&s,SB_B,&io); assert(s.state==SB_MENU_RECOVERY);
    press(&s,SB_A,NULL); assert(s.state==SB_MENU_RECOVERY);
}
static void missing_writer_rejects_without_claiming_success(void) {
    SbSetup s; sb_setup_open(&s,initial(),SB_ALL_FIELDS);
    press(&s,SB_A,NULL); press(&s,SB_X,NULL); press(&s,SB_A,NULL);
    assert(s.state==SB_MENU_EDIT && s.last_save==SB_COMMIT_REJECTED);
}
static void display_is_bounded_and_unknown_values_are_visible(void) {
    SbSetup s; char b[32], tiny[2]={'!','!'};
    sb_setup_open(&s,(SbSettings){999,0x110000,3},SB_ALL_FIELDS);
    sb_setup_field_value(&s,SB_LANGUAGE,b,sizeof(b)); assert(strstr(b,"Unknown"));
    sb_setup_field_value(&s,SB_ASPECT,b,sizeof(b)); assert(strstr(b,"Unknown"));
    sb_setup_field_value(&s,SB_AUDIO_MODE,b,sizeof(b)); assert(strstr(b,"Unknown"));
    sb_setup_field_value(&s,SB_LANGUAGE,tiny,1); assert(tiny[0]==0 && tiny[1]=='!');
    sb_setup_field_value(&s,SB_LANGUAGE,NULL,0);
    assert(strcmp(sb_setup_field_label((SbSetupRow)999),"Unknown")==0);
}

static _Alignas(SB_PAGE_SIZE) unsigned char storage[2*SB_PAGE_SIZE];
typedef struct { unsigned stops, releases; bool stop_ok, release_ok; char order[8]; unsigned n; } Life;
static bool stop(void *p, void *base, size_t bytes) {
    Life *f=p; assert(base==storage && bytes==sizeof(storage));
    f->order[f->n++]='Q'; ++f->stops; return f->stop_ok;
}
static bool release(void *p, void *base, size_t bytes) {
    Life *f=p; unsigned char *b=base;
    for (size_t i=0;i<bytes;i++) assert(b[i]==0);
    f->order[f->n++]='R'; ++f->releases; return f->release_ok;
}
static SbBootArena arena(void) {
    memset(storage,0xa5,sizeof(storage));
    return (SbBootArena){storage,sizeof(storage),SB_ARENA_LIVE};
}
static void retirement_quiesces_scrubs_then_releases(void) {
    Life f={.stop_ok=true,.release_ok=true}; SbArenaOps ops={&f,stop,release};
    SbBootArena a=arena(); assert(sb_boot_arena_retire(&a,&ops));
    assert(strcmp(f.order,"QR")==0 && a.base==NULL && a.bytes==0 && a.state==SB_ARENA_RELEASED);
    assert(sb_boot_arena_retire(&a,NULL) && f.stops==1 && f.releases==1);
}
static void failed_quiesce_does_not_clear_or_free_memory(void) {
    Life f={.release_ok=true}; SbArenaOps ops={&f,stop,release}; SbBootArena a=arena();
    assert(!sb_boot_arena_retire(&a,&ops) && f.releases==0 && a.state==SB_ARENA_LIVE);
    for (size_t i=0;i<sizeof(storage);i++) assert(storage[i]==0xa5);
}
static void failed_release_retries_without_calling_retired_code(void) {
    Life f={.stop_ok=true}; SbArenaOps ops={&f,stop,release}; SbBootArena a=arena();
    assert(!sb_boot_arena_retire(&a,&ops));
    assert(a.state==SB_ARENA_SCRUBBED && a.base==storage && f.stops==1);
    f.release_ok=true; assert(sb_boot_arena_retire(&a,&ops));
    assert(f.stops==1 && f.releases==2 && strcmp(f.order,"QRR")==0);
}
static void invalid_arena_ranges_are_rejected_before_callbacks(void) {
    Life f={.stop_ok=true,.release_ok=true}; SbArenaOps ops={&f,stop,release}; SbBootArena a=arena();
    a.bytes--; assert(!sb_boot_arena_retire(&a,&ops));
    a=arena(); a.base=storage+1; assert(!sb_boot_arena_retire(&a,&ops));
    a=arena(); a.base=(void *)(UINTPTR_MAX-(SB_PAGE_SIZE-1));
    assert(!sb_boot_arena_retire(&a,&ops));
    a=arena(); a.state=(SbArenaState)99; assert(!sb_boot_arena_retire(&a,&ops));
    assert(!sb_boot_arena_retire(NULL,&ops)); assert(f.stops==0 && f.releases==0);
}
static void descriptor_and_callback_context_cannot_be_retired(void) {
    Life f={.stop_ok=true,.release_ok=true}; SbArenaOps ops={&f,stop,release}; SbBootArena a=arena();
    SbBootArena *inside=(void *)storage; *inside=a;
    assert(!sb_boot_arena_retire(inside,&ops));
    a=arena(); ops.context=storage; assert(!sb_boot_arena_retire(&a,&ops));
    ops.context=&f; SbArenaOps *inside_ops=(void *)storage; *inside_ops=ops;
    assert(!sb_boot_arena_retire(&a,inside_ops)); assert(f.stops==0 && f.releases==0);
}
int main(void) {
    puts("TAP version 13");
    RUN(held_at_boot); RUN(short_presses_do_not_accumulate);
    RUN(disconnected_input_restarts_hold); RUN(different_controllers_cannot_share_hold);
    RUN(stale_report_gap_restarts_hold); RUN(missing_input_has_bounded_timeout);
    RUN(late_hold_cannot_extend_boot_window); RUN(gate_clock_wrap_is_supported);
    RUN(backward_clock_does_not_enter_menu); RUN(exact_sample_gap_is_allowed);
    RUN(menu_starts_without_mutation); RUN(entry_button_must_be_released);
    RUN(reconnect_requires_neutral_report); RUN(changing_device_without_disconnect_requires_release);
    RUN(language_wrap_and_unknown_value); RUN(video_edit_preserves_unknown_bits);
    RUN(aspect_modes_are_mutually_exclusive); RUN(audio_edit_preserves_unknown_bits);
    RUN(unavailable_fields_cannot_be_changed); RUN(conflicting_buttons_are_ignored);
    RUN(clean_continue_never_calls_writer); RUN(dirty_discard_needs_confirmation_and_never_writes);
    RUN(save_requires_second_press_and_verified_result); RUN(no_change_save_performs_no_write);
    RUN(rejected_commit_can_be_cancelled); RUN(uncertain_commit_blocks_continue_and_edits);
    RUN(rejected_retry_cannot_clear_prior_uncertainty); RUN(missing_writer_rejects_without_claiming_success); RUN(display_is_bounded_and_unknown_values_are_visible);
    RUN(retirement_quiesces_scrubs_then_releases); RUN(failed_quiesce_does_not_clear_or_free_memory);
    RUN(failed_release_retries_without_calling_retired_code); RUN(invalid_arena_ranges_are_rejected_before_callbacks);
    RUN(descriptor_and_callback_context_cannot_be_retired);
    printf("1..%u\n",tests);
    printf("# state bytes: gate=%zu menu=%zu arena=%zu\n",sizeof(SbBootGate),sizeof(SbSetup),sizeof(SbBootArena));
    return 0;
}
