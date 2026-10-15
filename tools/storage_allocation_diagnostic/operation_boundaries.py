# SPDX-License-Identifier: GPL-2.0-only
"""Original state checks for exact owned fixture instruction observations."""
class Boundaries:
    def __init__(self, count=1024):
        if type(count) is not int or not 0<count<=1024:raise ValueError('explicit positive bounded operation count required')
        self.complete=False;self.expected=count;self.next_index=0;self.active=None;self.frame=None
    def observe(self, event):
        if self.complete:raise ValueError('event after complete owned window')
        index=event.get('index')
        if type(index) is not int or index!=self.next_index:raise ValueError('missing/duplicate/out-of-order operation')
        frame=(event.get('thread'),event.get('esp'))
        if any(type(value) is not int or not 0<value<2**32 for value in frame):raise ValueError('missing exact execution identity')
        if self.frame is not None and self.frame!=frame:raise ValueError('owned function execution identity changed')
        if event.get('kind')=='issue':
            if self.active is not None:raise ValueError('overlapping operation boundary')
            if type(event.get('length')) is not int or event['length']!=4096 or type(event.get('offset')) is not int or event['offset']!=index*4096:
                raise ValueError('actual request shape differs')
            self.active=frame;self.frame=frame
        elif event.get('kind')=='consumer':
            if self.active!=frame:raise ValueError('consumer without exact issue identity')
            for key,value in (('status',0),('io_status',0),('information',4096),('verification_mask',0)):
                if type(event.get(key)) is not int or event[key]!=value:raise ValueError('consumer verification failed/missing: '+key)
            self.active=None;self.next_index+=1;self.complete=self.next_index==self.expected
        else:raise ValueError('unknown owned boundary')
