#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT = Path('/home/codex/xemu-shader-workbench-handoff')
HERE = ROOT / '.scratch/forza-deck-function-profile-20261015'
GAME = ROOT / '.scratch/spiritboot-game-profile-20261015'
REPO = GAME / 'spiritboot-pr248-source'
sys.path.insert(0, str(ROOT / 'xemu-test-runner-mesa-review/scripts'))
from runner_transport import RunnerApi, job_url  # noqa: E402
from runner_workflows import Workflows  # noqa: E402

URL = 'http://10.0.0.42:9368'
SOURCE = 'sbprof-deck-pgr2-p-04-20261015-v4'
JID = 'forza-map-stream-sg-phase-profile-deck-20261015-v1'
OUT = HERE / 'deck-run'
OUT.mkdir(parents=True, exist_ok=True)

FILES = {
    'xemu': GAME / 'deck-package/xemu-profile',
    'xemu.toml': GAME / 'xemu.toml',
    'flash.bin': REPO / '.scratch/forza-map-sg-release64/flash.bin',
    'game.iso': HERE / 'fixture/forza-map-stream-profile.iso',
    'phase_function_profile.so': HERE / 'build/phase_function_profile.so',
    'spiritboot-sg.functions': HERE / 'build/spiritboot-sg.functions',
    'state/eeprom.bin': ROOT / '.scratch/doa-crash-20261015/prepared/payload/state/eeprom.bin',
}
for lib in sorted((GAME / 'profile-lib').iterdir()):
    if lib.is_file():
        FILES[f'profile-lib/{lib.name}'] = lib

def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()

def item(path: Path, name: str) -> dict:
    return {'Path': name, 'Length': path.stat().st_size,
            'Sha256': sha(path), 'Executable': name == 'xemu'}

files = [item(path, name) for name, path in sorted(FILES.items())]
job = {
    'id': JID, 'targetOs': 'linux', 'executable': 'xemu',
    'expectedExecutableSha256': sha(FILES['xemu']),
    'arguments': [
        '-config_path', '{packageDir}/xemu.toml', '-m', '64',
        '-device', 'lpc47m157', '-serial', 'file:{resultDir}/serial.log',
        '-plugin', ('{packageDir}/phase_function_profile.so,'
                    'entries={packageDir}/spiritboot-sg.functions,'
                    'output={resultDir}/phase-profile.ndjson,'
                    'begin=0x110e0,end=0x110f0'),
        '-perfmap', '-no-shutdown',
    ],
    'workingDirectory': '.', 'launchMode': 'direct', 'timeoutSeconds': 1800,
    'startPaused': False, 'requireInput': False,
    'environment': {
        'SDL_VIDEODRIVER': 'x11',
        'LD_LIBRARY_PATH': '{packageDir}/profile-lib',
    },
    'requiredFiles': [x['Path'] for x in files],
    'inputs': [
        {'path': x['Path'], 'hash': True, 'expectedSha256': x['Sha256'],
         'role': 'emulator' if x['Path'] == 'xemu' else 'diagnostic-input'}
        for x in files
    ],
    'tags': [
        'FORZA-MAP-STREAM-PUBLIC-REPLAY', 'STEAM-DECK', 'RELEASE64',
        'DIAGNOSTIC-PHASE-FUNCTION-CENSUS', 'BIOS-ARM:retained-pata-sg',
        'SOURCE-TREE:e65870455d2af1bfcc7b187b629a7e3988021491',
    ],
    'operations': {
        'mode': 'diagnostic', 'allowDiagnostics': False,
        'allowManualInput': False, 'allowPauseResume': False,
        'allowPreview': False, 'allowBulkTransfers': True,
    },
    'diagnostics': [],
    'plan': [
        {'type': 'wait_for_artifact',
         'condition': {'name': '', 'scope': 'result',
                       'path': 'phase-profile.ndjson', 'mustExist': True,
                       'minimumBytes': 0, 'containsText': '"type":"phase_end"'},
         'timeoutMs': 900000, 'pollIntervalMs': 100},
        {'type': 'wait_for_artifact',
         'condition': {'name': '', 'scope': 'result', 'path': 'serial.log',
                       'mustExist': True, 'minimumBytes': 0,
                       'containsText': '\nok 1 - Forza map streaming public request replay'},
         'timeoutMs': 900000, 'pollIntervalMs': 100},
        {'type': 'wait', 'delayMs': 1000},
        {'type': 'quit'},
    ],
    'runtimeState': {
        'enabled': True, 'keepOnSuccess': False, 'keepOnFailure': True,
        'files': [{'source': 'state/eeprom.bin', 'destination': 'eeprom.bin',
                   'expectedSha256': sha(FILES['state/eeprom.bin'])}],
        'diskAssets': [{
            'assetId': 'pr256-clean-fatx-compat010-v1',
            'expectedSha256': '78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b',
            'destination': 'hdd.qcow2', 'retention': 'deleteAfterEvidence',
        }],
        'isolation': {
            'cacheMode': 'cold', 'cacheShaders': True,
            'driverCache': 'uncontrolled', 'allowUncontrolledDriverCache': True,
            'requirePrivateGuestState': True, 'maximumBytes': 536870912,
            'maximumFiles': 8192, 'deadlineSeconds': 30,
            'readOnlyAssets': [{
                'field': 'bootrom_path', 'assetId': 'pr73-deck-bootrom-e99e3a-v1',
                'expectedSha256': 'e99e3a772bf5f5d262786aee895664eb96136196e37732fe66e14ae062f20335',
            }],
        },
    },
    'workload': {
        'correctnessChecks': [],
        'evidenceRequirements': [
            {'name': 'phase-profile', 'scope': 'result',
             'path': 'phase-profile.ndjson', 'mustExist': True, 'minimumBytes': 100},
            {'name': 'serial', 'scope': 'result', 'path': 'serial.log',
             'mustExist': True, 'minimumBytes': 1000},
        ],
        'minimumMetricSamples': 0, 'requirePlanCompletion': True,
    },
    'experiment': {
        'id': 'forza-map-stream-sg-phase-profile-20261015',
        'variant': 'retained-sg-phase-census', 'reference': None,
        'variedFactors': ['diagnostic-plugin', 'marker-only-fixture'],
        'controlledFactors': ['bios', 'kernel', 'request-metadata', 'hdd', 'host'],
        'requireCorrectnessPass': True, 'requireCompleteEvidence': True,
        'allowOperatorIntervention': False, 'allowDiagnostics': True,
    },
}
request = {'id': JID, 'files': files, 'job': job}
(OUT / 'request.json').write_text(json.dumps(request, indent=2) + '\n')
(OUT / 'input-hashes.json').write_text(json.dumps({
    k: {'bytes': p.stat().st_size, 'sha256': sha(p)} for k, p in FILES.items()
}, indent=2) + '\n')

