/* Public Xbox ABI only. Frozen leaves retain their complete original scopes.
 * Controls reset outside timing; all output and verification are outside timing. */
#include "frozen/harness.h"
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
const char *g_fail_file;
int g_fail_line;
char g_fail_what[160];
void test_record_failure(const char *file, int line, const char *fmt, ...)
{
    g_fail_file = file; g_fail_line = line;
    va_list ap; va_start(ap, fmt);
    vsnprintf(g_fail_what, sizeof(g_fail_what), fmt, ap); va_end(ap);
}
DECLARE_GROUP(io_cc_write);
DECLARE_GROUP(io_createfile);
#define PATH "\\Device\\Harddisk0\\Partition1\\write-perf.tmp"
#define ROOT "\\Device\\Harddisk0\\Partition1\\"
#define SIZE (128u * 1024u)
static unsigned char data[SIZE], readback[SIZE];
static ULONGLONG elapsed;
static NTSTATUS open_file(HANDLE *h, IO_STATUS_BLOCK *io, const char *path,
                          ULONG disposition, ULONG options, ULONG access)
{
    ANSI_STRING name = {strlen(path), strlen(path) + 1, (PCHAR)path};
    OBJECT_ATTRIBUTES oa = {NULL, &name, OBJ_CASE_INSENSITIVE};
    return IoCreateFile(h, access | SYNCHRONIZE, &oa, io, NULL,
                        FILE_ATTRIBUTE_NORMAL, FILE_SHARE_READ | FILE_SHARE_WRITE,
                        disposition, options | FILE_SYNCHRONOUS_IO_NONALERT, 0);
}
static bool remove_file(void)
{
    HANDLE h; IO_STATUS_BLOCK io;
    NTSTATUS s = open_file(&h, &io, PATH, FILE_OPEN,
        FILE_NON_DIRECTORY_FILE | FILE_DELETE_ON_CLOSE, DELETE);
    if (s == STATUS_OBJECT_NAME_NOT_FOUND || s == STATUS_OBJECT_PATH_NOT_FOUND ||
        s == (NTSTATUS)0xc000000f) return true;
    ASSERT_NTSTATUS(s, STATUS_SUCCESS);
    ASSERT_NTSTATUS(NtClose(h), STATUS_SUCCESS);
    return true;
}
static bool query_length(HANDLE h, ULONG bytes)
{
    IO_STATUS_BLOCK io; FILE_NETWORK_OPEN_INFORMATION info;
    ASSERT_NTSTATUS(NtQueryInformationFile(h, &io, &info, sizeof(info),
                    FileNetworkOpenInformation), STATUS_SUCCESS);
    ASSERT_NTSTATUS(io.Status, STATUS_SUCCESS);
    ASSERT_TRUE(info.EndOfFile.QuadPart == bytes);
    return true;
}
static bool verify(HANDLE h, ULONG bytes)
{
    IO_STATUS_BLOCK io; LARGE_INTEGER zero = {.QuadPart=0};
    if (!query_length(h, bytes)) return false;
    memset(readback, 0, sizeof(readback));
    ASSERT_NTSTATUS(NtReadFile(h, NULL, NULL, NULL, &io, readback, bytes, &zero), STATUS_SUCCESS);
    ASSERT_NTSTATUS(io.Status, STATUS_SUCCESS);
    ASSERT_EQ_U32(io.Information, bytes);
    ASSERT_TRUE(memcmp(readback, data, bytes) == 0);
    return true;
}
/* c: 0 flush; 1 write; 2 overwrite; 3 reextend; 4 parent; 5 close. */
static bool control(unsigned c)
{
    HANDLE h = NULL; IO_STATUS_BLOCK io; NTSTATUS s;
    LARGE_INTEGER zero = {.QuadPart=0};
    FILE_END_OF_FILE_INFORMATION eof = {.EndOfFile={.QuadPart=SIZE}};
    ULONG bytes = (c == 2 || c == 3) ? SIZE : 65536;
    ULONGLONG start, end;
    if (!remove_file()) return false;
    if (c == 4) {
        start = KeQueryPerformanceCounter();
        s = open_file(&h, &io, ROOT, FILE_OPEN, FILE_DIRECTORY_FILE, GENERIC_READ);
        end = KeQueryPerformanceCounter(); elapsed = end - start;
        ASSERT_NTSTATUS(s, STATUS_SUCCESS);
        ASSERT_NTSTATUS(io.Status, STATUS_SUCCESS);
        ASSERT_EQ_U32(io.Information, FILE_OPENED);
        FILE_STANDARD_INFORMATION standard;
        ASSERT_NTSTATUS(NtQueryInformationFile(h, &io, &standard, sizeof(standard),
                        FileStandardInformation), STATUS_SUCCESS);
        ASSERT_TRUE(standard.Directory);
        ASSERT_NTSTATUS(NtClose(h), STATUS_SUCCESS);
        return true;
    }
    for (unsigned i = 0; i < bytes; ++i)
        data[i] = (c == 2 || c == 3) ? (unsigned char)((i * 29u) ^ (i >> 8) ^ (i >> 16) ^ 0x5au)
            : (unsigned char)((i * 2654435761u) >> 24) ^ 0x11;
    ASSERT_NTSTATUS(open_file(&h, &io, PATH, FILE_OVERWRITE_IF,
                    FILE_NON_DIRECTORY_FILE, GENERIC_READ | GENERIC_WRITE), STATUS_SUCCESS);
    ASSERT_EQ_U32(io.Information, FILE_CREATED);
    if (c != 1) {
        ASSERT_NTSTATUS(NtWriteFile(h, NULL, NULL, NULL, &io, data, bytes, &zero), STATUS_SUCCESS);
        ASSERT_NTSTATUS(io.Status, STATUS_SUCCESS);
        ASSERT_EQ_U32(io.Information, bytes);
    }
    if (c == 2 || c == 3) {
        ASSERT_NTSTATUS(NtClose(h), STATUS_SUCCESS); h = NULL;
        if (c == 3) {
            ASSERT_NTSTATUS(open_file(&h, &io, PATH, FILE_OVERWRITE_IF,
                FILE_NON_DIRECTORY_FILE, GENERIC_READ | GENERIC_WRITE), STATUS_SUCCESS);
            ASSERT_EQ_U32(io.Information, FILE_OVERWRITTEN);
            if (!query_length(h, 0)) return false;
        }
    }
    start = KeQueryPerformanceCounter();
    switch (c) {
    case 0: s = NtFlushBuffersFile(h, &io); break;
    case 1: s = NtWriteFile(h, NULL, NULL, NULL, &io, data, bytes, &zero); break;
    case 2: s = open_file(&h, &io, PATH, FILE_OVERWRITE_IF,
                FILE_NON_DIRECTORY_FILE, GENERIC_READ | GENERIC_WRITE); break;
    case 3: s = NtSetInformationFile(h, &io, &eof, sizeof(eof), FileEndOfFileInformation); break;
    default: s = NtClose(h); h = NULL; break;
    }
    end = KeQueryPerformanceCounter(); elapsed = end - start;
    ASSERT_NTSTATUS(s, STATUS_SUCCESS);
    if (c != 5) ASSERT_NTSTATUS(io.Status, STATUS_SUCCESS);
    if (c == 1) ASSERT_EQ_U32(io.Information, bytes);
    if (c == 2) {
        ASSERT_EQ_U32(io.Information, FILE_OVERWRITTEN);
        if (!query_length(h, 0)) return false;
        ASSERT_NTSTATUS(NtSetInformationFile(h, &io, &eof, sizeof(eof), FileEndOfFileInformation), STATUS_SUCCESS);
    }
    if (c == 5) {
        ASSERT_NTSTATUS(open_file(&h, &io, PATH, FILE_OPEN,
                        FILE_NON_DIRECTORY_FILE, GENERIC_READ), STATUS_SUCCESS);
        ASSERT_EQ_U32(io.Information, FILE_OPENED);
    }
    if (!verify(h, bytes)) return false;
    ASSERT_NTSTATUS(NtClose(h), STATUS_SUCCESS);
    return remove_file();
}
static const char *names[] = {"leaf-flush", "leaf-overwrite", "leaf-open-same-eof",
    "flush-written-64k", "write-64k", "overwrite-existing-128k", "reextend-128k",
    "parent-open", "close-written-64k"};
