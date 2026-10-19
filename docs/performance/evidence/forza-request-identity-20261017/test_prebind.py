# SPDX-License-Identifier: MIT
import copy
import unittest
import analyze_prebind as prebind

class PrebindTests(unittest.TestCase):
    def test_gap_boundaries(self):
        self.assertEqual([prebind.gap_bin(x)for x in [None,0,99.9,100,999.9,1000,9999.9,10000]],
          ['first_selected_call','under_100us','under_100us','100us_to_1ms','100us_to_1ms','1ms_to_10ms','1ms_to_10ms','at_least_10ms'])
        with self.assertRaises(ValueError):prebind.gap_bin(-1)

    def sample(self):
        row={'api':2,'bytes':512,'lifecycle':[{'bind':{'seq':15,'from_entry_us':50}}],
          'previous_selected_read_api':1,'previous_last_child_completion_seq':13,
          'extent_ready_flags':[True],'queue_start_partition':'no_queue_start_before_return',
          'previous_child_completion':'during_current_before_bind','api_us':100}
        events=[{'kind':2,'api':1,'virtual_ns':1000,'seq':9},
          {'kind':1,'api':2,'iosb':100,'virtual_ns':101000,'seq':10},
          {'kind':12,'api':2,'iosb':100,'virtual_ns':121000,'seq':12},
          {'kind':2,'api':2,'virtual_ns':201000,'seq':20}]
        return row,events

    def test_matching_and_disjoint_intervals(self):
        row,events=self.sample();result=prebind.enrich([row],events)[0]
        self.assertEqual(result['intercall_gap_us'],100)
        self.assertEqual(result['previous_completion_prebind_segment'],'mapping_ready_to_bind')
        self.assertEqual(result['entry_to_mapping_ready_us']+result['mapping_ready_to_bind_us'],50)
        row['previous_last_child_completion_seq']=11
        self.assertEqual(prebind.enrich([row],events)[0]['previous_completion_prebind_segment'],'entry_to_mapping_ready')

    def test_reject_bad_identity_and_order(self):
        row,events=self.sample()
        for replacement in [{'iosb':999},{'seq':16},{'virtual_ns':170000}]:
            changed=copy.deepcopy(events);changed[2].update(replacement)
            with self.assertRaises(ValueError):prebind.enrich([row],changed)
        with self.assertRaises(ValueError):prebind.enrich([row],events+[events[2]])

    def test_first_call_and_grouping(self):
        row,events=self.sample();row['previous_selected_read_api']=None;row['previous_last_child_completion_seq']=None
        result=prebind.enrich([row],events)
        self.assertEqual(result[0]['gap_bin'],'first_selected_call')
        groups=prebind.grouped(result,['bytes','extent_hit','partition'])
        self.assertEqual(groups[0]['intercall_gap_us']['n'],0)
        self.assertEqual(groups[0]['entry_to_bind_us']['median'],50)

if __name__=='__main__':unittest.main()
