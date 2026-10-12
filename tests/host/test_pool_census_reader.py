import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
SPEC = importlib.util.spec_from_file_location(
    "read_pool_census", ROOT / "tools/read_pool_census.py")
READER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(READER)


def census_fixture(sequence=8):
    header_bytes = READER.HEADER.size
    bin_slots, domains, classes = 4098, 3, 7
    allocations = header_bytes
    live = allocations + bin_slots * 4
    peak = live + bin_slots * 4
    pages = peak + bin_slots * 4
    entries = pages + domains * classes * READER.PAGE_STATS.size
    total = entries + 1024 * READER.ENTRY.size + 128
    data = bytearray(total)
    fields = [
        READER.MAGIC, READER.SCHEMA, total, sequence,
        5, 2, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
        bin_slots, domains, classes, READER.PAGE_STATS.size,
        1024, READER.ENTRY.size, allocations, live, peak, pages, entries, 4, 5,
    ]
    READER.HEADER.pack_into(data, 0, *fields)
    struct.pack_into("<I", data, allocations + 4, 11)
    struct.pack_into("<I", data, live + 4, 3)
    struct.pack_into("<I", data, peak + 4, 6)
    struct.pack_into("<I", data, allocations + 4096 * 4, 1)
    struct.pack_into("<I", data, allocations + 4097 * 4, 2)
    page_offset = pages + (1 * classes + 2) * READER.PAGE_STATS.size
    READER.PAGE_STATS.pack_into(data, page_offset, 4, 1, 1, 2, 3, 2, 4)
    entry_offset = entries + 2 * READER.ENTRY.size
    READER.ENTRY.pack_into(data, entry_offset, 0x12345678, 1, 1, 1,
                           11, 8, 3, 6, 2, 1, 0)
    return bytes(data)


def packet(payload):
    raw = payload.encode("ascii")
    return b"$" + raw + b"#" + f"{sum(raw) & 255:02x}".encode()


class PoolCensusReaderTests(unittest.TestCase):
    def test_decode_reports_nonzero_bins_pages_tags_and_integrity(self):
        result = READER.decode_census(census_fixture(), address=0x80123400)
        self.assertFalse(result["incomplete"])
        self.assertEqual(result["address"], "0x80123400")
        self.assertEqual(result["bins"][0], {"bin": 1, "request_bytes": "1-16",
                                             "allocations": 11, "live": 3, "peak_live": 6})
        self.assertEqual(result["pages"][0]["domain"], "title")
        self.assertEqual(result["pages"][0]["block_bytes_including_header"], 128)
        self.assertEqual(result["tags"][0]["tag"], "0x12345678")
        self.assertEqual(result["tags"][0]["completed_lifetimes"]["1_to_30s"], 1)
        self.assertEqual(result["bucket_pages"], {"current": 4, "peak": 5,
                                                   "class_domain_current_sum": 4,
                                                   "current_mismatch": False})
        self.assertEqual(result["bins"][1]["request_bytes"], "65521-65536")
        self.assertEqual(result["bins"][2]["request_bytes"], ">65536")

    def test_decode_rejects_odd_sequence_and_bad_offsets(self):
        with self.assertRaisesRegex(READER.CensusError, "interrupted"):
            READER.decode_census(census_fixture(sequence=9))
        corrupted = bytearray(census_fixture())
        struct.pack_into("<I", corrupted, 23 * 4, len(corrupted) + 1)
        with self.assertRaisesRegex(READER.CensusError, "range"):
            READER.decode_census(bytes(corrupted))

    def test_decode_marks_mismatched_current_page_totals_incomplete(self):
        corrupted = bytearray(census_fixture())
        struct.pack_into("<I", corrupted, 28 * 4, 3)
        result = READER.decode_census(bytes(corrupted))
        self.assertTrue(result["incomplete"])
        self.assertTrue(result["bucket_pages"]["current_mismatch"])
        self.assertEqual(result["error_counters"]["page_total_mismatches"], 1)

    def test_symbol_reader_accepts_mingw_prefix(self):
        with tempfile.TemporaryDirectory() as directory:
            symbols = Path(directory) / "nm.txt"
            symbols.write_text("80012000 B _NxpPoolCensusData\n")
            self.assertEqual(READER.symbol_address(symbols), 0x80012000)

    def test_remote_client_interrupt_reads_memory_and_continues(self):
        target = b"abcdefgh"
        class FakeSocket:
            def __init__(self):
                self.incoming = bytearray()

            def settimeout(self, _timeout):
                pass

            def sendall(self, value):
                if value == b"\x03":
                    self.incoming.extend(packet("T05thread:1;"))
                elif value.startswith(b"$"):
                    payload = value[1:value.index(b"#")].decode("ascii")
                    if payload.startswith("m"):
                        address_text, length_text = payload[1:].split(",")
                        offset = int(address_text, 16) - 0x1000
                        count = int(length_text, 16)
                        self.incoming.extend(b"+" + packet(target[offset:offset + count].hex()))
                    elif payload == "c":
                        self.incoming.extend(b"+")
                    else:
                        raise AssertionError(f"unexpected RSP packet: {payload}")

            def recv(self, count):
                result = bytes(self.incoming[:count])
                del self.incoming[:count]
                return result

            def close(self):
                pass

        fake_socket = FakeSocket()
        with mock.patch.object(READER.socket, "create_connection", return_value=fake_socket):
            remote = READER.GdbRemote("127.0.0.1", 1234)
            self.assertTrue(remote.interrupt().startswith("T"))
            self.assertEqual(remote.read_memory(0x1000, 8, chunk_size=4), target)
            remote.continue_execution()
            remote.close()


if __name__ == "__main__":
    unittest.main()
