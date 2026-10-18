# SPDX-License-Identifier: MIT
"""Extract only fixed object/volume metadata from the authorized Spirit snapshot.

This reader is specific to the hashed snapshot and owned baseline layout. It
cannot identify a Complex object and does not dump code, file data or RAM spans.
"""
import argparse
import hashlib
import json
import struct
from pathlib import Path

RAM_SHA256 = '8d052ca631542918f234d7acf5896d609bfe043bc362b4bcaba4b833f17a1090'
CR3 = 0xf000
SYMBOLS = {'ObpKernelHandleTable': 0x840638d4,
           'IoFileObjectType': 0x8406205c,
           'IoDeviceObjectType': 0x84062070}


class Snapshot:
    def __init__(self, data, cr3=CR3):
        self.data, self.cr3 = data, cr3

    def physical_u32(self, address):
        if not 0 <= address <= len(self.data) - 4:
            raise ValueError('Physical pointer outside snapshot')
        return struct.unpack_from('<I', self.data, address)[0]

    def physical(self, address):
        if not 0 <= address <= 0xffffffff:
            raise ValueError('Invalid virtual address')
        pde = self.physical_u32(self.cr3 + (address >> 22) * 4)
        if not pde & 1:
            raise ValueError('Unmapped page directory entry')
        if pde & 0x80:
            result = (pde & 0xffc00000) | (address & 0x3fffff)
        else:
            pte = self.physical_u32((pde & 0xfffff000) + ((address >> 12) & 1023) * 4)
            if not pte & 1:
                raise ValueError('Unmapped page table entry')
            result = (pte & 0xfffff000) | (address & 4095)
        if result >= len(self.data):
            raise ValueError('Mapped byte outside snapshot')
        return result

    def scalar(self, address, size=4):
        if size not in (1, 2, 4):
            raise ValueError('Only scalar field reads permitted')
        return int.from_bytes(bytes(self.data[self.physical(address + i)] for i in range(size)), 'little')

    def name(self, address):
        length, maximum = self.scalar(address, 2), self.scalar(address + 2, 2)
        if length > maximum or length > 128 or length % 2:
            raise ValueError('Invalid or oversized object name')
        pointer = self.scalar(address + 4)
        data = bytes(self.data[self.physical(pointer + i)] for i in range(length))
        return data.decode('utf-16-le', errors='strict')

    def object_name(self, body):
        header = body - 24
        offset = self.scalar(header + 12, 1)
        if offset < 16:
            raise ValueError('Object has no valid name metadata')
        return self.name(header - offset + 4)


def extract(data):
    if len(data) != 64 * 1024 * 1024 or hashlib.sha256(data).hexdigest() != RAM_SHA256:
        raise ValueError('This reader only accepts the recorded 64 MiB Spirit snapshot')
    memory = Snapshot(data)
    read = memory.scalar
    table = read(SYMBOLS['ObpKernelHandleTable'])
    table_code = read(table)
    if table_code & 3:
        raise ValueError('Unexpected multi-level handle table')
    handle = 0x42c
    entry = table_code + (handle >> 2) * 8
    raw_object = read(entry)
    header = raw_object & ~7
    file_object = header + 24
    if read(header + 8) != read(SYMBOLS['IoFileObjectType']) or read(file_object, 2) != 5:
        raise ValueError('Handle does not resolve to the expected file object type')
    device = read(file_object + 4)
    vpb = read(file_object + 0x4c)
    mounted, real = read(vpb + 8), read(vpb + 12)
    if real != device:
        raise ValueError('File and VPB real-device links disagree')
    device_type_object = read(SYMBOLS['IoDeviceObjectType'])
    for pointer in (device, mounted):
        if read(pointer - 24 + 8) != device_type_object:
            raise ValueError('Device object type mismatch')
    extension = read(mounted + 0x18)
    if read(extension + 0x84) != mounted or read(extension + 0x88) != real:
        raise ValueError('Mounted extension pointer cross-check failed')
    result = {
        'ram_sha256': RAM_SHA256, 'ram_bytes': len(data), 'cr3': hex(CR3),
        'handle': hex(handle), 'handle_table': hex(table), 'table_code': hex(table_code),
        'handle_entry': hex(entry), 'entry_object_tagged': hex(raw_object),
        'granted_access': hex(read(entry + 4)), 'file_object': hex(file_object),
        'file_object_type': hex(read(header + 8)), 'file_name': memory.name(file_object + 0x60),
        'native_file_flags': hex(read(file_object + 0x5c)),
        'published_file_flags': hex(read(file_object + 3, 1)),
        'synchronous_io': bool(read(file_object + 0x5c) & 2),
        'alertable_io': bool(read(file_object + 0x5c) & 4),
        'no_intermediate_buffering': bool(read(file_object + 0x5c) & 8),
        'file_device': hex(device), 'vpb': hex(vpb), 'vpb_real_device': hex(real),
        'vpb_mounted_device': hex(mounted), 'real_device_name': memory.object_name(real),
        'real_device_type': read(real + 0x1c, 1),
        'real_device_driver_name': memory.object_name(read(real + 8)),
        'mounted_device_type': read(mounted + 0x1c, 1),
        'mounted_driver_name': memory.object_name(read(mounted + 8)),
        'mounted_sector_bytes': read(mounted + 0x20), 'mounted_extension': hex(extension),
        'extension_volume_device': hex(read(extension + 0x84)),
        'extension_storage_device': hex(read(extension + 0x88)),
        'fat_sector_bytes': read(extension + 0xc0), 'fat_type': read(extension + 0xcc),
        'volume_flags': hex(read(extension + 0xe8)),
    }
    expected = {'real_device_name': 'HarddiskVolume3', 'real_device_type': 7,
                'real_device_driver_name': 'partmgr', 'mounted_device_type': 8,
                'mounted_driver_name': 'Vfatfs', 'mounted_sector_bytes': 512,
                'fat_sector_bytes': 512, 'fat_type': 4, 'volume_flags': '0x14',
                'native_file_flags': '0x40008', 'published_file_flags': '0x24',
                'synchronous_io': False, 'alertable_io': False,
                'no_intermediate_buffering': True}
    if any(result[key] != value for key, value in expected.items()):
        raise ValueError('Observed metadata differs from the archived interpretation')
    result['interpretation'] = 'Spirit handle 0x42c is an HDD volume file mounted as FATX16; drive letter not established.'
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('private_ram', type=Path)
    args = parser.parse_args()
    print(json.dumps(extract(args.private_ram.read_bytes()), indent=2))
