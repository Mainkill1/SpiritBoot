#!/usr/bin/env python3
"""Pause xemu briefly and read the opt-in SpiritBoot pool census via GDB RSP."""

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import socket
import struct
import sys
import time


MAGIC = 0x4E435031
SCHEMA = 3
HEADER = struct.Struct("<30I")
ENTRY = struct.Struct("<IHBB7I")
PAGE_STATS = struct.Struct("<7I")
DOMAIN_NAMES = ("kernel", "title", "shared")
CLASS_BLOCK_BYTES = (32, 64, 128, 256, 512, 1024, 2048)
SMALL_REQUEST_MAX = 2040
LARGE_BIN_BASE = 256
BIN_OVERFLOW = 4225
BIN_SLOTS = BIN_OVERFLOW + 1


def request_range(bin_number):
    if bin_number == 0:
        return "0"
    if bin_number < LARGE_BIN_BASE:
        low = (bin_number - 1) * 8 + 1
        return f"{low}-{bin_number * 8}"
    if bin_number < BIN_OVERFLOW:
        low = SMALL_REQUEST_MAX + 1 + (bin_number - LARGE_BIN_BASE) * 16
        high = min(low + 15, 65536)
        return f"{low}-{high}"
    return ">65536"


class CensusError(ValueError):
    pass


class GdbRemote:
    """Minimal acknowledged-mode GDB remote client for stop/read/continue."""

    def __init__(self, host, port, timeout=5):
        self.socket = socket.create_connection((host, port), timeout=timeout)
        self.socket.settimeout(timeout)
        self.pending_packet = None

    def close(self):
        self.socket.close()

    def _byte(self):
        value = self.socket.recv(1)
        if not value:
            raise CensusError("GDB stub closed the connection")
        return value

    @staticmethod
    def _frame(payload):
        raw = payload.encode("ascii")
        checksum = sum(raw) & 0xFF
        return b"$" + raw + b"#" + f"{checksum:02x}".encode("ascii")

    def _packet(self):
        if self.pending_packet is not None:
            payload = self.pending_packet
            self.pending_packet = None
            return payload
        while self._byte() != b"$":
            pass
        return self._packet_after_start()

    def _packet_after_start(self):
        payload = bytearray()
        while True:
            value = self._byte()
            if value == b"#":
                break
            payload.extend(value)
        try:
            received = int(self._byte() + self._byte(), 16)
        except ValueError as error:
            raise CensusError("malformed GDB packet checksum") from error
        if (sum(payload) & 0xFF) != received:
            self.socket.sendall(b"-")
            return self._packet()
        self.socket.sendall(b"+")
        return payload.decode("ascii")

    def _ack(self):
        while True:
            value = self._byte()
            if value == b"+":
                return
            if value == b"-":
                raise CensusError("GDB stub rejected a command packet")
            if value == b"$":
                self.pending_packet = self._packet_after_start()
                return

    def interrupt(self):
        self.socket.sendall(b"\x03")
        reply = self._packet()
        if not reply.startswith(("S", "T", "W", "X")):
            raise CensusError(f"unexpected stop reply: {reply[:80]}")
        return reply

    def read_memory(self, address, length, chunk_size=256):
        result = bytearray()
        while len(result) < length:
            count = min(chunk_size, length - len(result))
            request = f"m{address + len(result):x},{count:x}"
            self.socket.sendall(self._frame(request))
            self._ack()
            reply = self._packet()
            if reply.startswith("E"):
                raise CensusError(f"GDB memory read failed at 0x{address + len(result):08x}: {reply}")
            try:
                chunk = bytes.fromhex(reply)
            except ValueError as error:
                raise CensusError("GDB returned malformed memory data") from error
            if len(chunk) != count:
                raise CensusError(f"short GDB memory read: wanted {count}, received {len(chunk)}")
            result.extend(chunk)
        return bytes(result)

    def continue_execution(self):
        self.socket.sendall(self._frame("c"))
        self._ack()


