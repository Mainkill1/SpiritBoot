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
    uint32_t elapsed;

    if (g->result != SB_GATE_WAIT) return g->result;
    elapsed = in.ms - g->start;
    if (elapsed >= SB_WINDOW_MS || elapsed > UINT32_MAX / 2u)
        return g->result = SB_GATE_BOOT;
    if (in.valid && (in.buttons & SB_X))
        g->result = SB_GATE_ENTER;
    return g->result;
}

/* Public Xbox setting encodings. Unknown/unedited bits must survive. */
#define WIDE 0x00010000u
#define LETTERBOX 0x00100000u
#define TEXT(name, value) static const char name[] SB_INIT_DATA = value
TEXT(label_language, "Language");
TEXT(label_shape, "Screen shape");
TEXT(label_480p, "Allow 480p");
TEXT(label_720p, "Allow 720p");
TEXT(label_1080i, "Allow 1080i");
TEXT(label_pal60, "PAL60 preference");
TEXT(label_audio, "Audio mode");
TEXT(label_ac3, "Dolby Digital (AC3)");
TEXT(label_dts, "DTS");
TEXT(label_advanced_all, "All advanced settings");
TEXT(label_contig_cache, "Advanced: contig cache");
TEXT(label_xdvdfs_async, "Optical async reads");
TEXT(label_ata_settle, "Emulator ATA acceleration");
TEXT(label_save, "Save and reboot");
TEXT(label_continue, "Discard and continue");
TEXT(text_unknown_preserved, "Unknown (preserved)");
TEXT(text_unknown, "Unknown");
TEXT(text_unavailable, "Unavailable");
TEXT(text_english, "English");
TEXT(text_japanese, "Japanese");
TEXT(text_german, "German");
TEXT(text_french, "French");
TEXT(text_spanish, "Spanish");
TEXT(text_italian, "Italian");
TEXT(text_korean, "Korean");
TEXT(text_chinese, "Chinese");
TEXT(text_portuguese, "Portuguese");
TEXT(text_normal, "Normal (4:3)");
TEXT(text_widescreen, "Widescreen");
TEXT(text_letterbox, "Letterbox");
TEXT(text_stereo, "Stereo");
TEXT(text_mono, "Mono");
TEXT(text_surround, "Surround");
TEXT(text_on, "On");
TEXT(text_off, "Off");
TEXT(text_review, "Review changes");
TEXT(text_no_changes, "No changes");
TEXT(text_no_writes, "No EEPROM writes");
TEXT(text_ata_safe, "Safe delay");
TEXT(text_ata_all, "All devices (test)");
TEXT(text_mixed, "Mixed");
#undef TEXT

