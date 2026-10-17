#!/usr/bin/env python3
"""Embed reviewable owned inline commands; never invoke a Windows script file."""
import base64
from pathlib import Path
root = Path(__file__).resolve().parent
lines = ['/* Generated from owned PowerShell sources; no credentials. */']
for name in ('server', 'client'):
    encoded = base64.b64encode((root / ('desktop-pipe-'+name+'.ps1')).read_text().encode('utf-16-le')).decode()
    lines.append('static const WCHAR PIPE_'+name.upper()+'_COMMAND[] = L"'+encoded+'";')
(root / 'pipe-commands.h').write_text('\n'.join(lines)+'\n')
