#!/usr/bin/env python3
"""Only change the declared DVD of the PID/QMP endpoint owned by this job."""
import argparse,pathlib,json,re,socket,hashlib,os
p=argparse.ArgumentParser();p.add_argument('--pid',type=int,required=True);p.add_argument('--package',type=pathlib.Path,required=True);p.add_argument('--result',type=pathlib.Path,required=True);p.add_argument('--target-sha256',required=True);a=p.parse_args()
target=a.package/'target.iso';old=a.package/'storage-perf.iso';audit={'schema_version':1,'owned_pid':a.pid,'package':str(a.package),'result':str(a.result),'target':str(target),'transport':'runner-owned-local-qmp','operations':[]}
try:
 if hashlib.sha256(target.read_bytes()).hexdigest()!=a.target_sha256:raise ValueError('declared target media pin mismatch')
 argv=pathlib.Path(f'/proc/{a.pid}/cmdline').read_bytes().decode().split('\0')
 if pathlib.Path(argv[0]).name!='xemu':raise ValueError('owned runner PID is not the expected xemu process')
 endpoint=argv[argv.index('-qmp')+1];match=re.fullmatch(r'tcp:127\.0\.0\.1:(\d+),server=on,wait=off',endpoint)
 if not match:raise ValueError('unexpected owned QMP endpoint')
 audit['qmp_endpoint']=endpoint
 with socket.create_connection(('127.0.0.1',int(match[1])),timeout=3) as sock:
  sock.settimeout(3);reader=sock.makefile('rb');writer=sock.makefile('wb');hello=json.loads(reader.readline());audit['greeting']=hello
  index=0
  def command(name,args=None):
   global index
   index+=1;request={'execute':name,'id':index}
   if args is not None:request['arguments']=args
   writer.write(json.dumps(request,separators=(',',':')).encode()+b'\r\n');writer.flush()
   while True:
    response=json.loads(reader.readline())
    if response.get('id')==index:break
   audit['operations'].append({'request':request,'response':response})
   if 'error' in response:raise ValueError('owned QMP command failed: '+json.dumps(response['error']))
   return response['return']
  command('qmp_capabilities');blocks=command('query-block')
  candidates=[b for b in blocks if b.get('removable') and pathlib.Path(b.get('inserted',{}).get('file','')).resolve()==old.resolve()]
  if len(candidates)!=1 or not candidates[0].get('device'):raise ValueError('owned declared DVD is not uniquely identifiable')
  command('blockdev-change-medium',{'device':candidates[0]['device'],'filename':str(target.resolve()),'format':'raw','read-only-mode':'read-only'})
 audit['completed']=True
finally:
 (a.result/'native-media-control.json').write_text(json.dumps(audit,indent=2)+'\n')
