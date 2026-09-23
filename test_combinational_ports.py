import copy
import unittest
from qd_cdc import check
from test_qd_cdc import ff, net

# Explicit pin inventory from the Yosys simulation models, independent of checker tables.
PINS={'BUF':'A','NOT':'A','AND':'AB','NAND':'AB','OR':'AB','NOR':'AB',
      'XOR':'AB','XNOR':'AB','MUX':'ABS','AOI3':'ABC','OAI3':'ABC',
      'AOI4':'ABCD','OAI4':'ABCD'}


def gate(kind):
    return {'type':'$_'+kind+'_', 'connections':{**{p:[2] for p in PINS[kind]},'Y':[6]},
            'port_directions':{**{p:'input' for p in PINS[kind]},'Y':'output'}}


class CombinationalPortTests(unittest.TestCase):
    def test_every_input_including_mux_select_is_traced(self):
        for kind,pins in PINS.items():
            for pin in pins:
                with self.subTest(kind=kind,pin=pin):
                    cells={'same':ff(1,2,10),'foreign':ff(4,5,11),'gate':gate(kind),'dst':ff(6,3,10)}
                    cells['gate']['connections'][pin]=[5]
                    rows=check(net(cells),'top')
                    self.assertEqual(len(rows),1)
                    self.assertEqual(rows[0]['classification'],'CROSSING')
                    self.assertEqual(rows[0]['source_cell'],'foreign')
                    self.assertEqual(rows[0]['path'],['gate.Y','foreign.Q'])

    def test_malformed_cells_cannot_disappear_or_resolve(self):
        for kind in PINS:
            for mutation in ('direction','missing','extra','wide','null-pin','bad-bit',
                             'null-connections','null-directions','string-pin','bool-bit'):
                with self.subTest(kind=kind,mutation=mutation):
                    cells={'src':ff(1,2,10),'gate':gate(kind),'dst':ff(6,3,10)}
                    data=net(cells);g=cells['gate']
                    if mutation=='direction':g['port_directions']['A']='output'
                    if mutation=='missing':del g['connections']['A']
                    if mutation=='extra':g['connections']['EXTRA']=[30]
                    if mutation=='wide':g['connections']['A']=[2,5]
                    if mutation=='null-pin':g['connections']['A']=None
                    if mutation=='bad-bit':g['connections']['A']=['2']
                    if mutation=='null-connections':g['connections']=None
                    if mutation=='null-directions':g['port_directions']=None
                    if mutation=='string-pin':g['connections']['A']='2'
                    if mutation=='bool-bit':g['connections']['A']=[True]
                    rows=check(data,'top')
                    self.assertTrue(rows)
                    self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
                    self.assertTrue(any(r['source_cell']=='gate' for r in rows))
                    other=copy.deepcopy(data)
                    other['modules']['top']['cells']=dict(reversed(list(cells.items())))
                    self.assertEqual(rows,check(other,'top'))

    def test_wrong_input_direction_previously_hid_a_crossing(self):
        cells={'same':ff(1,2,10),'foreign':ff(4,5,11),'gate':gate('AND'),'dst':ff(6,3,10)}
        cells['gate']['connections']['B']=[5]
        data=net(cells)
        cells['gate']['port_directions']['B']='output'
        self.assertTrue(check(data,'top'))
        self.assertTrue(all(r['classification']=='UNKNOWN' for r in check(data,'top')))

    def test_valid_same_clock_and_constant_boundaries(self):
        for kind in PINS:
            cells={'src':ff(7,2,10),'gate':gate(kind),'dst':ff(6,3,10)}
            self.assertEqual(check(net(cells),'top'),[])
            data=net(cells)
            for bit in ('0','1','x','z'):
                fixture=copy.deepcopy(data)
                fixture['modules']['top']['cells']['gate']['connections']['A']=[bit]
                rows=check(fixture,'top')
                self.assertTrue(rows)
                self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
                self.assertFalse(any(r['source_cell']=='gate' for r in rows))

    def test_constant_does_not_alias_an_integer_input_net(self):
        for bit in ('0','1'):
            cells={'src':ff(7,2,10),'gate':gate('BUF'),'dst':ff(6,3,10)}
            data=net(cells)
            data['modules']['top']['ports']['unrelated']={'direction':'input','bits':[int(bit)]}
            cells['gate']['connections']['A']=[bit]
            rows=check(data,'top')
            self.assertTrue(rows)
            self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))

    def test_literal_clock_and_reset_cannot_alias_integer_nets(self):
        from test_async_reset import reset_ff
        cells={'src':ff(7,2,10),'first':reset_ff(2,3,11),'second':reset_ff(3,4,11)}
        for name in ('first','second'):cells[name]['attributes']['async_reg']='1'
        data=net(cells)
        cells['first']['connections']['R']=['0']
        cells['second']['connections']['R']=[0]
        rows=check(data,'top')
        self.assertNotIn('CANDIDATE_SYNCHRONIZER',[r['classification'] for r in rows])
        self.assertTrue(any(r.get('destination_reset_bit')=="'0'" for r in rows))
        self.assertTrue(any(r.get('destination_reset_bit')=='0' for r in rows))
        cells['src']['connections']['C']=['1']
        data['modules']['top']['ports']['not_a_constant']={'direction':'input','bits':[1]}
        rows=check(data,'top')
        self.assertNotIn('CROSSING',[r['classification'] for r in rows])
