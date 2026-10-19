#!/usr/bin/env python3
"""Conservative, fixed-layout Halo v1.09 menu presence check (not game validation)."""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageFilter

# Desktop shim capture at 1280x720 client size, four entries, Campaign selected.
SIZE = (1296, 759)
ROWS = {
    'campaign': (530, 405, 774, 446),
    'multiplayer': (500, 460, 810, 498),
    'settings': (540, 514, 765, 552),
    'game_demos': (497, 567, 810, 608),
}

def check(reference, candidate):
    with Image.open(reference) as source:
        expected = source.convert('RGB')
    with Image.open(candidate) as source:
        actual = source.convert('RGB')
    result = {
        'scope': 'four menu-entry masks, Campaign selected; not full game correctness',
        'reference_sha256': hashlib.sha256(reference.read_bytes()).hexdigest(),
        'candidate_sha256': hashlib.sha256(candidate.read_bytes()).hexdigest(),
        'layout': 'Halo v1.09 / 1280x720 client / Windows shim',
        'passed': False, 'entries': {},
    }
    if expected.size != SIZE or actual.size != SIZE:
        result['error'] = 'Unexpected capture size; layout not qualified'
        return result
    for name, box in ROWS.items():
        def foreground(pixel):
            r, g, b = pixel
            if name == 'campaign':
                return r > 180 and g > 195 and b > 210
            return b > 85 and b > r + 35 and g > r + 15
        crop = expected.crop(box)
        mask = Image.new('L', crop.size)
        mask.putdata([255 if foreground(p) else 0 for p in crop.getdata()])
        # Exclude blended glyph edges, which vary with the moving background.
        template = [bool(p) for p in mask.filter(ImageFilter.MinFilter(3)).getdata()]
        observed = [foreground(p) for p in actual.crop(box).getdata()]
        count = sum(template)
        hits = sum(a and b for a, b in zip(template, observed))
        qualified = count >= 500
        recall = hits / count if count else 0
        result['entries'][name] = {
            'reference_pixels': count, 'matching_pixels': hits,
            'recall': recall, 'reference_qualified': qualified,
            'present': qualified and recall >= 0.95,
        }
    result['passed'] = all(row['present'] for row in result['entries'].values())
    return result

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', required=True, type=Path)
    parser.add_argument('--candidate', required=True, type=Path)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = check(args.reference, args.candidate)
    data = json.dumps(result, indent=2) + '\n'
    if args.output:
        args.output.write_text(data)
    print(data, end='')
    raise SystemExit(0 if result['passed'] else 1)
