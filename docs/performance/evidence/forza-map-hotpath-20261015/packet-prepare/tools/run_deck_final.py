#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, sys
from pathlib import Path

ROOT=Path('/home/codex/xemu-shader-workbench-handoff')
HERE=ROOT/'.scratch/packet-prepare-hotpath-20261016'
GAME=ROOT/'.scratch/spiritboot-game-profile-20261015'
PROFILE=ROOT/'.scratch/forza-deck-function-profile-20261015'
sys.path.insert(0,str(ROOT/'xemu-test-runner-mesa-review/scripts'))
from runner_transport import RunnerApi,job_url
from runner_workflows import Workflows

URL='http://10.0.0.42:9368'
SOURCE='forza-map-stream-sg-phase-profile-deck-20261015-v1'
COMMON={
    'xemu':GAME/'deck-package/xemu-profile',
    'xemu.toml':GAME/'xemu.toml',
    'game.iso':PROFILE/'fixture/forza-map-stream-profile.iso',
    'phase_function_profile.so':PROFILE/'build/phase_function_profile.so',
    'state/eeprom.bin':ROOT/'.scratch/doa-crash-20261015/prepared/payload/state/eeprom.bin',
}
for lib in sorted((GAME/'profile-lib').iterdir()):
    if lib.is_file():COMMON[f'profile-lib/{lib.name}']=lib

def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1<<20),b''):h.update(block)
    return h.hexdigest()

