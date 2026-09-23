import copy
import unittest
from qd_cdc import check
from test_qd_cdc import ff, net


def chain(depth, reconvergent=False):
    cells={'src':ff(7,2,10)};bit=2
    for i in range(depth):
        out=100+i
        cells[f'b{i}']={'type':'$_AND_' if reconvergent else '$_BUF_',
            'connections':{'A':[bit],'Y':[out]},
            'port_directions':{'A':'input','Y':'output'}}
        if reconvergent:
            cells[f'b{i}']['connections']['B']=[bit]
            cells[f'b{i}']['port_directions']['B']='input'
        bit=out
    cells['dst']=ff(bit,3,11)
    return net(cells)


class TraversalTests(unittest.TestCase):
    def test_deep_valid_path_has_complete_trace(self):
        rows=check(chain(1500),'top')
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]['classification'],'CROSSING')
        self.assertEqual(len(rows[0]['path']),1501)
        self.assertEqual(rows[0]['path'][0],'b1499.Y')
        self.assertEqual(rows[0]['path'][-1],'src.Q')

    def test_reconvergence_preserves_all_paths_with_sufficient_budget(self):
        rows=check(chain(8,True),'top')
        self.assertEqual(len(rows),256)
        self.assertTrue(all(r['classification']=='CROSSING' for r in rows))

    def test_budget_exhaustion_is_unknown_and_order_independent(self):
        data=chain(20,True)
        rows=check(data,'top',max_traversal_work=100)
        incomplete=[r for r in rows if r.get('analysis_incomplete')]
        self.assertTrue(incomplete)
        self.assertTrue(all(r['classification']=='UNKNOWN' and r['max_traversal_work']==100 for r in incomplete))
        self.assertTrue(all('unexamined path count unknown' in r['path'][0] for r in incomplete))
        other=copy.deepcopy(data);other['modules']['top']['cells']=dict(reversed(list(other['modules']['top']['cells'].items())))
        for c in other['modules']['top']['cells'].values():
            c['connections']=dict(reversed(list(c['connections'].items())))
        self.assertEqual(rows,check(other,'top',max_traversal_work=100))

    def test_exact_boundary_cannot_be_a_false_clean_result(self):
        data=net({'dst':ff(2,3,10)})
        self.assertEqual(check(data,'top',max_traversal_work=2),[])
        rows=check(data,'top',max_traversal_work=1)
        self.assertEqual(len(rows),1)
        self.assertTrue(rows[0]['analysis_incomplete'])
        for bad in (0,-1,True,1.5,None):
            with self.assertRaises(ValueError):check(data,'top',max_traversal_work=bad)

    def test_loop_and_parent_ambiguity_are_retained(self):
        data=chain(2);cells=data['modules']['top']['cells']
        cells['b0']['connections']['A']=[101]
        rows=check(data,'top')
        self.assertTrue(any('combinational loop' in r['path'] and r['classification']=='UNKNOWN' for r in rows))
        cells['other']=ff(7,101,10)
        rows=check(data,'top')
        self.assertTrue(all(r['classification']=='UNKNOWN' for r in rows))
        self.assertTrue(all('multiple drivers on net 101' in r['path'] for r in rows))

    def test_cli_exposes_incomplete_analysis_and_rejects_bad_budget(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from qd_cdc import main
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'net.json';path.write_text(json.dumps(net({'dst':ff(2,3,10)})))
            args=['check',str(path),'--top','top','--json','--max-traversal-work']
            out=io.StringIO()
            with contextlib.redirect_stdout(out):status=main(args+['1'])
            self.assertEqual(status,1)
            self.assertTrue(json.loads(out.getvalue())[0]['analysis_incomplete'])
            with contextlib.redirect_stderr(io.StringIO()):status=main(args+['0'])
            self.assertEqual(status,2)
