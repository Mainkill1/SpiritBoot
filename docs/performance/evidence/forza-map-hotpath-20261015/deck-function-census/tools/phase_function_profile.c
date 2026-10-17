/* SPDX-License-Identifier: GPL-2.0-or-later
 * Diagnostic-only phase-bounded guest function/TB census. */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <glib.h>
#include <qemu-plugin.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

typedef struct Entry {
    uint64_t pc;
    char *label;
    uint64_t hits;
    uint64_t tb_executions;
    uint64_t weighted_instructions;
    uint64_t attributed_thread_cpu_ns;
} Entry;

typedef struct TbInfo {
    Entry *entry;
    uint64_t instructions;
} TbInfo;

static GPtrArray *entries;
static GHashTable *by_pc;
static FILE *output;
static struct qemu_plugin_scoreboard *active;
static uint64_t begin_pc, end_pc;
static unsigned completed_windows;
static uint64_t callbacks;
static uint64_t kernel_callbacks;
static uint64_t clock_errors;
static Entry *previous_entry;
static uint64_t previous_cpu_ns;
static gboolean previous_cpu_valid;
static uint64_t start_mono_ns, end_mono_ns;
static uint64_t start_cpu_ns, end_cpu_ns;

static gboolean clock_ns(clockid_t id, uint64_t *value)
{
    struct timespec ts;
    if (clock_gettime(id, &ts)) {
        clock_errors++;
        return false;
    }
    *value = (uint64_t)ts.tv_sec * UINT64_C(1000000000) + ts.tv_nsec;
    return true;
}

static void entry_free(gpointer opaque)
{
    Entry *e = opaque;
    g_free(e->label);
    g_free(e);
}

static gboolean load_entries(const char *path)
{
    gchar *contents = NULL;
    gchar **lines = NULL;
    GError *error = NULL;
    uint64_t previous = 0;
    if (!g_file_get_contents(path, &contents, NULL, &error)) {
        fprintf(stderr, "phase-profile: cannot read %s: %s\n", path,
                error ? error->message : "unknown error");
        g_clear_error(&error);
        return false;
    }
    lines = g_strsplit(contents, "\n", -1);
    for (size_t i = 0; lines[i]; i++) {
        gchar **fields;
        char *end;
        uint64_t pc;
        Entry *e;
        g_strstrip(lines[i]);
        if (!lines[i][0] || lines[i][0] == '#') {
            continue;
        }
        fields = g_strsplit_set(lines[i], " \t", 2);
        errno = 0;
        pc = g_ascii_strtoull(fields[0], &end, 0);
        if (errno || *end || !fields[1] || !fields[1][0] ||
            pc > UINT32_MAX || (entries->len && pc <= previous)) {
            fprintf(stderr, "phase-profile: invalid entry line %zu\n", i + 1);
            g_strfreev(fields);
            g_strfreev(lines);
            g_free(contents);
            return false;
        }
        e = g_new0(Entry, 1);
        e->pc = pc;
        e->label = g_strdup(g_strstrip(fields[1]));
        g_ptr_array_add(entries, e);
        g_hash_table_insert(by_pc, (gpointer)(uintptr_t)pc, e);
        previous = pc;
        g_strfreev(fields);
    }
    g_strfreev(lines);
    g_free(contents);
    return entries->len > 0;
}

static Entry *entry_containing(uint64_t pc)
{
    size_t lo = 0, hi = entries->len;
    Entry *first = g_ptr_array_index(entries, 0);
    if (pc < first->pc || pc >= UINT64_C(0x84080000)) {
        return NULL;
    }
    while (lo < hi) {
        size_t mid = lo + (hi - lo) / 2;
        Entry *e = g_ptr_array_index(entries, mid);
        if (e->pc <= pc) {
            lo = mid + 1;
        } else {
            hi = mid;
        }
    }
    return lo ? g_ptr_array_index(entries, lo - 1) : NULL;
}

