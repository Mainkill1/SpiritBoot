/* SPDX-License-Identifier: GPL-2.0-or-later
 * Disposable boot setup logic; no allocator, hardware I/O or mutable globals.
 */
#include "boot_setup.h"

void sb_boot_gate_init(SbBootGate *g, uint32_t now)
{
    *g = (SbBootGate){0};
    g->start = now;
}

SbGateResult sb_boot_gate_poll(SbBootGate *g, SbInput in)
{
    if (g->result != SB_GATE_WAIT) return g->result;
    if (in.ms - g->start >= SB_WINDOW_MS ||
        (g->sampled && in.ms - g->previous_ms > UINT32_MAX / 2u))
        return g->result = SB_GATE_BOOT;
    if (!in.valid || !(in.buttons & SB_START)) {
        g->tracking = false;
    } else {
        if (!g->tracking || in.source != g->source ||
            (g->sampled && in.ms - g->previous_ms > SB_SAMPLE_GAP_MS)) {
            g->held_at = in.ms;
            g->source = in.source;
            g->tracking = true;
        }
        if (in.ms - g->held_at >= SB_HOLD_MS)
            g->result = SB_GATE_ENTER;
    }
    g->previous_ms = in.ms;
    g->sampled = true;
    return g->result;
}

/* Public Xbox setting encodings. Unknown/unedited bits must survive. */
#define WIDE 0x00010000u
#define LETTERBOX 0x00100000u
static const char *const labels[SB_ROW_COUNT] = {
    "Language", "Screen shape", "Allow 480p", "Allow 720p", "Allow 1080i",
    "PAL60 preference", "Audio mode", "Dolby Digital (AC3)", "DTS",
    "Save and reboot", "Discard and continue"
};
static const char *const languages[] = {
    "Unknown (preserved)", "English", "Japanese", "German", "French", "Spanish",
    "Italian", "Korean", "Chinese", "Portuguese"
};
static const uint32_t masks[SB_FIELD_COUNT] = {
    0, WIDE|LETTERBOX, 0x00080000u, 0x00020000u, 0x00040000u,
    0x00400000u, 3u, 0x00010000u, 0x00020000u
};

void sb_setup_open(SbSetup *s, SbSettings initial, uint32_t supported)
{
    *s = (SbSetup){0};
    s->original = initial;
    s->edited = initial;
    s->supported = supported & SB_ALL_FIELDS;
}

uint32_t sb_setup_changed(const SbSetup *s)
{
    return (s->original.language != s->edited.language ? SB_LANGUAGE_WORD : 0u) |
           (s->original.video != s->edited.video ? SB_VIDEO_WORD : 0u) |
           (s->original.audio != s->edited.audio ? SB_AUDIO_WORD : 0u);
}

static uint32_t next_value(uint32_t now, const uint32_t *values, unsigned n, int direction)
{
    for (unsigned i=0; i<n; ++i)
        if (values[i] == now)
            return values[direction > 0 ? (i+1u)%n : (i+n-1u)%n];
    return values[direction > 0 ? 0u : n-1u];
}

static void edit(SbSetup *s, int direction)
{
    static const uint32_t lang[] = {1,2,3,4,5,6,7,8,9};
    static const uint32_t aspect[] = {0,WIDE,LETTERBOX};
    static const uint32_t audio[] = {0,1,2};
    uint32_t *word, value, mask;
    if ((unsigned)s->row >= SB_FIELD_COUNT || !(s->supported & (1u << s->row))) return;
    if (s->row == SB_LANGUAGE) {
        s->edited.language = next_value(s->edited.language,lang,9,direction);
        return;
    }
    word = s->row < SB_AUDIO_MODE ? &s->edited.video : &s->edited.audio;
    mask = masks[s->row];
    value = *word & mask;
    if (s->row == SB_ASPECT) value = next_value(value,aspect,3,direction);
    else if (s->row == SB_AUDIO_MODE) value = next_value(value,audio,3,direction);
    else value = value ? 0u : mask;
    *word = (*word & ~mask) | value;
}

static void request_save(SbSetup *s)
{
    s->state = sb_setup_changed(s) ? SB_MENU_CONFIRM_SAVE : SB_MENU_CONTINUE;
}

