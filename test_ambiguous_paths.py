import unittest
from qd_cdc import check
from test_qd_cdc import ff, net


class AmbiguousPathTests(unittest.TestCase):
    def test_multiple_flop_drivers_are_unknown_even_on_same_clock(self):
        for clock in (10,11):
            cells={'a':ff(1,2,10),'b':ff(4,2,clock),'dst':ff(2,3,11)}
            rows=[r for r in check(net(cells),'top') if r['destination_cell']=='dst']
            self.assertEqual({r['source_cell'] for r in rows},{'a','b'})
            self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
            self.assertTrue(all('multiple drivers on net 2' in r['path'] for r in rows))

    def test_known_and_unknown_driver_cannot_leave_a_resolved_path(self):
        cells={'a':ff(1,2,10),'dst':ff(2,3,11),
               'box':{'type':'VENDOR','connections':{'Y':[2]},'port_directions':{'Y':'output'}}}
        rows=[r for r in check(net(cells),'top') if r['destination_cell']=='dst']
        self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
        self.assertEqual(len(rows),2)

    def test_legacy_primary_input_internal_driver_is_not_silently_dropped(self):
        cells={'a':ff(1,2,10),'dst':ff(2,3,11)}
        data=net(cells);data['modules']['top']['ports']['alias']={'direction':'input','bits':[2]}
        rows=[r for r in check(data,'top') if r['destination_cell']=='dst']
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['classification'],'UNKNOWN')
        self.assertIn('input net also has internal driver',rows[0]['path'][-1])

    def test_candidate_requires_one_second_stage_and_one_stage_driver(self):
        cells={'a':ff(1,2,10),'first':ff(2,3,11,True),'second':ff(3,4,11,True)}
        self.assertIn('CANDIDATE_SYNCHRONIZER',[r['classification'] for r in check(net(cells),'top')])
        for extra in (ff(3,5,12,True),ff(3,5,11,False),ff(1,3,10)):
            modified=dict(cells,extra=extra)
            rows=check(net(modified),'top')
            self.assertNotIn('CANDIDATE_SYNCHRONIZER',[r['classification'] for r in rows])
            self.assertEqual(rows,check(net(dict(reversed(list(modified.items())))),'top'))

    def test_ambiguity_propagates_through_combinational_fanin(self):
        cells={'a':ff(1,2,10),'b':ff(4,2,10),'dst':ff(6,3,11),
               'buf':{'type':'$_BUF_','connections':{'A':[2],'Y':[6]},
                      'port_directions':{'A':'input','Y':'output'}}}
        rows=[r for r in check(net(cells),'top') if r['destination_cell']=='dst']
        self.assertEqual(len(rows),2)
        self.assertTrue(all(r['classification']=='UNKNOWN' and r['path'][0]=='buf.Y' for r in rows))
