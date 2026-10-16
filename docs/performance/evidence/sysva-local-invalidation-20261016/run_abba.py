#!/usr/bin/env python3
import copy
import hashlib
import json
import os
import sys
from pathlib import Path

PRODUCT = Path(os.environ.get(
    'SPIRITBOOT_PRODUCT', Path(__file__).resolve().parents[4]
)).resolve()
WORKSPACE = Path(os.environ.get('SPIRITBOOT_WORKSPACE', PRODUCT.parent)).resolve()
HERE = Path(os.environ.get(
    'SYSVA_FIXTURE_DIR', PRODUCT / '.scratch/sysva-sustained-fixture'
)).resolve()
RUNNER_SCRIPTS = Path(os.environ.get(
    'XEMU_RUNNER_SCRIPTS', WORKSPACE / 'xemu-test-runner-live-scene/scripts'
)).resolve()
sys.path.insert(0, str(RUNNER_SCRIPTS))
from runner_transport import RunnerApi, job_url, run_url
from runner_workflows import Workflows

URL = os.environ.get('XEMU_RUNNER_URL', 'http://10.0.7.1:9368')
SOURCE = os.environ.get(
    'XEMU_RUNNER_SOURCE', 'spiritboot-conker-xdvdfs-release64-on-c-20261016'
)
TEMPLATE = PRODUCT / 'docs/performance/evidence/conker-xdvdfs-hotpath-20261016/qualification/on-c/request.json'
FIXTURE = HERE / 'tests/xbe/kernel-performance/sysva-sustained.iso'
CONTROL_BIOS = Path(os.environ.get(
    'SPIRITBOOT_CONTROL_BIOS', PRODUCT / '.scratch/xdvdfs-forward-release64/flash.bin'
)).resolve()
CANDIDATE_BIOS = Path(os.environ.get(
    'SPIRITBOOT_CANDIDATE_BIOS', PRODUCT / '.scratch/sysva-local-release64-r2/flash.bin'
)).resolve()
ARMS = [
    ('A1', 'control', CONTROL_BIOS),
    ('B1', 'candidate', CANDIDATE_BIOS),
    ('B2', 'candidate', CANDIDATE_BIOS),
    ('A2', 'control', CONTROL_BIOS),
]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def update_file(request, name, path):
    digest = sha(path)
    for row in request['files']:
        if row['Path'] == name:
            row.update(Length=path.stat().st_size, Sha256=digest)
    for row in request['job']['inputs']:
        if row['path'] == name:
            row['expectedSha256'] = digest
    return digest


base = json.loads(TEMPLATE.read_text())
api = RunnerApi(URL, timeout=120)
work = Workflows(api, operation_seconds=1800, progress=True)
out = HERE / 'results'
out.mkdir(exist_ok=True)

for position, side, bios in ARMS:
    job_id = f'spiritboot-sysva-local-{position.lower()}-20261016-v2'
    request = copy.deepcopy(base)
    request['id'] = request['job']['id'] = job_id
    fixture_sha = sha(FIXTURE)
    request['files'].append({'Path': 'game.iso', 'Length': FIXTURE.stat().st_size,
                             'Sha256': fixture_sha, 'Executable': False})
    request['job']['requiredFiles'].append('game.iso')
    request['job']['inputs'].append({'path': 'game.iso', 'hash': True,
                                     'expectedSha256': fixture_sha,
                                     'role': 'native-regression-input'})
    bios_sha = update_file(request, 'flash.bin', bios)
    request['job']['arguments'] = [
        '-config_path', '{packageDir}/xemu.toml', '-m', '64',
        '-device', 'lpc47m157', '-serial', 'file:{resultDir}/native-serial.log',
        '-no-shutdown',
    ]
    request['job']['timeoutSeconds'] = 300
    request['job']['plan'] = [
        {'type': 'wait_for_artifact', 'condition': {
            'path': 'native-serial.log', 'scope': 'result', 'mustExist': True,
            'containsText': '== kernel-performance end PASS =='},
         'pollIntervalMs': 100, 'timeoutMs': 240000},
        {'type': 'wait', 'delayMs': 500},
        {'type': 'quit'},
    ]
    request['job']['diagnostics'] = []
    request['job']['operations'] = {
        'mode': 'diagnostic', 'allowDiagnostics': False,
        'allowManualInput': False, 'allowPauseResume': False,
        'allowPreview': False, 'allowBulkTransfers': False,
    }
    request['job']['workload'] = {'requirePlanCompletion': True}
    request['job']['runtimeState']['isolation']['readOnlyAssets'] = [
        row for row in request['job']['runtimeState']['isolation']['readOnlyAssets']
        if row['field'] != 'dvd_path'
    ]
    request['job']['tags'] = [
        'SPIRITBOOT-SYSVA-SUSTAINED-ABBA', 'USER-POWERSHELL-PIPE',
        'RELEASE64', f'POSITION:{position}', f'ARM:{side}',
        'ITERATIONS:1048576', 'SAMPLES:4',
    ]
    request['job']['experiment'] = {
        'id': 'spiritboot-sysva-local-invalidation-20261016',
        'variant': side,
        'reference': 'control',
        'variedFactors': ['bios'],
        'controlledFactors': ['fixture', 'xemu', 'config', 'eeprom', 'hdd', 'host', 'release-build'],
    }
    (out / f'{job_id}-request.json').write_text(json.dumps(request, indent=2) + '\n')
    print(json.dumps({'event': 'create', 'id': job_id, 'position': position,
                      'side': side, 'bios': bios_sha, 'fixture': fixture_sha}), flush=True)
    api.json('/api/v1/jobs', 'POST', request)
    state = work.status(job_id)
    if state['state'] == 'busy':
        work.operation(job_id)
        state = work.status(job_id)
    if state['state'] == 'draft':
        api.json(job_url(job_id) + '/reuse', 'POST', {'sourceJobId': SOURCE})
        work.operation(job_id)
        api.upload_path(job_url(job_id) + '/files/game.iso', FIXTURE,
                        FIXTURE.stat().st_size, fixture_sha)
        api.upload_path(job_url(job_id) + '/files/flash.bin', bios,
                        bios.stat().st_size, bios_sha)
        state = work.submit_draft(job_id)
    while state['state'] != 'tested':
        state = work.wait(job_id, 45)
        print(json.dumps({'event': 'wait', 'id': job_id, 'state': state.get('state'),
                          'runId': state.get('runId'), 'blocker': state.get('blocker')}), flush=True)
        if state.get('blocker') or state['state'] in ('held', 'blocked', 'cancelled', 'unavailable', 'draft'):
            raise SystemExit(json.dumps(state))
    detail = api.json(job_url(job_id))
    result = work.result(job_id, detail)
    (out / f'{job_id}-job.json').write_text(json.dumps(detail, indent=2) + '\n')
    (out / f'{job_id}-result.json').write_text(json.dumps(result, indent=2) + '\n')
    run_id = detail['runId']
    artifacts = api.json(run_url(run_id) + '/artifacts?limit=100')
    item = next(row for row in artifacts['items'] if row['path'] == 'native-serial.log')
    api.download(run_url(run_id) + '/artifacts/native-serial.log',
                 out / f'{job_id}-native-serial.log', item['bytes'])
    print(json.dumps({'event': 'collected', 'id': job_id, 'runId': run_id,
                      'outcome': result.get('outcome')}), flush=True)