int main(void)
{
    unsigned failed = 0, n = 0;
    tap_puts("== write-performance begin ==\n"); tap_version(14); tap_plan(81);
    tap_comment("WRITE-META version=1 frequency=%llu repeats=9 cases=9", KeQueryPerformanceFrequency());
    tap_drain();
    for (unsigned c = 0; c < 9; ++c) {
        for (unsigned i = 0; i < 9; ++i) {
            bool ok; g_fail_file = NULL; g_fail_what[0] = 0; elapsed = 0;
            if (c < 3) {
                test_fn_t fn = c == 0 ? g_group_io_cc_write.entries[0].fn
                    : g_group_io_createfile.entries[c == 1 ? 3 : 5].fn;
                ULONGLONG start = KeQueryPerformanceCounter();
                ok = fn();
                elapsed = KeQueryPerformanceCounter() - start;
            } else ok = control(c - 3);
            unsigned bytes = c == 7 ? 0 : ((c == 1 || c == 2 || c == 5 || c == 6) ? SIZE : 65536);
            tap_comment("WRITE case=%s sample=%u ticks=%llu bytes=%u correct=%u", names[c], i, elapsed, bytes, ok);
            char desc[96]; snprintf(desc, sizeof(desc), "%s/%u", names[c], i);
            if (ok) tap_ok(++n, desc);
            else { tap_not_ok(++n, desc); ++failed; tap_comment("failure %s:%d %s", g_fail_file ? g_fail_file : "?", g_fail_line, g_fail_what); }
            tap_drain();
        }
    }
    tap_comment("WRITE-SUMMARY samples=%u failures=%u", n, failed);
    tap_puts(failed ? "== write-performance end FAIL ==\n" : "== write-performance end PASS ==\n");
    tap_drain();
    LARGE_INTEGER delay = {.QuadPart=-5000000};
    KeDelayExecutionThread(KernelMode, FALSE, &delay);
    HalWriteSMBusValue(0x20, 0x02, FALSE, 0x80);
    for (;;) __asm__ __volatile__("hlt");
}
