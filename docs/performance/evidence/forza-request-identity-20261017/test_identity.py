# SPDX-License-Identifier: MIT
import unittest
import analyze_identity as a


def event(kind,api=0,iosb=0,child=0,srb=0,parent=0,thread=1,**kw):
    row=dict.fromkeys(a.FIELDS,0)
    row.update(kind=kind,api=api,iosb=iosb,child=child,srb=srb,parent=parent,thread=thread,**kw)
    return row


def run(rows,start=0,end=1000):
    for index,row in enumerate(rows,1):
        row.update(seq=index,host_ns=index*10,virtual_ns=index*100)
    return a.analyze(rows,start,end)


def begin(api,iosb):return event(1,api,iosb,bytes=512)
def bind(api,iosb,child,parent):return event(3,api,iosb,child,child+4,parent)
def start(api,child,thread=1):return event(4,api,child=child,srb=child+4,thread=thread)
def end(api,iosb):return event(2,api,iosb,status=0x103)
def done(child,iosb=0):return event(5,child=child,iosb=iosb)
def callback(iosb):return event(6,iosb=iosb,info=512)


class IdentityTests(unittest.TestCase):
    def test_current_and_old_queued_are_distinguished(self):
        result=run([begin(1,100),bind(1,100,200,300),end(1,100),
                    begin(2,104),bind(2,104,204,304),start(2,200),start(2,204),end(2,104)])
        self.assertEqual(result['reads'][0]['partition'],'no_start')
        self.assertEqual(result['reads'][1]['partition'],'own_and_other')
        self.assertEqual(result['reads'][1]['other_starts'],1)

    def test_queued_older_request_starts_inside_different_api(self):
        result=run([begin(1,100),bind(1,100,200,300),
                    event(7,1,child=200,srb=204,status=0x103),end(1,100),
                    begin(2,104),bind(2,104,204,304),start(2,200),end(2,104)])
        self.assertEqual(result['reads'][0]['queue_returns'],{'own:00000103':1})
        self.assertEqual(result['reads'][0]['partition'],'no_start')
        self.assertEqual(result['reads'][1]['partition'],'other_only')

    def test_callback_before_native_return(self):
        result=run([begin(1,100),bind(1,100,200,300),start(1,200),
                    done(200),done(300,100),callback(100),end(1,100)])
        self.assertEqual(result['reads'][0]['partition'],'own_only')
        self.assertTrue(result['reads'][0]['callback_seen_by_phase_end'])
        self.assertEqual(result['pending_at_phase_end'],{'iosbs':0,'children':0,'parents':0,'filesystem_partials':0})

    def test_split_same_parent_distinct_child_lifetimes(self):
        result=run([begin(1,100),bind(1,100,200,300),start(1,200),done(200),
                    bind(1,100,204,300),start(1,204),done(204),done(300,100),end(1,100)])
        self.assertEqual(result['reads'][0]['partition'],'own_only')
        self.assertEqual(result['reads'][0]['own_starts'],2)
        self.assertEqual(len(result['reads'][0]['dispatch_generations']),2)
        self.assertEqual(result['reads'][0]['parent_completion_count'],1)

    def test_filesystem_partial_without_iosb_resolves_to_root(self):
        result=run([begin(1,100),event(8,1,iosb=100,parent=300,child=400),
                    bind(1,0,200,400),start(1,200),done(200),done(400),
                    done(300,100),end(1,100),callback(100)])
        self.assertEqual(result['reads'][0]['partition'],'own_only')
        self.assertEqual(result['reads'][0]['dispatches_via_filesystem_partial'],1)
        self.assertEqual(result['reads'][0]['partial_completion_count'],1)
        self.assertEqual(result['reads'][0]['parent_completion_count'],1)

    def test_mapper_early_reject_reads_no_uninitialized_counters(self):
        result=run([begin(1,100),event(9,1,iosb=100,request=400),
                    event(11,1,request=400,status=0,value0=0),end(1,100)])
        self.assertEqual(result['mapper_calls'][0]['steps'],None)
        self.assertFalse(result['mapper_calls'][0]['walk_initialized'])

    def test_mapper_initialized_steps_and_extent_hit(self):
        result=run([begin(1,100),event(9,1,iosb=100,request=400),
                    event(10,1,request=400,value0=10,bytes=12),
                    event(11,1,request=400,status=1,value0=1,value1=10,bytes=12,info=12),
                    event(12,1,iosb=100,parent=300,value0=0),end(1,100)])
        self.assertEqual(result['mapper_calls'][0]['steps'],12)
        self.assertEqual(result['mapper_calls'][0]['api'],1)
        self.assertFalse(result['mapping_ready'][0]['extent_hit'])

    def test_ambiguous_partial_is_unknown_in_another_call(self):
        result=run([begin(1,100),event(8,1,iosb=100,parent=300,child=400),
                    bind(1,0,200,400),end(1,100),
                    begin(2,104),event(8,2,iosb=104,parent=304,child=400),
                    bind(2,0,204,400),end(2,104),begin(3,108),
                    start(3,200),start(3,204),end(3,108)])
        self.assertEqual(result['reads'][2]['partition'],'unresolved')
        self.assertEqual(result['reads'][2]['unknown_starts'],2)

    def test_unknown_null_iosb_does_not_prove_other_owner(self):
        result=run([begin(1,100),bind(1,100,200,300),bind(1,0,204,400),start(1,204),end(1,100)])
        self.assertEqual(result['reads'][0]['partition'],'unresolved')

    def test_impossible_mapper_success_rejected(self):
        with self.assertRaisesRegex(ValueError,'complete initialized'):
            run([begin(1,100),event(9,1,iosb=100,request=400),
                 event(11,1,request=400,status=1),end(1,100)])
        with self.assertRaisesRegex(ValueError,'complete initialized'):
            run([begin(1,100),event(9,1,iosb=100,request=400),
                 event(10,1,request=400,value0=10,bytes=12),
                 event(11,1,request=400,status=1,value0=1,value1=10,bytes=12,info=11),end(1,100)])

    def test_iosb_samples_and_parent_order_retained(self):
        result=run([event(1,1,iosb=100,bytes=512,status=0x103,info=99),
                    bind(1,100,200,300),done(200),done(300,100),
                    event(2,1,iosb=100,status=0x103,value0=0,info=512)])
        r=result['reads'][0]
        self.assertEqual((r['begin_iosb_status'],r['begin_iosb_info']),('00000103',99))
        self.assertEqual((r['return_iosb_status'],r['return_iosb_info']),('00000000',512))
        self.assertTrue(r['parent_completion_before_return'])

    def test_other_only_and_own_only(self):
        result=run([begin(1,100),bind(1,100,200,300),start(1,200),end(1,100),
                    begin(2,104),start(2,200),end(2,104)])
        self.assertEqual([r['partition']for r in result['reads']],['own_only','other_only'])

    def test_reused_child_after_completion_has_new_generation(self):
        result=run([begin(1,100),bind(1,100,200,300),start(1,200),done(200),done(300,100),
                    end(1,100),callback(100),begin(2,100),bind(2,100,200,300),start(2,200),end(2,100)])
        self.assertEqual([r['partition']for r in result['reads']],['own_only','own_only'])
        self.assertNotEqual(result['reads'][0]['dispatch_generations'],result['reads'][1]['dispatch_generations'])

    def test_unclosed_child_reuse_is_not_attributed(self):
        result=run([begin(1,100),bind(1,100,200,300),end(1,100),
                    begin(2,104),bind(2,104,200,304),start(2,200),end(2,104)])
        self.assertTrue(all(r['partition']=='unresolved'for r in result['reads']))

    def test_iosb_reuse_before_callback_is_rejected_for_partition(self):
        result=run([begin(1,100),end(1,100),begin(2,100),end(2,100)])
        self.assertTrue(all(r['partition']=='unresolved'for r in result['reads']))

    def test_warmup_maps_are_not_reused_after_restore(self):
        result=run([begin(1,100),bind(1,100,200,300),end(1,100),
                    begin(2,104),start(2,200),end(2,104)],start=40)
        self.assertEqual(result['reads'][0]['partition'],'unresolved')
        self.assertEqual(result['reads'][0]['unknown_starts'],1)

    def test_cross_thread_start_inclusive_interval(self):
        result=run([begin(1,100),bind(1,100,200,300),start(0,200,thread=2),end(1,100)])
        self.assertEqual(result['reads'][0]['partition'],'own_only')
        self.assertEqual(result['reads'][0]['starts_on_different_thread'],1)

    def test_srb_mismatch_is_unknown(self):
        result=run([begin(1,100),bind(1,100,200,300),event(4,1,child=200,srb=999),end(1,100)])
        self.assertEqual(result['reads'][0]['partition'],'unresolved')

    def test_queue_pending_is_not_counted_as_start(self):
        result=run([begin(1,100),bind(1,100,200,300),event(7,1,child=200,srb=204,status=0x103),end(1,100)])
        self.assertEqual(result['reads'][0]['partition'],'no_start')
        self.assertEqual(result['reads'][0]['queue_returns'],{'own:00000103':1})

    def test_phase_end_open_api_and_pending_lifetimes_reported(self):
        result=run([begin(1,100),bind(1,100,200,300)])
        self.assertEqual(result['reads'],[])
        self.assertEqual(result['event_counts']['open_api_at_phase_end'],1)
        self.assertEqual(result['pending_at_phase_end'],{'iosbs':1,'children':1,'parents':1,'filesystem_partials':0})

    def test_loss_and_truncated_flush_rejected(self):
        header='identity_meta version=1 events=0 overflow=0 reentry=0 lost=0 read_fail=0 open_api=0 map_open=0 map_reentry=0 map_lost=0\n'
        self.assertEqual(a.parse(header+'identity_end events=0\n')[1],[])
        for text in [header,header.replace('overflow=0','overflow=1')+'identity_end events=0\n',
                     header+'identity_end events=1\n',header.replace('version=1','version=2')+'identity_end events=0\n']:
            with self.assertRaises(ValueError):a.parse(text)

    def test_duplicate_fields_rejected(self):
        with self.assertRaises(ValueError):a.fields('events=0 events=0',{'events'})

if __name__=='__main__':unittest.main()