api = RunnerApi(URL, timeout=120)
work = Workflows(api, operation_seconds=1800, progress=True)
status = api.json('/api/v1/status')
assert not status.get('CurrentJob') and status['Queue']['Pending'] == status['Queue']['Testing'] == 0, status
api.json('/api/v1/jobs', 'POST', request)
state = work.status(JID)
if state['state'] == 'busy':
    work.operation(JID)
    state = work.status(JID)
if state['state'] == 'draft':
    api.json(job_url(JID) + '/reuse', 'POST', {'sourceJobId': SOURCE})
    work.operation(JID)
    available = {x['path']: x for x in api.json(job_url(JID) + '/files')}
    for x in files:
        if x['Path'] not in available or not available[x['Path']]['status']['complete'] or \
                available[x['Path']]['sha256'] != x['Sha256']:
            api.upload_path(job_url(JID) + '/files/' + x['Path'], FILES[x['Path']],
                            x['Length'], x['Sha256'])
state = work.submit_draft(JID)
print(json.dumps({'event': 'submitted', 'state': state['state']}), flush=True)
while True:
    state = work.wait(JID, 45)
    print(json.dumps({'event': 'wait', 'state': state.get('state'),
                      'runId': state.get('runId'), 'blocker': state.get('blocker')}), flush=True)
    if state.get('state') == 'tested' or state.get('blocker') or \
            state.get('state') in {'held', 'blocked', 'cancelled', 'unavailable', 'draft'}:
        break
if state.get('state') != 'tested':
    raise SystemExit(json.dumps(state, default=str))
detail = api.json(job_url(JID))
(OUT / 'job.json').write_text(json.dumps(detail, indent=2) + '\n')
receipt = work.collect(JID, OUT / 'evidence', [], True)
(OUT / 'collection.json').write_text(json.dumps(receipt, indent=2) + '\n')
print(json.dumps({'event': 'complete', 'runId': detail['runId'],
                  'directory': receipt['directory']}), flush=True)
