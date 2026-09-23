import unittest

from qd_cdc import check
from test_qd_cdc import ff, net


class ClockEndpointTests(unittest.TestCase):
    def test_derived_launch_clock_never_gets_candidate(self):
        cells = {'src': ff(1, 2, 12), 'first': ff(2, 3, 11, True),
                 'second': ff(3, 4, 11, True),
                 'clock_gate': {'type': '$_BUF_', 'connections': {'A': [10], 'Y': [12]},
                                'port_directions': {'A': 'input', 'Y': 'output'}}}
        rows = check(net(cells), 'top')
        path = next(r for r in rows if r['destination_cell'] == 'first')
        self.assertEqual(path['classification'], 'UNKNOWN')
        self.assertEqual(path['source_cell'], 'src')
        self.assertIn('source clock unresolved', path['path'][-1])
        self.assertEqual(path['source_clock_bit'], '12')
        self.assertNotIn('CANDIDATE_SYNCHRONIZER', [r['classification'] for r in rows])

    def test_unsupported_driver_on_input_clock_is_unknown_at_both_ends(self):
        cells = {'src': ff(1, 2, 10), 'dst': ff(2, 3, 11),
                 'box': {'type': 'CLOCK_BOX', 'connections': {'Y': [10]},
                         'port_directions': {'Y': 'output'}}}
        design = net(cells)
        design['modules']['top']['ports']['clock_alias'] = {'direction': 'input', 'bits': [10]}
        rows = check(design, 'top')
        self.assertTrue(any(r['destination_cell']=='src' and
                            'gated/derived or unresolved clock' in r['path'] for r in rows))
        path = next(r for r in rows if r['destination_cell']=='dst')
        self.assertEqual(path['classification'], 'UNKNOWN')

    def test_same_net_opposite_edges_are_visible(self):
        for launch, capture in [('P', 'N'), ('N', 'P')]:
            cells = {'src': ff(1, 2, 10), 'dst': ff(2, 3, 10)}
            cells['src']['type'] = '$_DFF_'+launch+'_'
            cells['dst']['type'] = '$_DFF_'+capture+'_'
            rows = check(net(cells), 'top')
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]['classification'], 'UNKNOWN')
            self.assertIn('same-net opposite-edge timing unverified', rows[0]['path'])
            self.assertNotEqual(rows[0]['source_clock_edge'], rows[0]['destination_clock_edge'])

    def test_resolved_clocks_preserve_positive_and_same_edge_results(self):
        cells = {'src': ff(1, 2, 10), 'dst': ff(2, 3, 11)}
        self.assertEqual(check(net(cells), 'top')[0]['classification'], 'CROSSING')
        cells['dst']['connections']['C'] = [10]
        self.assertEqual(check(net(cells), 'top'), [])

    def test_clock_findings_do_not_depend_on_cell_order(self):
        cells = {'src': ff(1, 2, 10), 'dst': ff(2, 3, 10)}
        cells['dst']['type'] = '$_DFF_N_'
        self.assertEqual(check(net(cells), 'top'),
                         check(net(dict(reversed(list(cells.items())))), 'top'))
