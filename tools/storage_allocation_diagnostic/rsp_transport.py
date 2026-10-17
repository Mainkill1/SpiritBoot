# SPDX-License-Identifier: GPL-2.0-only
"""Original owned diagnostic helpers; no launch or ownership bypass."""
import socket
import struct
import time

PCR_CURRENT_THREAD = 0xFFDFF124
class Rsp:
    def __init__(self, host, port, deadline):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.sock.settimeout(.25)
        self.deadline = deadline
        self.stopped = False
        self.breakpoints = set()

    def byte(self):
        while True:
            if time.monotonic() >= self.deadline:
                raise TimeoutError("bounded trace deadline")
            try:
                byte = self.sock.recv(1)
            except socket.timeout:
                continue
            if not byte:
                raise EOFError("GDB connection closed")
            return byte

    def send(self, command):
        data = command.encode("ascii")
        self.sock.sendall(b"$" + data + b"#" + f"{sum(data) & 255:02x}".encode())

    def reply(self):
        while self.byte() != b"$":
            pass
        response = bytearray()
        while True:
            byte = self.byte()
            if byte == b"#":
                break
            response.extend(byte)
        checksum = self.byte() + self.byte()
        if int(checksum, 16) != sum(response) & 255:
            self.sock.sendall(b"-")
            raise ValueError("RSP response checksum mismatch")
        self.sock.sendall(b"+")
        return response.decode("ascii")

    def packet(self, command):
        self.send(command)
        return self.reply()

    def stop_reply(self, response):
        if response.startswith(("W", "X")):
            raise EOFError("guest exited: " + response)
        if not response.startswith(("S", "T")):
            raise ValueError("unexpected stop: " + response)
        self.stopped = True
        return response

    def run(self, command):
        self.stopped = False
        self.send(command)
        return self.stop_reply(self.reply())

    def interrupt(self):
        if not self.stopped:
            self.sock.sendall(b"\x03")
            self.stop_reply(self.reply())

    def read(self, address, size):
        if size > 512 or address < 0x1000 or address + size > 0x100000000:
            raise ValueError("bounded valid pointer required")
        reply = self.packet(f"m{address:x},{size:x}")
        if reply.startswith("E") or len(reply) != size * 2:
            raise ValueError(f"unreadable pointer {address:08x}/{size}")
        return bytes.fromhex(reply)

    def regs(self):
        return struct.unpack("<9I", bytes.fromhex(self.packet("g"))[:36])

    def bp(self, address, enabled=True):
        reply = self.packet(f'{"Z" if enabled else "z"}0,{address:x},1')
        if reply != "OK":
            raise ValueError("breakpoint refused: " + reply)
        if enabled:
            self.breakpoints.add(address)
        else:
            self.breakpoints.discard(address)

    def thread(self):
        thread = struct.unpack("<I", self.read(PCR_CURRENT_THREAD, 4))[0]
        if thread < 0x80000000 or thread & 3:
            raise ValueError(f"invalid current KTHREAD {thread:08x}")
        return thread
