/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Diagnostic scalar transcriber. Eligibility lives in the Rust model. */
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <glib.h>
#include <qemu-plugin.h>
#ifdef _WIN32
#include <windows.h>
#endif

QEMU_PLUGIN_EXPORT int qemu_plugin_version = QEMU_PLUGIN_VERSION;

#ifdef _WIN32
#define HOST_API_LIST(X) \
    X(qemu_plugin_get_registers) \
    X(qemu_plugin_insn_vaddr) \
    X(qemu_plugin_read_memory_vaddr) \
    X(qemu_plugin_read_register) \
    X(qemu_plugin_register_atexit_cb) \
    X(qemu_plugin_register_vcpu_insn_exec_cb) \
    X(qemu_plugin_register_vcpu_tb_trans_cb) \
    X(qemu_plugin_tb_get_insn) \
    X(qemu_plugin_tb_n_insns)
#define DECLARE_HOST_API(name) static __typeof__(&name) host_##name;
HOST_API_LIST(DECLARE_HOST_API)

static gboolean resolve_host_api(void)
{
    HMODULE host = GetModuleHandleW(NULL);
    if (!host) {
        return false;
    }
#define RESOLVE_HOST_API(name) do { \
        host_##name = (__typeof__(host_##name))GetProcAddress(host, #name); \
        if (!host_##name) { \
            fprintf(stderr, "xdvdfs-trace: missing host API %s\n", #name); \
            return false; \
        } \
    } while (0);
    HOST_API_LIST(RESOLVE_HOST_API)
#undef RESOLVE_HOST_API
    return true;
}

#define qemu_plugin_get_registers host_qemu_plugin_get_registers
#define qemu_plugin_insn_vaddr host_qemu_plugin_insn_vaddr
#define qemu_plugin_read_memory_vaddr host_qemu_plugin_read_memory_vaddr
#define qemu_plugin_read_register host_qemu_plugin_read_register
#define qemu_plugin_register_atexit_cb host_qemu_plugin_register_atexit_cb
#define qemu_plugin_register_vcpu_insn_exec_cb host_qemu_plugin_register_vcpu_insn_exec_cb
#define qemu_plugin_register_vcpu_tb_trans_cb host_qemu_plugin_register_vcpu_tb_trans_cb
#define qemu_plugin_tb_get_insn host_qemu_plugin_tb_get_insn
#define qemu_plugin_tb_n_insns host_qemu_plugin_tb_n_insns
#else
static gboolean resolve_host_api(void)
{
    return true;
}
#endif

enum {
    IRP_NOCACHE = 0x00000001,
    IRP_PAGING_IO = 0x00000002,
    IRP_ASSOCIATED_IRP = 0x00000008,
    MDL_MAPPED_TO_SYSTEM_VA = 0x0001,
    MDL_PAGES_LOCKED = 0x0002,
    MDL_SOURCE_IS_NONPAGED_POOL = 0x0004,
    MDL_HEADER_BYTES = 28,
    PAGE_BYTES = 4096,
};

static struct qemu_plugin_register *esp_register;
static FILE *trace_output;
static const char *report_path;
static uint64_t dispatch_pc;
static uint64_t accepted;
static uint64_t rejected;
static uint64_t callbacks;
static gboolean init_failed;

static gboolean read_bytes(uint32_t address, void *output, size_t size)
{
    g_autoptr(GByteArray) data = g_byte_array_new();
    if (!size || !qemu_plugin_read_memory_vaddr(address, data, size) ||
        data->len != size) {
        return false;
    }
    memcpy(output, data->data, size);
    return true;
}

static gboolean read_u8(uint32_t address, uint8_t *value)
{
    return read_bytes(address, value, sizeof(*value));
}

static gboolean read_u16(uint32_t address, uint16_t *value)
{
    uint8_t data[2];
    if (!read_bytes(address, data, sizeof(data))) {
        return false;
    }
    *value = (uint16_t)data[0] | (uint16_t)data[1] << 8;
    return true;
}

static gboolean read_u32(uint32_t address, uint32_t *value)
{
    uint8_t data[4];
    if (!read_bytes(address, data, sizeof(data))) {
        return false;
    }
    *value = (uint32_t)data[0] | (uint32_t)data[1] << 8 |
             (uint32_t)data[2] << 16 | (uint32_t)data[3] << 24;
    return true;
}

