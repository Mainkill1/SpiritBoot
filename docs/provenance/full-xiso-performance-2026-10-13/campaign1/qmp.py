import socket,json,sys
port=int(sys.argv[1]);cmd=sys.argv[2];args=({'command-line':sys.argv[3]} if cmd=='human-monitor-command' else json.loads(sys.argv[3])) if len(sys.argv)>3 else {}
with socket.create_connection(('127.0.0.1',port),timeout=15) as s:
 f=s.makefile('rwb',buffering=0)
 def response():
  while True:
   r=json.loads(f.readline())
   if 'event' not in r:return r
 response()
 for c,a in [('qmp_capabilities',{}),(cmd,args)]:
  f.write((json.dumps({'execute':c,'arguments':a})+'\n').encode());r=response()
 print(json.dumps(r))