static void close_cpu_interval(uint64_t now, gboolean valid)
{
    if (previous_entry && previous_cpu_valid && valid && now >= previous_cpu_ns) {
        previous_entry->attributed_thread_cpu_ns += now - previous_cpu_ns;
    }
    previous_cpu_ns = now;
    previous_cpu_valid = valid;
}

static void begin_phase(unsigned int vcpu_index, void *opaque)
{
    uint64_t cpu = 0, mono = 0;
    gboolean valid;
    (void)opaque;
    if (completed_windows || qemu_plugin_u64_get(
            qemu_plugin_scoreboard_u64(active), vcpu_index)) {
        return;
    }
    valid = clock_ns(CLOCK_THREAD_CPUTIME_ID, &cpu);
    clock_ns(CLOCK_MONOTONIC_RAW, &mono);
    previous_entry = NULL;
    previous_cpu_ns = cpu;
    previous_cpu_valid = valid;
    start_cpu_ns = cpu;
    start_mono_ns = mono;
    qemu_plugin_u64_set(qemu_plugin_scoreboard_u64(active), vcpu_index, 1);
    fprintf(output, "{\"type\":\"phase_start\",\"window\":1,"
            "\"monotonic_raw_ns\":%" PRIu64 ",\"thread_cpu_ns\":%" PRIu64 "}\n",
            mono, cpu);
    fflush(output);
}

static void end_phase(unsigned int vcpu_index, void *opaque)
{
    uint64_t cpu = 0, mono = 0;
    gboolean valid;
    (void)opaque;
    if (!qemu_plugin_u64_get(qemu_plugin_scoreboard_u64(active), vcpu_index)) {
        return;
    }
    valid = clock_ns(CLOCK_THREAD_CPUTIME_ID, &cpu);
    clock_ns(CLOCK_MONOTONIC_RAW, &mono);
    close_cpu_interval(cpu, valid);
    previous_entry = NULL;
    qemu_plugin_u64_set(qemu_plugin_scoreboard_u64(active), vcpu_index, 0);
    completed_windows = 1;
    end_cpu_ns = cpu;
    end_mono_ns = mono;
    fprintf(output, "{\"type\":\"phase_end\",\"window\":1,"
            "\"monotonic_raw_ns\":%" PRIu64 ",\"thread_cpu_ns\":%" PRIu64 "}\n",
            mono, cpu);
    fflush(output);
}

static void tb_exec(unsigned int vcpu_index, void *opaque)
{
    TbInfo *info = opaque;
    uint64_t now = 0;
    gboolean valid = clock_ns(CLOCK_THREAD_CPUTIME_ID, &now);
    (void)vcpu_index;
    close_cpu_interval(now, valid);
    previous_entry = info->entry;
    callbacks++;
    if (info->entry) {
        info->entry->tb_executions++;
        info->entry->weighted_instructions += info->instructions;
        kernel_callbacks++;
    }
}

static void entry_hit(unsigned int vcpu_index, void *opaque)
{
    Entry *e = opaque;
    (void)vcpu_index;
    e->hits++;
}

static void translate(qemu_plugin_id_t id, struct qemu_plugin_tb *tb)
{
    size_t n = qemu_plugin_tb_n_insns(tb);
    TbInfo *info;
    (void)id;
    if (!n) {
        return;
    }
    info = g_new0(TbInfo, 1);
    info->entry = entry_containing(qemu_plugin_tb_vaddr(tb));
    info->instructions = n;
    qemu_plugin_register_vcpu_tb_exec_cond_cb(
        tb, tb_exec, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_COND_GT,
        qemu_plugin_scoreboard_u64(active), 0, info);
    for (size_t i = 0; i < n; i++) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        uint64_t pc = qemu_plugin_insn_vaddr(insn);
        Entry *e = g_hash_table_lookup(by_pc, (gpointer)(uintptr_t)pc);
        if (e) {
            qemu_plugin_register_vcpu_insn_exec_cond_cb(
                insn, entry_hit, QEMU_PLUGIN_CB_NO_REGS, QEMU_PLUGIN_COND_GT,
                qemu_plugin_scoreboard_u64(active), 0, e);
        }
        if (pc == begin_pc) {
            qemu_plugin_register_vcpu_insn_exec_cb(
                insn, begin_phase, QEMU_PLUGIN_CB_NO_REGS, NULL);
        }
        if (pc == end_pc) {
            qemu_plugin_register_vcpu_insn_exec_cb(
                insn, end_phase, QEMU_PLUGIN_CB_NO_REGS, NULL);
        }
    }
}