static gboolean read_u64(uint32_t address, uint64_t *value)
{
    uint8_t data[8];
    if (!read_bytes(address, data, sizeof(data))) {
        return false;
    }
    *value = 0;
    for (unsigned int i = 0; i < sizeof(data); i++) {
        *value |= (uint64_t)data[i] << (i * 8);
    }
    return true;
}

static gboolean kernel_pointer(uint32_t value)
{
    return value >= UINT32_C(0x80000000) && !(value & 3);
}

static gboolean add_u32(uint32_t base, uint32_t offset, uint32_t *result)
{
    if (UINT32_MAX - base < offset) {
        return false;
    }
    *result = base + offset;
    return true;
}

static gboolean field_u8(uint32_t base, uint32_t offset, uint8_t *value)
{
    uint32_t address;
    return add_u32(base, offset, &address) && read_u8(address, value);
}

static gboolean field_u16(uint32_t base, uint32_t offset, uint16_t *value)
{
    uint32_t address;
    return add_u32(base, offset, &address) && read_u16(address, value);
}

static gboolean field_u32(uint32_t base, uint32_t offset, uint32_t *value)
{
    uint32_t address;
    return add_u32(base, offset, &address) && read_u32(address, value);
}

static gboolean field_u64(uint32_t base, uint32_t offset, uint64_t *value)
{
    uint32_t address;
    return add_u32(base, offset, &address) && read_u64(address, value);
}

static gboolean read_esp(uint32_t *esp)
{
    g_autoptr(GByteArray) data = g_byte_array_new();
    if (!esp_register || qemu_plugin_read_register(esp_register, data) != 4 ||
        data->len != 4) {
        return false;
    }
    *esp = (uint32_t)data->data[0] | (uint32_t)data->data[1] << 8 |
           (uint32_t)data->data[2] << 16 | (uint32_t)data->data[3] << 24;
    return true;
}

static gboolean find_esp(void)
{
    g_autoptr(GArray) registers = qemu_plugin_get_registers();
    if (!registers) {
        return false;
    }
    for (guint i = 0; i < registers->len; i++) {
        qemu_plugin_reg_descriptor *descriptor = &g_array_index(
            registers, qemu_plugin_reg_descriptor, i);
        if (!strcmp(descriptor->name, "esp")) {
            esp_register = descriptor->handle;
            return true;
        }
    }
    return false;
}

static void capture(unsigned int vcpu_index, void *opaque)
{
    uint32_t esp, irp, flags, stack, file, fcb, vcb, target, mdl;
    uint32_t requested, file_bytes, file_sector, alignment, next;
    uint32_t mapped, start, mdl_bytes, mdl_offset, data_address;
    uint8_t stack_count, current_location, is_directory;
    uint16_t mdl_size, mdl_flags;
    uint64_t file_offset_bits, span, pages, required_size;
    (void)vcpu_index;
    (void)opaque;
    callbacks++;

    if (!esp_register && !find_esp()) {
        init_failed = true;
        rejected++;
        return;
    }
    if (!read_esp(&esp) || !kernel_pointer(esp) ||
        !field_u32(esp, 8, &irp) || !kernel_pointer(irp) ||
        !field_u32(irp, 4, &flags) ||
        !field_u8(irp, 0x18, &stack_count) ||
        !field_u8(irp, 0x19, &current_location) || !stack_count ||
        !current_location || current_location > stack_count ||
        !field_u32(irp, 0x5c, &stack) || !kernel_pointer(stack) ||
        !field_u32(stack, 4, &requested) ||
        !field_u64(stack, 0x0c, &file_offset_bits) ||
        !field_u32(stack, 0x18, &file) || !kernel_pointer(file) ||
        !field_u32(file, 8, &fcb) || !kernel_pointer(fcb) ||
        !field_u32(fcb, 0, &vcb) || !kernel_pointer(vcb) ||
        !field_u32(fcb, 4, &file_sector) ||
        !field_u32(fcb, 8, &file_bytes) ||
        !field_u8(fcb, 0x0d, &is_directory) || is_directory ||
        !field_u32(vcb, 0x0c, &target) || !kernel_pointer(target) ||
        !field_u32(target, 0x24, &alignment) ||
        !field_u32(irp, 0x6c, &mdl) || !kernel_pointer(mdl) ||
        !field_u32(mdl, 0, &next) || !field_u16(mdl, 4, &mdl_size) ||
        !field_u16(mdl, 6, &mdl_flags) ||
        !field_u32(mdl, 0x0c, &mapped) ||
        !field_u32(mdl, 0x10, &start) ||
        !field_u32(mdl, 0x14, &mdl_bytes) ||
        !field_u32(mdl, 0x18, &mdl_offset)) {
        rejected++;
        return;
    }
    span = (uint64_t)mdl_offset + mdl_bytes;
    pages = (span + PAGE_BYTES - 1) / PAGE_BYTES;
    required_size = MDL_HEADER_BYTES + pages * 4;
    if (mdl_flags & (MDL_MAPPED_TO_SYSTEM_VA | MDL_SOURCE_IS_NONPAGED_POOL)) {
        data_address = mapped;
    } else if (UINT32_MAX - start >= mdl_offset) {
        data_address = start + mdl_offset;
    } else {
        rejected++;
        return;
    }

    fprintf(trace_output,
            "file\t%" PRId64 "\t%" PRIu32 "\t%" PRIu32 "\t%" PRIu32
            "\t%u\t%u\t%u\t%" PRIu32 "\t%" PRIu32 "\t%u\t1\t%u\t%u\t%u"
            "\t%" PRIu32 "\n",
            (int64_t)file_offset_bits, requested, file_bytes, file_sector,
            !!(flags & IRP_PAGING_IO), !!(flags & IRP_ASSOCIATED_IRP),
            !!(flags & IRP_NOCACHE), data_address, alignment,
            current_location > 1, next != 0,
            !!(mdl_flags & (MDL_PAGES_LOCKED | MDL_SOURCE_IS_NONPAGED_POOL)),
            (uint64_t)mdl_size >= required_size, mdl_bytes);
    accepted++;
    if (!(accepted & 63)) {
        fflush(trace_output);
    }
}

