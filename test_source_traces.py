import unittest
from qd_cdc import check
from test_qd_cdc import ff, net


class SourceTraceTests(unittest.TestCase):
    def design(self):
        cells={'src':ff(1,2,10),'dst':ff(2,3,11)}
        cells['src']['attributes']['src']='launch.sv:7.2-9.4'
        cells['dst']['attributes']['src']='capture.sv:12.2-14.4'
        data=net(cells)
        data['modules']['top']['netnames']={
            'bus':{'bits':[9,2,2]}, 'u.sync.d_i':{'bits':[2]}}
        return data

    def test_both_locations_and_all_alias_offsets_survive(self):
        row=check(self.design(),'top')[0]
        self.assertEqual(row['source_location'],'launch.sv:7.2-9.4')
        self.assertEqual(row['destination_location'],'capture.sv:12.2-14.4')
        expected=[{'name':'bus','offset':1},{'name':'bus','offset':2},{'name':'u.sync.d_i','offset':0}]
        self.assertEqual(row['source_q_aliases'],expected)
        self.assertEqual(row['destination_d_aliases'],expected)
        self.assertEqual(row['source'],'capture.sv:12.2-14.4')

    def test_metadata_does_not_change_classification_or_order(self):
        data=self.design();before=check(data,'top')
        data['modules']['top']['netnames']=dict(reversed(list(data['modules']['top']['netnames'].items())))
        self.assertEqual(before,check(data,'top'))
        data['modules']['top']['cells']['dst']['connections']['C']=[10]
        self.assertEqual(check(data,'top'),[])

    def test_missing_locations_aliases_and_constants_are_explicit(self):
        data=self.design();mod=data['modules']['top']
        mod.pop('netnames');mod['cells']['src']['attributes'].pop('src')
        row=check(data,'top')[0]
        self.assertEqual(row['source_location'],'')
        self.assertEqual(row['source_q_aliases'],[])
        mod['netnames']={'constant':{'bits':['0','1','x','z']}}
        self.assertEqual(check(data,'top')[0]['source_q_aliases'],[])

    def test_unknown_path_retains_endpoint_metadata(self):
        data=self.design();mod=data['modules']['top']
        mod['cells']['dst']['connections']['C']=[10]
        mod['cells']['dst']['type']='$_DFF_N_'
        row=check(data,'top')[0]
        self.assertEqual(row['classification'],'UNKNOWN')
        self.assertEqual(row['source_location'],'launch.sv:7.2-9.4')
        self.assertTrue(row['source_q_aliases'])

    def test_malformed_alias_metadata_is_rejected(self):
        for bad in (None,[],{'bad':None},{'bad':{'bits':None}},
                    {'bad':{'bits':[True]}},{'bad':{'bits':[-1]}},{'bad':{'bits':['2']}}):
            with self.subTest(bad=bad):
                data=self.design();data['modules']['top']['netnames']=bad
                with self.assertRaises(ValueError):check(data,'top')
