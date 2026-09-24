import copy
import unittest

from qd_cdc import check
from test_async_reset import reset_ff
from test_qd_cdc import ff, net


class SyncStructureTest(unittest.TestCase):
    def crossing(self, cells):
        return next(r for r in check(net(cells), 'top') if r['classification'] == 'CROSSING')

    def test_unannotated_two_stage_chain_is_visible_but_still_crossing(self):
        cells = {'src': ff(1, 2, 10), 'first': reset_ff(2, 3, 11),
                 'second': reset_ff(3, 4, 11)}
        row = self.crossing(cells)
        self.assertEqual(row['synchronizer_structure'], {
            'status': 'two_stage_structure', 'safety': 'UNKNOWN',
            'first_stage': {'cell': 'first', 'location': 'fixture.sv:4', 'q_bit': '3'},
            'second_stage': {'cell': 'second', 'location': 'fixture.sv:4'},
            'first_q_consumers': [{'cell': 'second', 'port': 'D'}],
            'reason': ''})
        self.assertEqual(sum(r['classification'] == 'UNKNOWN' for r in check(net(cells), 'top')), 2)

    def test_side_consumer_and_reset_mismatch_keep_structure_unknown(self):
        base = {'src': ff(1, 2, 10), 'first': reset_ff(2, 3, 11),
                'second': reset_ff(3, 4, 11)}
        side = copy.deepcopy(base)
        side['side'] = {'type': '$_BUF_', 'connections': {'A': [3], 'Y': [5]},
                        'port_directions': {'A': 'input', 'Y': 'output'}}
        row = self.crossing(side)
        self.assertEqual(row['synchronizer_structure']['status'], 'UNKNOWN')
        self.assertEqual(row['synchronizer_structure']['reason'], 'first-stage Q has other consumers')
        self.assertEqual(row['synchronizer_structure']['first_q_consumers'], [
            {'cell': 'second', 'port': 'D'}, {'cell': 'side', 'port': 'A'}])
        mismatch = copy.deepcopy(base)
        mismatch['second']['connections']['R'] = [21]
        row = self.crossing(mismatch)
        self.assertEqual(row['synchronizer_structure']['reason'], 'clock/edge/reset mismatch')
        mismatch = copy.deepcopy(base)
        mismatch['second']['connections']['C'] = [12]
        self.assertEqual(self.crossing(mismatch)['synchronizer_structure']['reason'],
                         'clock/edge/reset mismatch')
        mismatch = copy.deepcopy(base)
        mismatch['second']['type'] = '$_DFF_NN0_'
        self.assertEqual(self.crossing(mismatch)['synchronizer_structure']['reason'],
                         'clock/edge/reset mismatch')

    def test_unsupported_or_ambiguous_second_stage_is_not_chain(self):
        base = {'src': ff(1, 2, 10), 'first': ff(2, 3, 11), 'second': ff(3, 4, 11)}
        unsupported = copy.deepcopy(base)
        unsupported['second']['type'] = 'VENDOR_FF'
        row = self.crossing(unsupported)
        self.assertEqual(row['synchronizer_structure']['status'], 'UNKNOWN')
        self.assertEqual(row['synchronizer_structure']['reason'], 'no unique mapped second stage')
        ambiguous = copy.deepcopy(base)
        ambiguous['extra'] = ff(5, 3, 11)
        row = self.crossing(ambiguous)
        self.assertEqual(row['synchronizer_structure']['reason'], 'first-stage Q has ambiguous driver')

    def test_zero_and_multiple_second_stages_are_unknown(self):
        base = {'src': ff(1, 2, 10), 'first': ff(2, 3, 11)}
        self.assertEqual(self.crossing(base)['synchronizer_structure']['reason'],
                         'no unique mapped second stage')
        base['second'] = ff(3, 4, 11)
        base['third'] = ff(3, 5, 11)
        self.assertEqual(self.crossing(base)['synchronizer_structure']['reason'],
                         'no unique mapped second stage')

    def test_first_stage_q_export_is_visible_fanout(self):
        cells = {'src': ff(1, 2, 10), 'first': ff(2, 3, 11),
                 'second': ff(3, 4, 11)}
        design = net(cells)
        design['modules']['top']['ports']['tap'] = {'direction': 'output', 'bits': [3]}
        row = next(r for r in check(design, 'top') if r['classification'] == 'CROSSING')
        self.assertEqual(row['synchronizer_structure']['status'], 'UNKNOWN')
        self.assertIn({'cell': 'TOP_OUTPUT', 'port': 'tap'},
                      row['synchronizer_structure']['first_q_consumers'])

    def test_annotated_candidate_with_side_fanout_exposes_uncertainty(self):
        cells = {'src': ff(1, 2, 10), 'first': ff(2, 3, 11, True),
                 'second': ff(3, 4, 11, True),
                 'side': {'type': '$_BUF_', 'connections': {'A': [3], 'Y': [5]},
                          'port_directions': {'A': 'input', 'Y': 'output'}}}
        row = next(r for r in check(net(cells), 'top')
                   if r['classification'] == 'CANDIDATE_SYNCHRONIZER')
        self.assertEqual(row['synchronizer_structure']['status'], 'UNKNOWN')
        self.assertEqual(row['synchronizer_structure']['reason'],
                         'first-stage Q has other consumers')


if __name__ == '__main__':
    unittest.main()
