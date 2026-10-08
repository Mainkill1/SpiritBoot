/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Fake QEMU transport executes the production plugin's registered inline ops.
 * Native emulator qualification is separate from this deterministic harness.
 */
#include "../../tools/profiling/tb_frequency.c"

struct qemu_plugin_scoreboard { uint64_t value; };
struct qemu_plugin_insn { uint8_t byte; };
struct qemu_plugin_tb {
    uint64_t pc;
    struct qemu_plugin_insn insns[2];
    size_t count;
    qemu_plugin_u64 entries[2];
    uint64_t adds[2];
    size_t operations;
};
static qemu_plugin_vcpu_tb_trans_cb_t translation;
static qemu_plugin_udata_cb_t exiting;

uint64_t qemu_plugin_tb_vaddr(const struct qemu_plugin_tb *tb) { return tb->pc; }
size_t qemu_plugin_tb_n_insns(const struct qemu_plugin_tb *tb) { return tb->count; }
struct qemu_plugin_insn *qemu_plugin_tb_get_insn(const struct qemu_plugin_tb *tb, size_t i)
{ return (struct qemu_plugin_insn *)&tb->insns[i]; }
size_t qemu_plugin_insn_size(const struct qemu_plugin_insn *insn) { return 1; }
size_t qemu_plugin_insn_data(const struct qemu_plugin_insn *insn, void *data, size_t length)
{ if (length) { *(uint8_t *)data = insn->byte; return 1; } return 0; }
struct qemu_plugin_scoreboard *qemu_plugin_scoreboard_new(size_t size)
{ return g_new0(struct qemu_plugin_scoreboard, 1); }
void qemu_plugin_scoreboard_free(struct qemu_plugin_scoreboard *score) { g_free(score); }
uint64_t qemu_plugin_u64_sum(qemu_plugin_u64 entry) { return entry.score->value; }
void qemu_plugin_register_vcpu_tb_trans_cb(qemu_plugin_id_t id, qemu_plugin_vcpu_tb_trans_cb_t cb)
{ translation = cb; }
void qemu_plugin_register_atexit_cb(qemu_plugin_id_t id, qemu_plugin_udata_cb_t cb, void *data)
{ exiting = cb; }
void qemu_plugin_register_vcpu_tb_exec_inline_per_vcpu(struct qemu_plugin_tb *tb,
    enum qemu_plugin_op op, qemu_plugin_u64 entry, uint64_t add)
{
    g_assert_cmpint(op, ==, QEMU_PLUGIN_INLINE_ADD_U64);
    g_assert_cmpuint(tb->operations, <, 2);
    tb->entries[tb->operations] = entry;
    tb->adds[tb->operations++] = add;
}
static void execute(struct qemu_plugin_tb *tb, uint64_t times)
{
    tb->operations = 0;
    translation(1, tb);
    for (size_t i = 0; i < tb->operations; i++) {
        tb->entries[i].score->value += tb->adds[i] * times;
    }
}
int main(int argc, char **argv)
{
    qemu_info_t info = {.target_name = "i386", .system_emulation = true,
                        .system = {.smp_vcpus = 1, .max_vcpus = 1}};
    if (qemu_plugin_install(1, &info, argc - 1, argv + 1)) {
        return 2;
    }
    struct qemu_plugin_tb first = {.pc = 0x84001001, .insns = {{0x90}}, .count = 1};
    execute(&first, 3);
    execute(&first, 2);
    first.insns[0].byte = 0xc3;
    execute(&first, 7);
    struct qemu_plugin_tb other = {.pc = 0x10000, .insns = {{0x90}, {0xc3}}, .count = 2};
    execute(&other, 11);
    exiting(1, NULL);
    return 0;
}