def symbol_address(symbols_path, name="NxpPoolCensusData"):
    for line in Path(symbols_path).read_text(errors="replace").splitlines():
        fields = line.split()
        if len(fields) < 3:
            continue
        candidate = fields[-1].lstrip("_")
        if candidate == name and re.fullmatch(r"[0-9a-fA-F]+", fields[0]):
            address = int(fields[0], 16)
            if address > 0xFFFFFFFF:
                raise CensusError(f"symbol address is outside 32-bit guest space: {address:#x}")
            return address
    raise CensusError(f"symbol {name} not found in {symbols_path}")


def _checked_range(name, offset, count, stride, size, total):
    end = offset + count * stride
    if offset < size or end < offset or end > total:
        raise CensusError(f"invalid {name} range in census record")
    return end


def decode_census(data, address=0):
    if len(data) < HEADER.size:
        raise CensusError("census record is shorter than its header")
    (magic, schema, byte_count, sequence, allocations, frees, allocation_sequence,
     key_overflows, large_overflows, large_free_misses, lifetime_overflows,
     lifetime_misses, untracked_frees, saturations, page_underflows,
     lifetime_active, lifetime_active_peak, bin_slots, domain_count, class_count,
     page_stats_bytes, entry_count, entry_bytes, bin_allocations_offset,
     bin_live_offset, bin_peak_offset, pages_offset, entries_offset,
     bucket_pages_current, bucket_pages_peak) = HEADER.unpack_from(data)
    if magic != MAGIC or schema != SCHEMA:
        raise CensusError(f"unsupported census identity: magic={magic:#x}, schema={schema}")
    if byte_count != len(data):
        raise CensusError(f"census size mismatch: header={byte_count}, read={len(data)}")
    if sequence & 1:
        raise CensusError("census update was interrupted; retry while xemu is running")
    if bin_slots != BIN_SLOTS or domain_count != len(DOMAIN_NAMES) or class_count != len(CLASS_BLOCK_BYTES):
        raise CensusError("census array dimensions do not match schema 3")
    if page_stats_bytes != PAGE_STATS.size or entry_bytes != ENTRY.size:
        raise CensusError("census record element sizes do not match schema 2")

    for name, offset in (("bin allocations", bin_allocations_offset),
                         ("bin live", bin_live_offset), ("bin peak", bin_peak_offset)):
        _checked_range(name, offset, bin_slots, 4, HEADER.size, byte_count)
    _checked_range("page statistics", pages_offset, domain_count * class_count,
                   page_stats_bytes, HEADER.size, byte_count)
    _checked_range("tag table", entries_offset, entry_count, entry_bytes,
                   HEADER.size, byte_count)

    arrays = []
    for offset in (bin_allocations_offset, bin_live_offset, bin_peak_offset):
        arrays.append(struct.unpack_from(f"<{bin_slots}I", data, offset))
    bin_allocations, bin_live, bin_peak = arrays
    bins = []
    for number, (count, live, peak) in enumerate(zip(bin_allocations, bin_live, bin_peak)):
        if not (count or live or peak):
            continue
        bins.append({"bin": number,
                     "request_bytes": request_range(number),
                     "allocations": count, "live": live, "peak_live": peak})

    pages = []
    page_rows_current = 0
    for domain_index, domain in enumerate(DOMAIN_NAMES[:domain_count]):
        for class_index, block_bytes in enumerate(CLASS_BLOCK_BYTES[:class_count]):
            offset = pages_offset + (domain_index * class_count + class_index) * page_stats_bytes
            values = PAGE_STATS.unpack_from(data, offset)
            if any(values):
                page_rows_current += values[3] + values[5]
                pages.append({"domain": domain, "class_index": class_index,
                              "block_bytes_including_header": block_bytes,
                              "fresh_refills": values[0], "empty_page_reuses": values[1],
                              "detaches": values[2], "active_pages": values[3],
                              "peak_active_pages": values[4], "empty_pages": values[5],
                              "peak_empty_pages": values[6]})

    page_total_mismatch = page_rows_current != bucket_pages_current
    page_highwater_error = bucket_pages_peak < bucket_pages_current

    tags = []
    for index in range(entry_count):
        offset = entries_offset + index * entry_bytes
        tag, bin_number, domain, used, allocs, frees_count, live, peak, short, medium, retained = ENTRY.unpack_from(data, offset)
        if not used:
            continue
        tags.append({"tag": f"0x{tag:08x}", "bin": bin_number,
                     "domain": DOMAIN_NAMES[domain] if domain < len(DOMAIN_NAMES) else f"unknown-{domain}",
                     "allocations": allocs, "frees": frees_count, "live": live,
                     "peak_live": peak, "completed_lifetimes": {
                         "under_1s": short, "1_to_30s": medium, "30s_or_more": retained}})

    error_counters = {"key_overflows": key_overflows, "large_overflows": large_overflows,
                      "large_free_misses": large_free_misses,
                      "lifetime_overflows": lifetime_overflows,
                      "lifetime_misses": lifetime_misses, "untracked_frees": untracked_frees,
                      "counter_saturations": saturations, "page_counter_underflows": page_underflows,
                      "page_total_mismatches": int(page_total_mismatch),
                      "page_highwater_errors": int(page_highwater_error)}
    return {"schema": schema, "address": f"0x{address:08x}", "bytes": byte_count,
            "sequence": sequence, "totals": {"allocations": allocations, "frees": frees,
                                                "allocation_sequence": allocation_sequence,
                                                "active_lifetime_samples": lifetime_active,
                                                "peak_lifetime_samples": lifetime_active_peak},
            "error_counters": error_counters,
            "incomplete": any(error_counters.values()), "bins": bins,
            "bucket_pages": {"current": bucket_pages_current,
                              "peak": bucket_pages_peak,
                              "class_domain_current_sum": page_rows_current,
                              "current_mismatch": page_total_mismatch},
            "pages": pages, "tags": tags,
            "lifetime_note": "Completed samples are <1 s, 1-30 s, or >=30 s; active samples are right-censored."}


