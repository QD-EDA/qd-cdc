import unittest

from qd_cdc import check
from test_qd_cdc import ff, net


def gate(kind, inputs, output=12):
    pins = dict(inputs, Y=[output])
    return {'type': kind, 'connections': pins,
            'port_directions': {p: ('output' if p == 'Y' else 'input') for p in pins},
            'attributes': {'src': 'clock_gate.sv:7'}}


class ClockOriginTests(unittest.TestCase):
    def design(self, clock_cell):
        cells = {'src': ff(1, 2, 12), 'dst': ff(2, 3, 11), 'gate': clock_cell}
        ports = {name: {'direction': 'input', 'bits': [bit]} for name, bit in
                 [('clk_a', 10), ('gate_en', 20), ('clk_b', 11), ('din', 1)]}
        return net(cells, ports)

    def test_gated_launch_origin_retains_unknown(self):
        rows = check(self.design(gate('$_AND_', {'A': [10], 'B': [20]})), 'top')
        crossing = next(r for r in rows if r['source_cell'] == 'src' and r['destination_cell'] == 'dst')
        self.assertEqual(crossing['classification'], 'UNKNOWN')
        self.assertEqual(crossing['source_clock_origin'], {
            'kind': 'one_hop_combinational', 'cell': 'gate', 'cell_type': '$_AND_',
            'location': 'clock_gate.sv:7',
            'inputs': [{'pin': 'A', 'bit': '10', 'ports': [{'port': 'clk_a', 'offset': 0}]},
                       {'pin': 'B', 'bit': '20', 'ports': [{'port': 'gate_en', 'offset': 0}]}]})
        self.assertEqual(crossing['destination_clock_origin'], {
            'kind': 'direct_primary_input', 'ports': [{'port': 'clk_b', 'offset': 0}]})

    def test_buffer_and_port_aliases(self):
        design = self.design(gate('$_BUF_', {'A': [10]}))
        design['modules']['top']['ports']['clock_alias'] = {'direction': 'input', 'bits': [10]}
        row = next(r for r in check(design, 'top') if r['source_cell'] == 'src' and r['destination_cell'] == 'dst')
        self.assertEqual(row['source_clock_origin']['inputs'][0]['ports'], [
            {'port': 'clk_a', 'offset': 0}, {'port': 'clock_alias', 'offset': 0}])
        self.assertEqual(row['classification'], 'UNKNOWN')

    def test_ambiguous_unsupported_constant_and_loop_do_not_invent_origin(self):
        variants = [
            {'box': {'type': 'CLOCK_BOX', 'connections': {'Y': [12]},
                     'port_directions': {'Y': 'output'}}},
            {'other': gate('$_BUF_', {'A': [20]})},
            {},
            {},
        ]
        for index, extra in enumerate(variants):
            with self.subTest(index=index):
                first = gate('$_AND_', {'A': [10], 'B': [20]})
                if index == 2:
                    first['connections']['B'] = ['0']
                if index == 3:
                    first['connections']['B'] = [12]
                design = self.design(first)
                design['modules']['top']['cells'].update(extra)
                row = next(r for r in check(design, 'top')
                           if r['source_cell'] == 'src' and r['destination_cell'] == 'dst')
                self.assertEqual(row['classification'], 'UNKNOWN')
                self.assertEqual(row['source_clock_origin']['kind'], 'UNKNOWN')

    def test_direct_clocks_keep_existing_crossing(self):
        cells = {'src': ff(1, 2, 10), 'dst': ff(2, 3, 11)}
        rows = check(net(cells), 'top')
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['classification'], 'CROSSING')
        self.assertEqual(rows[0]['source_clock_origin']['kind'], 'direct_primary_input')
