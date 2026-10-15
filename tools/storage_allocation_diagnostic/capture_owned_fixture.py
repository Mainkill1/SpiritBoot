# SPDX-License-Identifier: GPL-2.0-only
"""Diagnostic-only owned-XBE boot gate and exact operation boundary observer.

Uses the unchanged preparatory ledger/transport. No launch, QMP or data writes.
An independently verified Windows process/listener guard must precede attach.
"""
import argparse
import json
import struct
import time
from pathlib import Path

from allocation_ledger import ReturnMatcher, analyze
from support import load_transport, caller_frames
from operation_boundaries import Boundaries


def capture(args, transport_class=None):
    kernel=json.loads(args.binding.read_text());fixture=json.loads(args.fixture.read_text())
    context=json.loads(args.context.read_text())
    if type(fixture.get('operation_count')) is not int or fixture['operation_count']!=1024:
        raise ValueError('exact selected compiled operation count required')
    if (context.get('status')!='owned_paused_route_verified' or context.get('mode')!='DIAGNOSTIC_ONLY' or
            context.get('gdb_port')!=args.port or context.get('kernel_sha256')!=kernel['final_sha256'] or
            context.get('selected_case')!=fixture['selected_case']):raise ValueError('guarded context differs')
    if not 0<args.seconds<=90:raise ValueError('bounded diagnostic duration required')
    args.out.mkdir(exist_ok=False)
    (args.out/'context-before-attach.json').write_bytes(args.context.read_bytes())
    (args.out/'kernel-binding.json').write_bytes(args.binding.read_bytes())
    (args.out/'fixture-binding.json').write_bytes(args.fixture.read_bytes())
    log=(args.out/'events.jsonl').open('w',buffering=1)
    boundary_log=(args.out/'boundaries.jsonl').open('w',buffering=1)
    control_log=(args.out/'debugger-control.jsonl').open('w',buffering=1)
    events=[];boundaries=[];rsp=None;error=None;status='error';count=0;stops=0;measure_frame=None
    step_stops=0;same_identity_step_stops=0
    matcher=ReturnMatcher();tracker=Boundaries(fixture['operation_count'])
    pool={site['address']:site for site in kernel['sites'] if site['call'] in ('allocate','free')}
    sites={name:row['address'] for name,row in fixture['sites'].items()}
    def emit(kind,**data):
        row=dict(seq=len(events),kind=kind,host_monotonic_ns=time.monotonic_ns(),**data)
        events.append(row);log.write(json.dumps(row)+'\n');return row
    def boundary(**data):
        row=dict(seq=len(boundaries),host_monotonic_ns=time.monotonic_ns(),**data)
        boundaries.append(row);boundary_log.write(json.dumps(row)+'\n');return row
    def u32(address):return struct.unpack('<I',rsp.read(address,4))[0]
    def string(address):
        data=bytearray()
        for i in range(96):
            value=rsp.read(address+i,1)
            if value==b'\0':return data.decode('ascii')
            data.extend(value)
        raise ValueError('owned bounded selection string missing terminator')
    try:
        Rsp=transport_class or load_transport(args.transport,kernel['transport_sha256'])
        rsp=Rsp('127.0.0.1',args.port,time.monotonic()+args.seconds)
        rsp.stop_reply(rsp.packet('?'));initial=rsp.regs()[8]
        rsp.bp(fixture['entry_address']);rsp.run('c')
        if rsp.regs()[8]!=fixture['entry_address']:raise ValueError('wrong owned XBE boot gate')
        rsp.bp(fixture['entry_address'],False)
        if rsp.read(fixture['entry_address'],16).hex()!=fixture['entry_bytes']:raise ValueError('live owned entry differs')
        for site in kernel['sites']:
            if rsp.read(site['address'],len(bytes.fromhex(site['entry_bytes']))).hex()!=site['entry_bytes']:
                raise ValueError('live selected kernel site differs')
        for site in fixture['sites'].values():
            if rsp.read(site['address'],16).hex()!=site['bytes']:raise ValueError('live owned boundary differs')
        emit('start',baseline_complete=False,baseline=[],owned_fixture_gate_pc=fixture['entry_address'],
             initial_pc=initial,case_id=fixture['selected_case'],performance_acceptance_eligible=False)
        for address in sites.values():rsp.bp(address)
        rsp.run('c')
        while True:
            stops+=1
            if stops>100000:raise ValueError('diagnostic stop capacity reached')
            regs=rsp.regs();eax,esp,ebp,pc=regs[0],regs[4],regs[5],regs[8]
            thread=u32(kernel['current_thread_address'])
            if thread<0x80000000 or thread&3:raise ValueError('compiled current-thread identity invalid')
            call=matcher.returned(thread,pc,esp)
            if call is not None:emit('return',call_id=call['call_id'],thread=thread,pc=pc,esp=esp,eax=eax,
                                     active_operation_index=tracker.next_index if tracker.active else None)
            if pc==sites['measure_entry']:
                if measure_frame is not None:raise ValueError('repeated owned measure invocation')
                _,handle,idp,cachep=struct.unpack('<4I',rsp.read(esp,16))
                if string(idp)!=fixture['selected_case'] or string(cachep)!='cold-ish':raise ValueError('actual selected case differs')
                measure_frame=dict(thread=thread,entry_esp=esp,handle=handle)
                boundary(kind='measure-entry',thread=thread,entry_esp=esp,handle=handle,case_id=string(idp))
            elif pc in (sites['operation_issue'],sites['consumer_verified']):
                if measure_frame is None or thread!=measure_frame['thread']:raise ValueError('boundary outside owned measure identity')
                index=u32(esp+fixture['index_stack_offset'])
                if pc==sites['operation_issue']:
                    arguments=list(struct.unpack('<8I',rsp.read(esp,32)))
                    offset=struct.unpack('<q',rsp.read(arguments[7],8))[0]
                    row=boundary(kind='issue',index=index,thread=thread,esp=esp,length=arguments[6],offset=offset,
                                 pc=pc,args=arguments,target_register_eax=eax,service_count=u32(kernel['service_count_address']))
                    if (arguments[0]!=measure_frame['handle'] or arguments[1:4]!=[0,0,0] or
                            arguments[4]!=esp+fixture['iosb_stack_offset']):raise ValueError('actual synchronous request bindings differ')
                    tracker.observe(row)
                    for address in pool:
                        if address not in rsp.breakpoints:rsp.bp(address)
                else:
                    io_status,information=struct.unpack('<II',rsp.read(esp+fixture['iosb_stack_offset'],8))
                    row=boundary(kind='consumer',index=index,thread=thread,esp=esp,pc=pc,
                                 status=u32(esp+fixture['status_stack_offset']),io_status=io_status,information=information,
                                 verification_mask=u32(esp+fixture['result_mask_stack_offset']),
                                 service_count=u32(kernel['service_count_address']))
                    tracker.observe(row)
                    if tracker.complete:
                        status='ok';break
            elif pc in pool:
                site=pool[pc];values=struct.unpack('<'+'I'*(1+site['argument_bytes']//4),rsp.read(esp,4+site['argument_bytes']))
                count+=1
                if count>20000:raise ValueError('diagnostic call capacity reached')
                event=emit('entry',call_id=count,call=site['call'],thread=thread,caller_pc=values[0],entry_esp=esp,
                           args=list(values[1:]),owner=dict(kind='unknown',evidence_sha256=None),
                           caller_evidence=caller_frames(rsp,ebp,esp),active_operation_index=tracker.next_index if tracker.active else None)
                matcher.enter(event)
                if values[0] not in rsp.breakpoints:rsp.bp(values[0])
            elif call is None and not any(key[1]==pc for key in matcher.pending):raise ValueError('unexpected debugger stop')
            rsp.bp(pc,False)
            # A step reply can stop before leaving the consumed location. Keep
            # its breakpoint disabled, and never reinterpret that stop as a
            # fresh entry/return. Changed registers alone do not establish a
            # new call at the same thread/PC/ESP. These bounded retries are
            # diagnostic control events, not guest allocation/free events.
            step_before_regs=regs;step_before_thread=thread
            for attempt in range(8):
                reply=rsp.run('s');after_regs=rsp.regs();after_thread=u32(kernel['current_thread_address'])
                step_stops+=1
                same_identity=(after_thread,after_regs[8],after_regs[4])==(thread,pc,esp)
                control_log.write(json.dumps(dict(seq=step_stops-1,host_monotonic_ns=time.monotonic_ns(),
                    command='s',reply=reply,attempt=attempt,consumed_stop_thread=thread,
                    consumed_stop_registers=list(regs),before_thread=step_before_thread,before_registers=list(step_before_regs),
                    after_thread=after_thread,after_registers=list(after_regs),
                    same_stop_identity=same_identity,
                    observed_register_context_unchanged=after_thread==step_before_thread and after_regs==step_before_regs))+'\n')
                if step_stops>100000:raise ValueError('diagnostic step stop capacity reached')
                if not same_identity:break
                same_identity_step_stops+=1
                step_before_regs=after_regs;step_before_thread=after_thread
            else:raise ValueError('single-step made no progress beyond consumed stop identity')
            if pc in sites.values() or pc in pool or any(key[1]==pc for key in matcher.pending):rsp.bp(pc)
            stepped=after_regs[8]
            if stepped in sites.values() or stepped in pool or any(key[1]==stepped for key in matcher.pending):continue
            rsp.run('c')
    except Exception as exc:
        error=repr(exc);emit('loss',reason=error)
    finally:
        if rsp is not None:
            rsp.deadline=time.monotonic()+10
            try:
                rsp.interrupt()
                for address in list(rsp.breakpoints):rsp.bp(address,False)
                if rsp.packet('D')!='OK':raise ValueError('detach refused')
            except Exception as exc:
                status='error';error=repr(exc);emit('loss',reason='cleanup: '+error)
            finally:rsp.sock.close()
        emit('end',status=status,error=error)
        log.close();boundary_log.close();control_log.close()
        report=analyze(events)
        report['debugger_control']=dict(step_stops=step_stops,same_identity_step_stops=same_identity_step_stops,
            raw_step_log='debugger-control.jsonl',per_consumed_stop_attempt_limit=8,
            register_order=['eax','ecx','edx','ebx','esp','ebp','esi','edi','eip'],
            instruction_retirement_proven=False,performance_acceptance_eligible=False)
        report['owned_boundaries']=dict(complete=tracker.complete,operations=tracker.next_index,error=error,
            exact_observed_guest_pcs=any(row['kind'] in ('issue','consumer') for row in boundaries),performance_acceptance_eligible=False,
            consumer_semantics='normal API return plus status/IOSB/length and full-byte comparison observed before next timestamp')
        (args.out/'report.json').write_text(json.dumps(report,indent=2))
    return 0 if status=='ok' else 1


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('binding','fixture','context','transport','out'):parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--port',type=int,required=True);parser.add_argument('--seconds',type=float,default=60)
    parser.add_argument('--execute-diagnostic',action='store_true',required=True)
    raise SystemExit(capture(parser.parse_args()))