def run(arm,bios,functions):
    jid=f'packet-prepare-final-{arm}-deck-20261016-v3'
    out=HERE/'deck-final'/arm;out.mkdir(parents=True,exist_ok=True)
    paths=dict(COMMON);paths['flash.bin']=bios;paths['kernel.functions']=functions
    def item(name,path):return {'Path':name,'Length':path.stat().st_size,
        'Sha256':sha(path),'Executable':name=='xemu'}
    files=[item(name,path) for name,path in sorted(paths.items())]
    job={
      'id':jid,'targetOs':'linux','executable':'xemu',
      'expectedExecutableSha256':sha(paths['xemu']),
      'arguments':['-config_path','{packageDir}/xemu.toml','-m','64','-device','lpc47m157',
        '-serial','file:{resultDir}/serial.log','-plugin',
        '{packageDir}/phase_function_profile.so,entries={packageDir}/kernel.functions,'
        'output={resultDir}/phase-profile.ndjson,begin=0x110e0,end=0x110f0',
        '-perfmap','-no-shutdown'],
      'workingDirectory':'.','launchMode':'direct','timeoutSeconds':1800,
      'startPaused':False,'requireInput':False,
      'environment':{'SDL_VIDEODRIVER':'x11','LD_LIBRARY_PATH':'{packageDir}/profile-lib'},
      'requiredFiles':[x['Path'] for x in files],
      'inputs':[{'path':x['Path'],'hash':True,'expectedSha256':x['Sha256'],
                 'role':'emulator' if x['Path']=='xemu' else 'diagnostic-input'} for x in files],
      'tags':['FORZA-MAP-STREAM-PUBLIC-REPLAY','STEAM-DECK','RELEASE64',
              'DIAGNOSTIC-PHASE-FUNCTION-CENSUS',f'BIOS-ARM:packet-prepare-{arm}'],
      'operations':{'mode':'diagnostic','allowDiagnostics':False,'allowManualInput':False,
        'allowPauseResume':False,'allowPreview':False,'allowBulkTransfers':True},
      'diagnostics':[],
      'plan':[
        {'type':'wait_for_artifact','condition':{'name':'','scope':'result',
          'path':'phase-profile.ndjson','mustExist':True,'minimumBytes':0,
          'containsText':'"type":"phase_end"'},'timeoutMs':900000,'pollIntervalMs':100},
        {'type':'wait_for_artifact','condition':{'name':'','scope':'result',
          'path':'serial.log','mustExist':True,'minimumBytes':0,
          'containsText':'\nok 1 - Forza map streaming public request replay'},
          'timeoutMs':900000,'pollIntervalMs':100},
        {'type':'wait','delayMs':1000},{'type':'quit'}],
      'runtimeState':{'enabled':True,'keepOnSuccess':False,'keepOnFailure':True,
        'files':[{'source':'state/eeprom.bin','destination':'eeprom.bin',
          'expectedSha256':sha(paths['state/eeprom.bin'])}],
        'diskAssets':[{'assetId':'pr256-clean-fatx-compat010-v1',
          'expectedSha256':'78af83a6c8a1f84cefd37b811a4197419ace68e09ad197376ca9bb2cca05e56b',
          'destination':'hdd.qcow2','retention':'deleteAfterEvidence'}],
        'isolation':{'cacheMode':'cold','cacheShaders':True,'driverCache':'uncontrolled',
          'allowUncontrolledDriverCache':True,'requirePrivateGuestState':True,
          'maximumBytes':536870912,'maximumFiles':8192,'deadlineSeconds':30,
          'readOnlyAssets':[{'field':'bootrom_path','assetId':'pr73-deck-bootrom-e99e3a-v1',
            'expectedSha256':'e99e3a772bf5f5d262786aee895664eb96136196e37732fe66e14ae062f20335'}]}},
      'workload':{'correctnessChecks':[],'evidenceRequirements':[
        {'name':'phase-profile','scope':'result','path':'phase-profile.ndjson','mustExist':True,'minimumBytes':100},
        {'name':'serial','scope':'result','path':'serial.log','mustExist':True,'minimumBytes':1000}],
        'minimumMetricSamples':0,'requirePlanCompletion':True},
      'experiment':{'id':'packet-prepare-final-paired-profile-20261016','variant':arm,'reference':None,
        'variedFactors':['bios-packet-prepare-patch'],'controlledFactors':['kernel-stack','fixture','hdd','host'],
        'requireCorrectnessPass':True,'requireCompleteEvidence':True,
        'allowOperatorIntervention':False,'allowDiagnostics':True}}
    request={'id':jid,'files':files,'job':job}
    (out/'request.json').write_text(json.dumps(request,indent=2)+'\n')
    api=RunnerApi(URL,timeout=120);work=Workflows(api,operation_seconds=1800,progress=True)
    status=api.json('/api/v1/status')
    assert not status.get('CurrentJob') and status['Queue']['Pending']==status['Queue']['Testing']==0,status
    api.json('/api/v1/jobs','POST',request);state=work.status(jid)
    if state['state']=='busy':work.operation(jid);state=work.status(jid)
    if state['state']=='draft':
        api.json(job_url(jid)+'/reuse','POST',{'sourceJobId':SOURCE});work.operation(jid)
        available={x['path']:x for x in api.json(job_url(jid)+'/files')}
        for x in files:
            if x['Path'] not in available or not available[x['Path']]['status']['complete'] or available[x['Path']]['sha256']!=x['Sha256']:
                api.upload_path(job_url(jid)+'/files/'+x['Path'],paths[x['Path']],x['Length'],x['Sha256'])
    state=work.submit_draft(jid);print(json.dumps({'arm':arm,'event':'submitted','state':state['state']}),flush=True)
    while True:
        state=work.wait(jid,45);print(json.dumps({'arm':arm,'event':'wait','state':state.get('state'),'runId':state.get('runId'),'blocker':state.get('blocker')}),flush=True)
        if state.get('state')=='tested' or state.get('blocker') or state.get('state') in {'held','blocked','cancelled','unavailable','draft'}:break
    if state.get('state')!='tested':raise SystemExit(json.dumps(state,default=str))
    detail=api.json(job_url(jid));(out/'job.json').write_text(json.dumps(detail,indent=2)+'\n')
    receipt=work.collect(jid,out/'evidence',[],True);(out/'collection.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print(json.dumps({'arm':arm,'event':'complete','runId':detail['runId'],'directory':receipt['directory']}),flush=True)

run('a1-baseline',HERE/'baseline-release64/flash.bin',HERE/'deck/baseline.functions')
run('b1-candidate',HERE/'release64-v5/flash.bin',HERE/'deck/candidate-final.functions')
run('b2-candidate',HERE/'release64-v5/flash.bin',HERE/'deck/candidate-final.functions')
run('a2-baseline',HERE/'baseline-release64/flash.bin',HERE/'deck/baseline.functions')
