/* SPDX-License-Identifier: GPL-2.0-or-later */
#ifndef SPIRITBOOT_BOOT_SETUP_H
#define SPIRITBOOT_BOOT_SETUP_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define SB_HOLD_MS 600u
#define SB_WINDOW_MS 2000u
#define SB_SAMPLE_GAP_MS 100u
#define SB_PAGE_SIZE 4096u

/* Normalized inputs, NOT Xbox USB packet bits. Source includes device generation. */
enum { SB_START=1u, SB_UP=2u, SB_DOWN=4u, SB_LEFT=8u, SB_RIGHT=16u,
       SB_A=32u, SB_B=64u, SB_X=128u };
typedef struct { uint32_t ms, source, buttons; bool valid; } SbInput;
typedef enum { SB_GATE_WAIT, SB_GATE_ENTER, SB_GATE_BOOT } SbGateResult;
typedef struct {
    uint32_t start, held_at, previous_ms, source;
    SbGateResult result;
    bool tracking, sampled;
} SbBootGate;
void sb_boot_gate_init(SbBootGate *gate, uint32_t now);
SbGateResult sb_boot_gate_poll(SbBootGate *gate, SbInput input);

/* Only standardized setting indices 7/8/9; no factory or key material. */
typedef struct { uint32_t language, video, audio; } SbSettings;
enum { SB_LANGUAGE_WORD=1u, SB_VIDEO_WORD=2u, SB_AUDIO_WORD=4u };
typedef enum {
    SB_LANGUAGE, SB_ASPECT, SB_480P, SB_720P, SB_1080I, SB_PAL60,
    SB_AUDIO_MODE, SB_AC3, SB_DTS, SB_FIELD_COUNT,
    SB_SAVE=SB_FIELD_COUNT, SB_CONTINUE, SB_ROW_COUNT
} SbSetupRow;
#define SB_ALL_FIELDS ((1u << SB_FIELD_COUNT) - 1u)
/* OK requires durable write + independent verification. REJECTED promises no
 * mutation. Any other outcome is uncertain and prohibits ordinary title launch. */
typedef enum { SB_COMMIT_OK, SB_COMMIT_REJECTED, SB_COMMIT_UNCERTAIN } SbCommitResult;
typedef struct {
    void *context;
    SbCommitResult (*commit)(void *, const SbSettings *, const SbSettings *, uint32_t);
} SbSettingsStore;
typedef enum {
    SB_MENU_EDIT, SB_MENU_CONFIRM_SAVE, SB_MENU_CONFIRM_DISCARD,
    SB_MENU_CONTINUE, SB_MENU_REBOOT, SB_MENU_RECOVERY
} SbMenuState;
typedef struct {
    SbSettings original, edited;
    uint32_t supported, previous_buttons, source;
    SbSetupRow row;
    SbMenuState state;
    SbCommitResult last_save;
    bool armed, source_seen;
} SbSetup;
void sb_setup_open(SbSetup *setup, SbSettings initial, uint32_t supported);
void sb_setup_input(SbSetup *setup, SbInput input, const SbSettingsStore *store);
uint32_t sb_setup_changed(const SbSetup *setup);
const char *sb_setup_field_label(SbSetupRow row);
void sb_setup_field_value(const SbSetup *setup, SbSetupRow row, char *out, size_t size);

/* This descriptor, retirement code/stack, ops and release context must be
 * OUTSIDE the arena. Return from menu code before invoking the coordinator.
 * Native adapter must also retire overlay code and extra PTs, not only data. */
typedef enum { SB_ARENA_LIVE, SB_ARENA_QUIESCED, SB_ARENA_SCRUBBED,
               SB_ARENA_RELEASED } SbArenaState;
typedef struct { void *base; size_t bytes; SbArenaState state; } SbBootArena;
typedef struct {
    void *context;
    bool (*quiesce)(void *, void *, size_t); /* drain GPU/USB/DMA + detach callbacks */
    /* All-or-nothing: false retains ownership of the ENTIRE scrubbed arena;
     * true returns every page. Preflight before freeing any frame. */
    bool (*release)(void *, void *, size_t);
} SbArenaOps;
bool sb_boot_arena_retire(SbBootArena *arena, const SbArenaOps *ops);
#endif