static const char *const labels[SB_ROW_COUNT] SB_INIT_DATA = {
    label_language, label_shape, label_480p, label_720p, label_1080i,
    label_pal60, label_audio, label_ac3, label_dts, label_advanced_all,
    label_contig_cache,
    label_xdvdfs_async,
    label_ata_settle,
    label_save, label_continue
};
static const char *const languages[] SB_INIT_DATA = {
    text_unknown_preserved, text_english, text_japanese, text_german,
    text_french, text_spanish, text_italian, text_korean, text_chinese,
    text_portuguese
};
static const uint32_t masks[SB_FIELD_COUNT] SB_INIT_DATA = {
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

SB_INIT_CODE static uint32_t
next_value(uint32_t now, const uint32_t *values, unsigned n, int direction)
{
    for (unsigned i=0; i<n; ++i)
        if (values[i] == now)
            return values[direction > 0 ? (i+1u)%n : (i+n-1u)%n];
    return values[direction > 0 ? 0u : n-1u];
}

SB_INIT_CODE static void edit(SbSetup *s, int direction)
{
    static const uint32_t lang[] SB_INIT_DATA = {1,2,3,4,5,6,7,8,9};
    static const uint32_t aspect[] SB_INIT_DATA = {0,WIDE,LETTERBOX};
    static const uint32_t audio[] SB_INIT_DATA = {0,1,2};
    uint32_t *word, value, mask;
    if ((unsigned)s->row >= SB_FIELD_COUNT || !(s->supported & (1u << s->row))) return;
    if (s->row == SB_ADVANCED_ALL) {
        value = s->edited.experimental & SB_EXPERIMENT_ADVANCED_ALL_MASK;
        if (value == SB_EXPERIMENT_ADVANCED_ALL_MASK)
            s->edited.experimental &= ~SB_EXPERIMENT_ADVANCED_ALL_MASK;
        else
            s->edited.experimental |= SB_EXPERIMENT_ADVANCED_ALL_MASK;
        return;
    }
    if (s->row == SB_CONTIG_CACHE_ALIAS) {
        s->edited.experimental ^= SB_EXPERIMENT_CONTIG_CACHE_ALIAS;
        return;
    }
    if (s->row == SB_XDVDFS_ASYNC) {
        s->edited.experimental ^= SB_EXPERIMENT_XDVDFS_ASYNC;
        return;
    }
    if (s->row == SB_ATA_STATUS_SETTLE) {
        static const uint32_t modes[] SB_INIT_DATA = {
            0, SB_EXPERIMENT_ATA_FORCE_ALL
        };
        value = s->edited.experimental & SB_EXPERIMENT_ATA_MODE_MASK;
        value = next_value(value,modes,2,direction);
        s->edited.experimental =
            (s->edited.experimental & ~SB_EXPERIMENT_ATA_MODE_MASK) | value;
        return;
    }
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

SB_INIT_CODE static void request_save(SbSetup *s)
{
    s->state = sb_setup_changed(s) ? SB_MENU_CONFIRM_SAVE : SB_MENU_CONTINUE;
}

SB_INIT_CODE static void save(SbSetup *s, const SbSettingsStore *store)
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

SB_INIT_CODE static SbSetupRow
main_row_next(SbSetupRow row, int direction)
{
    if (direction > 0) {
        if (row < SB_DTS) return (SbSetupRow)(row + 1);
        if (row == SB_DTS) return SB_SAVE;
        if (row == SB_SAVE) return SB_CONTINUE;
        return SB_LANGUAGE;
    }
    if (row == SB_LANGUAGE) return SB_CONTINUE;
    if (row == SB_CONTINUE) return SB_SAVE;
    if (row == SB_SAVE) return SB_DTS;
    return (SbSetupRow)(row - 1);
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
    if (s->state == SB_MENU_CREDITS) {
        if (edges == SB_BACK || edges == SB_B)
            s->state = SB_MENU_EDIT;
        else if (edges == SB_UP || edges == SB_LEFT)
            s->credits_page = (uint8_t)((s->credits_page +
                                        SB_CREDITS_PAGE_COUNT - 1u) %
                                       SB_CREDITS_PAGE_COUNT);
        else if (edges == SB_DOWN || edges == SB_RIGHT)
            s->credits_page = (uint8_t)((s->credits_page + 1u) %
                                       SB_CREDITS_PAGE_COUNT);
        return;
    }
    if (s->state == SB_MENU_ADVANCED) {
        if (edges == SB_B || edges == SB_Y) {
            s->state = SB_MENU_EDIT;
            s->row = SB_LANGUAGE;
        } else if (edges == SB_UP) {
            s->row = s->row == SB_ADVANCED_ALL ? SB_ATA_STATUS_SETTLE :
                     (SbSetupRow)(s->row - 1);
        } else if (edges == SB_DOWN) {
            s->row = s->row == SB_ATA_STATUS_SETTLE ? SB_ADVANCED_ALL :
                     (SbSetupRow)(s->row + 1);
        } else if (edges == SB_LEFT || edges == SB_RIGHT || edges == SB_A) {
            edit(s,edges == SB_LEFT ? -1 : 1);
        }
        return;
    }
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
    if (edges == SB_BACK) {
        s->state = SB_MENU_CREDITS;
        s->credits_page = 0;
        return;
    }
    if (edges == SB_Y) {
        s->state = SB_MENU_ADVANCED;
        s->row = SB_ADVANCED_ALL;
    }
    else if (edges == SB_UP) s->row = main_row_next(s->row,-1);
    else if (edges == SB_DOWN) s->row = main_row_next(s->row,1);
    else if (edges == SB_B || (edges == SB_A && s->row == SB_CONTINUE))
        s->state = sb_setup_changed(s) ? SB_MENU_CONFIRM_DISCARD : SB_MENU_CONTINUE;
    else if (edges == SB_X || (edges == SB_A && s->row == SB_SAVE)) request_save(s);
    else if (edges == SB_LEFT || edges == SB_RIGHT || edges == SB_A)
        edit(s,edges == SB_LEFT ? -1 : 1);
}

const char *sb_setup_field_label(SbSetupRow row)
{
    return (unsigned)row < SB_ROW_COUNT ? labels[row] : text_unknown;
}

SB_INIT_CODE static void text_copy(char *to, size_t capacity, const char *from)
{
    size_t i=0;
    if (!to || !capacity) return;
    while (i+1u < capacity && from[i]) { to[i]=from[i]; ++i; }
    to[i]=0;
}

void sb_setup_field_value(const SbSetup *s, SbSetupRow row, char *out, size_t size)
{
    const char *text=text_unknown;
    uint32_t value;
    if ((unsigned)row < SB_FIELD_COUNT) {
        if (!(s->supported & (1u << row))) text=text_unavailable;
        else if (row == SB_LANGUAGE)
            text=languages[s->edited.language <= 9u ? s->edited.language : 0u];
        else if (row == SB_ADVANCED_ALL) {
            value = s->edited.experimental & SB_EXPERIMENT_ADVANCED_ALL_MASK;
            text = value == SB_EXPERIMENT_ADVANCED_ALL_MASK ? text_on :
                   value == 0 ? text_off : text_mixed;
        }
        else if (row == SB_CONTIG_CACHE_ALIAS)
            text=(s->edited.experimental & SB_EXPERIMENT_CONTIG_CACHE_ALIAS) ? text_on : text_off;
        else if (row == SB_XDVDFS_ASYNC)
            text=(s->edited.experimental & SB_EXPERIMENT_XDVDFS_ASYNC) ? text_on : text_off;
        else if (row == SB_ATA_STATUS_SETTLE) {
            value = s->edited.experimental & SB_EXPERIMENT_ATA_MODE_MASK;
            text = value == SB_EXPERIMENT_ATA_FORCE_ALL ? text_ata_all :
                   text_ata_safe;
        }
        else {
            value = (row < SB_AUDIO_MODE ? s->edited.video : s->edited.audio) & masks[row];
            if (row == SB_ASPECT)
                text=value==0 ? text_normal : value==WIDE ? text_widescreen :
                     value==LETTERBOX ? text_letterbox : text_unknown_preserved;
            else if (row == SB_AUDIO_MODE)
                text=value==0 ? text_stereo : value==1 ? text_mono :
                     value==2 ? text_surround : text_unknown_preserved;
            else text=value ? text_on : text_off;
        }
    } else if (row == SB_SAVE)
        text=sb_setup_changed(s) ? text_review : text_no_changes;
    else if (row == SB_CONTINUE) text=text_no_writes;
    text_copy(out,size,text);
}