def capture(host, port, address, attempts=25, retry_delay=0.025, leave_stopped=False):
    remote = GdbRemote(host, port)
    stopped = False
    try:
        for attempt in range(attempts):
            remote.interrupt()
            stopped = True
            prefix = remote.read_memory(address, HEADER.size)
            if len(prefix) < HEADER.size:
                raise CensusError("short census header")
            sequence = struct.unpack_from("<I", prefix, 12)[0]
            if sequence & 1:
                remote.continue_execution()
                stopped = False
                time.sleep(retry_delay)
                continue
            byte_count = struct.unpack_from("<I", prefix, 8)[0]
            if not HEADER.size <= byte_count <= 2 * 1024 * 1024:
                raise CensusError(f"implausible census record size: {byte_count}")
            raw = remote.read_memory(address, byte_count)
            parsed_sequence = struct.unpack_from("<I", raw, 12)[0]
            if parsed_sequence != sequence or parsed_sequence & 1:
                remote.continue_execution()
                stopped = False
                time.sleep(retry_delay)
                continue
            return decode_census(raw, address)
        raise CensusError(f"census lock stayed busy for {attempts} stop attempts")
    finally:
        try:
            if stopped and not leave_stopped:
                remote.continue_execution()
        finally:
            remote.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--address", type=lambda value: int(value, 0),
                        help="guest virtual address of NxpPoolCensusData")
    target.add_argument("--symbols", type=Path,
                        help="nm output containing NxpPoolCensusData")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--leave-stopped", action="store_true",
                        help="leave xemu paused after the read")
    args = parser.parse_args(argv)
    try:
        if not 1 <= args.port <= 65535:
            raise CensusError("port must be from 1 to 65535")
        address = args.address if args.address is not None else symbol_address(args.symbols)
        if not 0 <= address <= 0xFFFFFFFF:
            raise CensusError("address must be a 32-bit guest virtual address")
        result = capture(args.host, args.port, address, leave_stopped=args.leave_stopped)
        result["captured_at_utc"] = datetime.now(timezone.utc).isoformat()
        rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
        if args.output:
            args.output.write_text(rendered)
            print(f"wrote {args.output}; census incomplete={result['incomplete']}")
        else:
            sys.stdout.write(rendered)
        return 0 if not result["incomplete"] else 2
    except (OSError, CensusError, struct.error) as error:
        print(f"pool census read failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