static void translate(qemu_plugin_id_t id, struct qemu_plugin_tb *tb)
{
    size_t count = qemu_plugin_tb_n_insns(tb);
    (void)id;
    for (size_t i = 0; i < count; i++) {
        struct qemu_plugin_insn *insn = qemu_plugin_tb_get_insn(tb, i);
        if (qemu_plugin_insn_vaddr(insn) == dispatch_pc) {
            qemu_plugin_register_vcpu_insn_exec_cb(
                insn, capture, QEMU_PLUGIN_CB_R_REGS, NULL);
        }
    }
}

static void finish(qemu_plugin_id_t id, void *opaque)
{
    FILE *report;
    (void)id;
    (void)opaque;
    if (trace_output && fclose(trace_output)) {
        rejected++;
    }
    report = fopen(report_path, "w");
    if (!report) {
        fprintf(stderr, "xdvdfs-trace: cannot create report: %s\n",
                strerror(errno));
        return;
    }
    fprintf(report,
            "{\"schema\":1,\"pc\":\"0x%08" PRIx64
            "\",\"callbacks\":%" PRIu64 ",\"accepted\":%" PRIu64
            ",\"rejected\":%" PRIu64 ",\"register_init_failed\":%s}\n",
            dispatch_pc, callbacks, accepted, rejected,
            init_failed ? "true" : "false");
    fclose(report);
}

QEMU_PLUGIN_EXPORT int qemu_plugin_install(qemu_plugin_id_t id,
                                          const qemu_info_t *info,
                                          int argc, char **argv)
{
    const char *output_path = NULL;
    char *end;
    for (int i = 0; i < argc; i++) {
        if (g_str_has_prefix(argv[i], "output=") && !output_path) {
            output_path = argv[i] + strlen("output=");
        } else if (g_str_has_prefix(argv[i], "report=") && !report_path) {
            report_path = argv[i] + strlen("report=");
        } else if (g_str_has_prefix(argv[i], "pc=") && !dispatch_pc) {
            errno = 0;
            dispatch_pc = g_ascii_strtoull(argv[i] + strlen("pc="), &end, 0);
            if (errno || *end) {
                return -1;
            }
        } else {
            return -1;
        }
    }
    if (!output_path || !*output_path || !report_path || !*report_path ||
        dispatch_pc > UINT32_MAX || dispatch_pc < UINT32_C(0x80000000) ||
        !resolve_host_api() || !info->system_emulation ||
        strcmp(info->target_name, "i386") || info->system.max_vcpus != 1) {
        return -1;
    }
    trace_output = fopen(output_path, "w");
    if (!trace_output) {
        return -1;
    }
    qemu_plugin_register_vcpu_tb_trans_cb(id, translate);
    qemu_plugin_register_atexit_cb(id, finish, NULL);
    return 0;
}
