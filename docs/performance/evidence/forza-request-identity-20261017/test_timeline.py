# SPDX-License-Identifier: MIT
import unittest
from analyze_timeline import timeline
from test_identity import event,begin,bind,start,end,done,callback


def run(rows):
    for i,e in enumerate(rows,1):e.update(seq=i,host_ns=i*10,virtual_ns=i*100)
    return timeline(rows,0,1000)


class TimelineTests(unittest.TestCase):
    def test_previous_completion_during_next_api_before_bind(self):
        r=run([begin(1,100),bind(1,100,200,300),start(1,200),end(1,100),
               begin(2,104),done(200),done(300,100),callback(100),
               bind(2,104,204,304),start(2,204),end(2,104)])
        c=r['reads'][1]
        self.assertEqual(c['previous_child_completion'],'during_current_before_bind')
        self.assertEqual(len(c['entry_tracked_started_uncompleted']),1)
        self.assertEqual(c['lifecycle'][0]['bind_tracked_started_uncompleted'],[])

    def test_next_start_precedes_old_child_complete_not_tag_count(self):
        r=run([begin(1,100),bind(1,100,200,300),start(1,200),end(1,100),
               begin(2,104),bind(2,104,204,304),start(2,204),done(200),end(2,104)])
        c=r['reads'][1]
        self.assertEqual(c['previous_child_completion'],'during_current_after_bind')
        self.assertEqual(len(c['lifecycle'][0]['bind_tracked_started_uncompleted']),1)
        self.assertEqual(c['queue_start_partition'],'no_queue_start_before_return')
        self.assertAlmostEqual(sum(c['submission_segments'].values()),c['api_us'])

    def test_no_start_eventual_own_start(self):
        r=run([begin(1,100),bind(1,100,200,300),
               event(7,1,child=200,srb=204,status=0x103),end(1,100),start(0,200),done(200),done(300,100),callback(100)])
        c=r['reads'][0]
        self.assertEqual(c['queue_start_partition'],'queued_start_after_return')
        self.assertEqual(c['lifecycle'][0]['starts'][0]['relative_to_return'],'after')

    def test_partial_keeps_original_generation_through_completion(self):
        r=run([begin(1,100),event(8,1,iosb=100,parent=300,child=400),
               bind(1,0,200,400),start(1,200),done(200),done(400),
               done(300,100),callback(100),end(1,100)])
        c=r['reads'][0]
        self.assertTrue(c['lifecycle'][0]['via_partial'])
        self.assertEqual(len(c['root_completions']),1)
        self.assertLess(c['lifecycle'][0]['adapter_parent_completion']['seq'],c['root_completions'][0]['seq'])

if __name__=='__main__':unittest.main()
