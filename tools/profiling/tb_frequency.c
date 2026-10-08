/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Optional QEMU plugin: bounded single-vCPU Xbox TB-entry counters. */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <glib.h>
#include <qemu-plugin.h>

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

typedef struct Record {
    uint64_t pc;
    size_t instructions;
    uint64_t translations;
    char digest[65];
    struct qemu_plugin_scoreboard *executions;
} Record;

static GMutex lock;
static GHashTable *records;
static FILE *output;
static size_t max_records = 65536;
static uint64_t dropped;
static struct qemu_plugin_scoreboard *untracked, *untracked_weight;

static guint record_hash(gconstpointer data)
{
    const Record *r = data;
    return g_str_hash(r->digest) ^ (guint)r->pc;
}

static gboolean record_equal(gconstpointer a, gconstpointer b)
{
    const Record *x = a, *y = b;
    return x->pc == y->pc && x->instructions == y->instructions &&
           strcmp(x->digest, y->digest) == 0;
}

static void record_free(gpointer data)
{
    Record *r = data;
    qemu_plugin_scoreboard_free(r->executions);
    g_free(r);
}

static void translate(qemu_plugin_id_t id, struct qemu_plugin_tb *tb)
{
    Record key = { .pc = qemu_plugin_tb_vaddr(tb),
                   .instructions = qemu_plugin_tb_n_insns(tb) };
    GChecksum *sum = g_checksum_new(G_CHECKSUM_SHA256);
    Record *record;

    /* Translation-only hashing distinguishes modified code at a reused PC.
     * Execution uses one inline increment, without a plugin callback or I/O.
     */
    for (size_t i = 0; i < key.instructions; i++) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        uint8_t bytes[15]; /* Maximum i386 instruction length. */
        size_t size = qemu_plugin_insn_size(insn);
        uint8_t length = size;
        if (!size || size > sizeof(bytes) ||
            qemu_plugin_insn_data(insn, bytes, size) != size) {
            g_checksum_free(sum);
            abort(); /* Never silently combine identities with missing bytes. */
        }
        g_checksum_update(sum, &length, 1);
        g_checksum_update(sum, bytes, size);
    }
    g_strlcpy(key.digest, g_checksum_get_string(sum), sizeof(key.digest));
    g_checksum_free(sum);

    g_mutex_lock(&lock);
    record = g_hash_table_lookup(records, &key);
    if (record) {
        record->translations++;
    } else if (g_hash_table_size(records) < max_records) {
        record = g_new0(Record, 1);
        *record = key;
        record->translations = 1;
        record->executions = qemu_plugin_scoreboard_new(sizeof(uint64_t));
        g_hash_table_add(records, record);
    } else {
        dropped++;
    }
    g_mutex_unlock(&lock);

    qemu_plugin_register_vcpu_tb_exec_inline_per_vcpu(
        tb, QEMU_PLUGIN_INLINE_ADD_U64,
        qemu_plugin_scoreboard_u64(record ? record->executions : untracked), 1);
    if (!record) {
        qemu_plugin_register_vcpu_tb_exec_inline_per_vcpu(
            tb, QEMU_PLUGIN_INLINE_ADD_U64,
            qemu_plugin_scoreboard_u64(untracked_weight), key.instructions);
    }
}

static void finish(qemu_plugin_id_t id, void *userdata)
{
    GHashTableIter iterator;
    gpointer data;
    g_hash_table_iter_init(&iterator, records);
    while (g_hash_table_iter_next(&iterator, &data, NULL)) {
        Record *r = data;
        fprintf(output, "{\"type\":\"tb\",\"pc\":\"0x%08" PRIx64 "\","
                "\"code_sha256\":\"%s\",\"instructions\":%zu,"
                "\"translations\":%" PRIu64 ",\"executions\":%" PRIu64 "}\n",
                r->pc, r->digest, r->instructions, r->translations,
                qemu_plugin_u64_sum(qemu_plugin_scoreboard_u64(r->executions)));
    }
    if (!ferror(output)) {
        fprintf(output, "{\"type\":\"complete\",\"dropped_translations\":%"
                PRIu64 ",\"untracked_executions\":%" PRIu64
                ",\"untracked_weight\":%" PRIu64 "}\n", dropped,
                qemu_plugin_u64_sum(qemu_plugin_scoreboard_u64(untracked)),
                qemu_plugin_u64_sum(qemu_plugin_scoreboard_u64(untracked_weight)));
    }
    if (fclose(output)) {
        fprintf(stderr, "SpiritBoot TB profile write failed: %s\n", strerror(errno));
    }
    g_hash_table_destroy(records);
    qemu_plugin_scoreboard_free(untracked);
    qemu_plugin_scoreboard_free(untracked_weight);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                          const qemu_info_t *info,
                                          int argc, char **argv)
{
    const char *path = NULL;
    bool have_limit = false;
    if (!info->system_emulation || strcmp(info->target_name, "i386") ||
        info->system.max_vcpus != 1) {
        fprintf(stderr, "SpiritBoot profiling requires single-vCPU i386 system emulation\n");
        return -1;
    }
    for (int i = 0; i < argc; i++) {
        if (g_str_has_prefix(argv[i], "output=") && !path) {
            path = argv[i] + strlen("output=");
        } else if (g_str_has_prefix(argv[i], "max_records=") && !have_limit) {
            const char *value = argv[i] + strlen("max_records=");
            char *end;
            errno = 0;
            uint64_t number = g_ascii_strtoull(value, &end, 10);
            if (!g_ascii_isdigit(*value) || *end || errno ||
                number < 1 || number > 131072) {
                return -1;
            }
            max_records = number;
            have_limit = true;
        } else {
            return -1;
        }
    }
    if (!path || !*path || !(output = fopen(path, "wx"))) {
        fprintf(stderr, "SpiritBoot profiling requires a new writable output file\n");
        return -1;
    }
    fprintf(output, "{\"type\":\"header\",\"schema\":1,\"max_records\":%zu}\n",
            max_records);
    fflush(output);
    records = g_hash_table_new_full(record_hash, record_equal, record_free, NULL);
    untracked = qemu_plugin_scoreboard_new(sizeof(uint64_t));
    untracked_weight = qemu_plugin_scoreboard_new(sizeof(uint64_t));
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate);
    qemu_plugin_register_atexit_cb(id, finish, NULL);
    return 0;
}