static void finish(qemu_plugin_id_t id, void *opaque)
{
    (void)id;
    (void)opaque;
    for (size_t i = 0; i < entries->len; i++) {
        Entry *e = g_ptr_array_index(entries, i);
        if (!e->hits && !e->tb_executions) {
            continue;
        }
        fprintf(output, "{\"type\":\"entry\",\"pc\":\"0x%08" PRIx64
                "\",\"label\":\"%s\",\"hits\":%" PRIu64
                ",\"tb_executions\":%" PRIu64
                ",\"weighted_instructions\":%" PRIu64
                ",\"attributed_thread_cpu_ns\":%" PRIu64 "}\n",
                e->pc, e->label, e->hits, e->tb_executions,
                e->weighted_instructions, e->attributed_thread_cpu_ns);
    }
    fprintf(output, "{\"type\":\"complete\",\"entries\":%u,"
            "\"completed_windows\":%u,\"callbacks\":%" PRIu64
            ",\"kernel_callbacks\":%" PRIu64
            ",\"clock_errors\":%" PRIu64
            ",\"phase_wall_ns\":%" PRIu64
            ",\"phase_thread_cpu_ns\":%" PRIu64 "}\n",
            entries->len, completed_windows, callbacks, kernel_callbacks,
            clock_errors, end_mono_ns >= start_mono_ns ? end_mono_ns - start_mono_ns : 0,
            end_cpu_ns >= start_cpu_ns ? end_cpu_ns - start_cpu_ns : 0);
    fclose(output);
    qemu_plugin_scoreboard_free(active);
    g_hash_table_destroy(by_pc);
    g_ptr_array_free(entries, true);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                          const qemu_info_t *info,
                                          int argc, char **argv)
{
    const char *entry_path = NULL;
    const char *output_path = NULL;
    for (int i = 0; i < argc; i++) {
        if (g_str_has_prefix(argv[i], "entries=") && !entry_path) {
            entry_path = argv[i] + strlen("entries=");
        } else if (g_str_has_prefix(argv[i], "output=") && !output_path) {
            output_path = argv[i] + strlen("output=");
        } else if (g_str_has_prefix(argv[i], "begin=") && !begin_pc) {
            begin_pc = g_ascii_strtoull(argv[i] + strlen("begin="), NULL, 0);
        } else if (g_str_has_prefix(argv[i], "end=") && !end_pc) {
            end_pc = g_ascii_strtoull(argv[i] + strlen("end="), NULL, 0);
        } else {
            return -1;
        }
    }
    if (!entry_path || !output_path || !begin_pc || !end_pc ||
        !info->system_emulation || strcmp(info->target_name, "i386") ||
        info->system.max_vcpus != 1) {
        return -1;
    }
    output = fopen(output_path, "wx");
    if (!output) {
        return -1;
    }
    entries = g_ptr_array_new_with_free_func(entry_free);
    by_pc = g_hash_table_new(g_direct_hash, g_direct_equal);
    if (!load_entries(entry_path)) {
        fclose(output);
        g_hash_table_destroy(by_pc);
        g_ptr_array_free(entries, true);
        return -1;
    }
    active = qemu_plugin_scoreboard_new(sizeof(uint64_t));
    fprintf(output, "{\"type\":\"header\",\"schema\":1,"
            "\"scope\":\"first marker-bounded 1024-request measured phase\","
            "\"entries\":%u,\"begin\":\"0x%08" PRIx64
            "\",\"end\":\"0x%08" PRIx64 "\"}\n",
            entries->len, begin_pc, end_pc);
    fflush(output);
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate);
    qemu_plugin_register_atexit_cb(id, finish, NULL);
    return 0;
}
