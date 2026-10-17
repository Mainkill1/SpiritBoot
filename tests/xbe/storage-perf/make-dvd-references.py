#!/usr/bin/env python3
"""Extract fresh pinned DVD inputs; read only public XBE header metadata."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import tempfile

RELEASED_ISO_PINS = {
    'clean': '8d01028844e508629d3f73481714ad46ea9931ba55f35956f28d7121f9eba475',
    'performance': '099d161a6010499cb86be58ccd2297a8be8802d8b8f4b97f7ef720ff5d0d6d33',
}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require_pin(path, expected, label):
    if len(expected) != 64 or sha256_file(path) != expected:
        raise ValueError(label + ' pin mismatch')


def generate_references(references, extractor, extractor_sha256, output, manifest):
    """Generate from explicit pinned inputs, never reuse an extracted cache.

    The CLI supplies the fixed released ISO pins. Tests call this function with
    invented inputs and an owned extractor; those inputs are not native evidence.
    """
    references = [(name, Path(iso).resolve(), pin) for name, iso, pin in references]
    if not references or len({name for name, _, _ in references}) != len(references):
        raise ValueError('missing or duplicate reference name')
    if any(name not in RELEASED_ISO_PINS for name, _, _ in references):
        raise ValueError('unknown reference name')
    extractor = Path(extractor).resolve()
    require_pin(extractor, extractor_sha256, 'extractor')
    for name, iso, pin in references:
        require_pin(iso, pin, name + ' ISO')
    rows = []
    header = ['/* Generated public XBE header metadata; no executable section bytes. */']
    with tempfile.TemporaryDirectory(prefix='pr248-dvd-reference-') as work:
        for name, iso, pin in references:
            destination = Path(work) / name
            subprocess.run([str(extractor), '-q', '-x', '-d', str(destination), str(iso)], check=True)
            # A concurrent change to an input/tool cannot acquire the old pin.
            require_pin(iso, pin, name + ' ISO')
            require_pin(extractor, extractor_sha256, 'extractor')
            xbe = destination / 'default.xbe'
            size = xbe.stat().st_size
            with xbe.open('rb') as stream:
                data = stream.read(4096)
            if data[:4] != b'XBEH' or len(data) != 4096:
                raise ValueError('invalid public XBE header')
            base = struct.unpack_from('<I', data, 0x104)[0]
            extent = struct.unpack_from('<I', data, 0x108)[0]
            count = struct.unpack_from('<I', data, 0x11c)[0]
            table = struct.unpack_from('<I', data, 0x120)[0] - base
            if table < 0 or count < 1 or table + count * 56 > min(extent, len(data)):
                raise ValueError('invalid public XBE section metadata')
            first_raw = min(struct.unpack_from('<I', data, table + i * 56 + 12)[0] for i in range(count))
            if first_raw < len(data):
                raise ValueError('requested reference crosses into executable/data sections')
            rows.append({'name': name, 'iso_sha256': pin, 'iso_bytes': iso.stat().st_size,
                         'file': 'default.xbe', 'file_bytes': size, 'header_bytes': len(data),
                         'declared_header_extent': extent, 'first_section_raw_offset': first_raw,
                         'header_sha256': hashlib.sha256(data).hexdigest(),
                         'extractor_sha256': extractor_sha256,
                         'extraction_mode': 'fresh_temporary_directory'})
            header.append(f'static const UCHAR dvd_{name}_header[4096]={{')
            header.extend(','.join(str(byte) for byte in data[i:i+32]) + ',' for i in range(0, len(data), 32))
            header.append('};')
            header.append(f'#define DVD_{name.upper()}_FILE_BYTES {size}u')
    Path(output).write_text('\n'.join(header) + '\n')
    Path(manifest).write_text(json.dumps(rows, indent=2) + '\n')
    return rows


def main():
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--clean-iso', type=Path, required=True)
    parser.add_argument('--performance-iso', type=Path, required=True)
    parser.add_argument('--extractor', type=Path, required=True)
    parser.add_argument('--extractor-sha256', required=True)
    parser.add_argument('--output', type=Path, default=root/'dvd-metadata-reference.h')
    parser.add_argument('--manifest', type=Path, default=root/'dvd-reference-manifest.json')
    args = parser.parse_args()
    references = [(name, getattr(args, name+'_iso'), pin) for name, pin in RELEASED_ISO_PINS.items()]
    rows = generate_references(references, args.extractor, args.extractor_sha256, args.output, args.manifest)
    print(json.dumps(rows))


if __name__ == '__main__':
    main()