static void save(SbSetup *s, const SbSettingsStore *store)
{
    bool already_uncertain = s->state == SB_MENU_RECOVERY;
    s->last_save = store && store->commit ?
        store->commit(store->context,&s->original,&s->edited,sb_setup_changed(s)) :
        SB_COMMIT_REJECTED;
    if (s->last_save == SB_COMMIT_OK) s->state = SB_MENU_REBOOT;
    else if (s->last_save == SB_COMMIT_REJECTED && !already_uncertain)
        s->state = SB_MENU_EDIT;
    else {
        s->last_save = SB_COMMIT_UNCERTAIN;
        s->state = SB_MENU_RECOVERY;
    }
}

void sb_setup_input(SbSetup *s, SbInput in, const SbSettingsStore *store)
{
    uint32_t edges;
    if (s->state == SB_MENU_REBOOT || s->state == SB_MENU_CONTINUE) return;
    if (!in.valid) {
        s->armed = s->source_seen = false;
        s->previous_buttons = 0;
        return;
    }
    if (!s->source_seen || in.source != s->source) {
        s->armed = false;
        s->source_seen = true;
        s->source = in.source;
    }
    if (!s->armed) {
        if (!in.buttons) s->armed = true;
        s->previous_buttons = in.buttons;
        return;
    }
    edges = in.buttons & ~s->previous_buttons;
    s->previous_buttons = in.buttons;
    if (!edges || (edges & (edges-1u))) return;
    if (s->state == SB_MENU_RECOVERY) {
        if (edges == SB_A) save(s,store);
        return;
    }
    if (s->state == SB_MENU_CONFIRM_SAVE || s->state == SB_MENU_CONFIRM_DISCARD) {
        if (edges == SB_B) s->state = SB_MENU_EDIT;
        else if (edges == SB_A) {
            if (s->state == SB_MENU_CONFIRM_SAVE) save(s,store);
            else s->state = SB_MENU_CONTINUE;
        }
        return;
    }
    if (s->state != SB_MENU_EDIT) return;
    if (edges == SB_UP) s->row = (SbSetupRow)((s->row+SB_ROW_COUNT-1u)%SB_ROW_COUNT);
    else if (edges == SB_DOWN) s->row = (SbSetupRow)((s->row+1u)%SB_ROW_COUNT);
    else if (edges == SB_B || (edges == SB_A && s->row == SB_CONTINUE))
        s->state = sb_setup_changed(s) ? SB_MENU_CONFIRM_DISCARD : SB_MENU_CONTINUE;
    else if (edges == SB_X || (edges == SB_A && s->row == SB_SAVE)) request_save(s);
    else if (edges == SB_LEFT || edges == SB_RIGHT || edges == SB_A)
        edit(s,edges == SB_LEFT ? -1 : 1);
}

const char *sb_setup_field_label(SbSetupRow row)
{
    return (unsigned)row < SB_ROW_COUNT ? labels[row] : "Unknown";
}

static void text_copy(char *to, size_t capacity, const char *from)
{
    size_t i=0;
    if (!to || !capacity) return;
    while (i+1u < capacity && from[i]) { to[i]=from[i]; ++i; }
    to[i]=0;
}

void sb_setup_field_value(const SbSetup *s, SbSetupRow row, char *out, size_t size)
{
    const char *text="Unknown";
    uint32_t value;
    if ((unsigned)row < SB_FIELD_COUNT) {
        if (!(s->supported & (1u << row))) text="Unavailable";
        else if (row == SB_LANGUAGE)
            text=languages[s->edited.language <= 9u ? s->edited.language : 0u];
        else {
            value = (row < SB_AUDIO_MODE ? s->edited.video : s->edited.audio) & masks[row];
            if (row == SB_ASPECT)
                text=value==0 ? "Normal (4:3)" : value==WIDE ? "Widescreen" :
                     value==LETTERBOX ? "Letterbox" : "Unknown (preserved)";
            else if (row == SB_AUDIO_MODE)
                text=value==0 ? "Stereo" : value==1 ? "Mono" :
                     value==2 ? "Surround" : "Unknown (preserved)";
            else text=value ? "On" : "Off";
        }
    } else if (row == SB_SAVE) text=sb_setup_changed(s) ? "Review changes" : "No changes";
    else if (row == SB_CONTINUE) text="No EEPROM writes";
    text_copy(out,size,text);
}
