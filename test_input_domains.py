import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from qd_cdc import check, main
from test_qd_cdc import ff, net


def design():
    return net({'dst': ff(2, 3, 10)}, {'din': {'direction': 'input', 'bits': [2]},
               'clk_a': {'direction': 'input', 'bits': [11]},
               'clk_b': {'direction': 'input', 'bits': [10]}})


def domains(clock='clk_a'):
    return {'din': {'clock': clock, 'evidence': 'test harness launch clock'}}


class InputDomainTests(unittest.TestCase):
    def test_unmapped_input_is_unknown_only_when_audit_requested(self):
        self.assertEqual(check(design(), 'top'), [])
        report = check(design(), 'top', input_domains={})
        self.assertEqual(len(report), 1)
        self.assertEqual(report[0]['classification'], 'UNKNOWN')
        self.assertEqual(report[0]['source_ports'], [{'port': 'din', 'offset': 0}])
        self.assertEqual(report[0]['source_bit'], '2')

    def test_explicit_crossing_and_same_clock_assumption(self):
        report = check(design(), 'top', input_domains=domains())
        self.assertEqual(report[0]['classification'], 'CROSSING')
        self.assertEqual(report[0]['source_clock'], '11')
        self.assertEqual(report[0]['input_domain_assumptions'], [dict(port='din', **domains()['din'])])
        self.assertEqual(check(design(), 'top', input_domains=domains('clk_b')), [])

    def test_combinational_fanin_keeps_each_primary_input(self):
        data = design(); mod = data['modules']['top']
        mod['ports']['sel'] = {'direction': 'input', 'bits': [4]}
        mod['cells']['gate'] = {'type': '$_AND_', 'connections': {'A': [2], 'B': [4], 'Y': [5]},
                                'port_directions': {'A': 'input', 'B': 'input', 'Y': 'output'}}
        mod['cells']['dst']['connections']['D'] = [5]
        report = check(data, 'top', input_domains=domains())
        self.assertEqual(sorted(r['classification'] for r in report), ['CROSSING', 'UNKNOWN'])
        self.assertTrue(all(r['path'][0] == 'gate.Y' for r in report))

    def test_alias_conflict_and_invalid_constraints_rejected(self):
        for value in ([], {'missing': domains()['din']}, domains('absent'),
                      {'din': {'clock': 'clk_a'}}, {'din': {'clock': 'clk_a', 'evidence': ''}},
                      {'din': {'clock': 'clk_a', 'evidence': 'x', 'typo': True}}):
            with self.assertRaises(ValueError): check(design(), 'top', input_domains=value)
        data=design(); data['modules']['top']['ports']['alias']={'direction':'input','bits':[2]}
        mapping=domains(); mapping['alias']={'clock':'clk_b','evidence':'conflict'}
        with self.assertRaises(ValueError): check(data, 'top', input_domains=mapping)
        data['modules']['top']['ports']['clk_a']['bits']=[11,12]
        with self.assertRaises(ValueError): check(data, 'top', input_domains=domains())

    def test_vector_offsets_aliases_and_order_are_deterministic(self):
        data=design(); mod=data['modules']['top']
        mod['ports']['din']['bits']=[1,2]
        mod['ports']['alias']={'direction':'input','bits':[2]}
        report=check(data, 'top', input_domains=domains())
        self.assertEqual(report[0]['source_ports'], [{'port':'alias','offset':0},{'port':'din','offset':1}])
        mod['ports']=dict(reversed(list(mod['ports'].items())))
        self.assertEqual(report, check(data, 'top', input_domains=domains()))

    def test_annotated_chain_is_still_only_a_candidate(self):
        data=design(); cells=data['modules']['top']['cells']
        cells['dst']=ff(2,3,10,True); cells['stage2']=ff(3,4,10,True)
        report=check(data,'top',input_domains=domains())
        self.assertEqual(report[0]['classification'],'CANDIDATE_SYNCHRONIZER')

    def test_internally_driven_input_or_declared_clock_stays_unknown(self):
        for driven in (2,11):
            data=design()
            data['modules']['top']['cells']['driver']={
                'type':'$_BUF_', 'connections':{'A':[10],'Y':[driven]},
                'port_directions':{'A':'input','Y':'output'}}
            report=check(data,'top',input_domains=domains())
            self.assertEqual(report[0]['classification'],'UNKNOWN')
            self.assertIn('internal driver',report[0]['path'][-1])

    def test_cli_records_constraints_even_when_no_crossing(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder); (root/'net.json').write_text(json.dumps(design()))
            (root/'domains.json').write_text(json.dumps(domains('clk_b')))
            out=io.StringIO()
            with contextlib.redirect_stdout(out):
                result=main(['check',str(root/'net.json'),'--top','top','--json',
                             '--input-domains',str(root/'domains.json')])
            self.assertEqual(result,0)
            report=json.loads(out.getvalue())
            self.assertEqual(report['findings'],[])
            self.assertEqual(report['input_domains'],domains('clk_b'))
            self.assertEqual(report['scope'],'input-domain structural audit; not CDC safety proof')
