import copy
import unittest

from qd_cdc import check
from test_qd_cdc import ff, net


class ScalarPortTests(unittest.TestCase):
    def test_malformed_plain_flops_cannot_be_resolved_crossings(self):
        for edge in 'PN':
            for pin in ('D', 'Q', 'C'):
                for bad in (None, [], [2, 3], '2', [None], [True], [-1], ['2'], [{}]):
                    with self.subTest(edge=edge, pin=pin, bad=bad):
                        cells = {'src': ff(1, 2, 10), 'dst': ff(2, 3, 11)}
                        design = net(cells)
                        cells['src']['type'] = '$_DFF_'+edge+'_'
                        cells['src']['connections'][pin] = bad
                        rows = check(design, 'top')
                        self.assertTrue(rows)
                        self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
                        self.assertTrue(any(r['source_cell']=='src' for r in rows))

    def test_wrong_directions_and_extra_ports_are_not_candidates(self):
        for mutation in ('direction', 'missing-direction', 'extra-direction', 'extra-port', 'missing-port',
                         'null-connections', 'null-directions'):
            with self.subTest(mutation=mutation):
                cells = {'src': ff(1, 2, 10), 'first': ff(2, 3, 11, True),
                         'second': ff(3, 4, 11, True)}
                design = net(cells)
                cell = cells['first']
                if mutation=='direction': cell['port_directions']['Q']='input'
                if mutation=='missing-direction': del cell['port_directions']['Q']
                if mutation=='extra-direction': cell['port_directions']['E']='input'
                if mutation=='extra-port': cell['connections']['E']=[30]
                if mutation=='missing-port': del cell['connections']['D']
                if mutation=='null-connections': cell['connections']=None
                if mutation=='null-directions': cell['port_directions']=None
                rows=check(design, 'top')
                self.assertTrue(rows)
                self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
                reordered=copy.deepcopy(design)
                reordered['modules']['top']['cells']=dict(reversed(list(cells.items())))
                self.assertEqual(rows, check(reordered, 'top'))

    def test_invalid_extra_output_taints_connected_data_and_clock(self):
        cells={'bad':ff(1,2,10), 'dst':ff(20,3,11), 'clocked':ff(4,5,20)}
        design=net(cells)
        cells['bad']['connections']['EXTRA']=[20]
        cells['bad']['port_directions']['EXTRA']='output'
        rows=check(design,'top')
        self.assertTrue(any(r['destination_cell']=='dst' and r['classification']=='UNKNOWN' for r in rows))
        self.assertTrue(any(r['destination_cell']=='clocked' and r['classification']=='UNKNOWN' for r in rows))

    def test_valid_edges_and_scalar_constants_keep_existing_scope(self):
        for edge in 'PN':
            cells={'src':ff(1,2,10), 'dst':ff(2,3,11)}
            for cell in cells.values(): cell['type']='$_DFF_'+edge+'_'
            self.assertEqual([r['classification'] for r in check(net(cells),'top')],['CROSSING'])
            cells['dst']['connections']['C']=[10]
            self.assertEqual(check(net(cells),'top'),[])
        for bit in ('0','1','x','z'):
            cells={'src':ff(bit,2,10)}
            # Constants are legal scalar syntax but are not clock/domain evidence.
            rows=check(net(cells, {'clk':{'direction':'input','bits':[10]}}),'top')
            self.assertTrue(rows)
            self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
