#!/usr/bin/env python3
"""Collect structural request/acknowledge evidence; never claim protocol safety."""
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys
import time

PIN = '7a3ad34b6d483f4d1d69ac670ddb1c45f1172e19'
TOP = 'prim_sync_reqack'


def main():
    if len(sys.argv) != 3:
        sys.exit('usage: run_opentitan_reqack_pilot.py OPENTITAN_ROOT NEW_EVIDENCE_DIRECTORY')
    ot, out = [Path(p).resolve() for p in sys.argv[1:]]
    repo = Path(__file__).resolve().parent
    records, summaries = [], []
    def run(name, argv):
        start=time.monotonic()
        r=subprocess.run(argv,cwd=repo,capture_output=True,text=True,timeout=120)
        (out/(name+'.stdout')).write_text(r.stdout)
        (out/(name+'.stderr')).write_text(r.stderr)
        records.append(dict(name=name,argv=argv,exit_status=r.returncode,seconds=time.monotonic()-start))
        (out/'commands.json').write_text(json.dumps(records,indent=2)+'\n')
        return r
    try:
        if (subprocess.check_output(['git','rev-parse','HEAD'],cwd=ot,text=True).strip()!=PIN or
                subprocess.check_output(['git','status','--porcelain'],cwd=ot,text=True)):
            raise ValueError('expected clean pinned OpenTitan checkout')
        out.mkdir()
        include=ot/'hw/ip/prim/rtl'
        files=[ot/'hw/ip/prim_generic/rtl/prim_flop.sv',
               ot/'hw/ip/prim_generic/rtl/prim_flop_2sync.sv', include/'prim_sync_reqack.sv']
        # Record the declared assertion-header inventory, not a proven include closure.
        inputs=files+list(include.glob('prim_assert*.sv*'))+[repo/'qd_cdc.py',Path(__file__).resolve()]
        (out/'inputs.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest()
                                                  for p in sorted(set(inputs))},indent=2)+'\n')
        if run('yosys-version',['yosys','-V']).returncode:
            raise ValueError('Yosys unavailable')
        domains={'src_req_i':{'clock':'clk_src_i','evidence':'Pinned upstream interface contract; timing unverified'},
                 'dst_ack_i':{'clock':'clk_dst_i','evidence':'Pinned upstream interface contract; timing unverified'}}
        (out/'domains.json').write_text(json.dumps(domains,indent=2)+'\n')
        # Match the existing QD formal pilot's restricted Yosys command paths.
        def quote(path):
            value=str(path)
            if not re.fullmatch(r'[A-Za-z0-9_./-]+',value):
                raise ValueError('Yosys pilot requires simple paths without spaces or metacharacters')
            return value
        source_args=' '.join(map(quote,files))
        for engine,mode in [('native',0),('native',1),('slang',0),('slang',1)]:
            name=f'{engine}-rz{mode}'
            netlist=out/(name+'.json')
            if engine=='native':
                front=f'read_verilog -sv -I{quote(include)} {source_args}; chparam -set EnRzHs {mode} {TOP}; hierarchy -top {TOP}'
            else:
                front=f'read_slang --top {TOP} -GEnRzHs={mode} -I{quote(include)} {source_args}'
            synth=run(name+'-synthesis',['yosys','-Q','-p',front+
                      f'; proc; flatten; opt; techmap; opt; write_json {quote(netlist)}'])
            if synth.returncode:
                if engine=='native' and mode==1:
                    summaries.append(dict(configuration=name,qualification='UNKNOWN',reason='native RZ synthesis failed; inspect raw diagnostics'))
                    continue
                raise ValueError(name+': required synthesis failed')
            cmd=[sys.executable,str(repo/'qd_cdc.py'),'check',str(netlist),'--top',TOP,
                 '--input-domains',str(out/'domains.json'),'--json']
            first=run(name+'-check',cmd);again=run(name+'-repeat',cmd)
            if first.returncode!=1 or again.returncode!=1 or first.stdout!=again.stdout:
                raise ValueError(name+': expected deterministic findings / exit 1')
            ports=json.loads(netlist.read_text())['modules'][TOP]['ports']
            rows=json.loads(first.stdout)['findings']
            crossings=[r for r in rows if r['classification']=='CROSSING']
            if len(crossings)!=2 or any(r['classification']=='CANDIDATE_SYNCHRONIZER' for r in rows):
                raise ValueError(name+': crossing inventory mismatch')
            prefix='gen_rz_hs_protocol' if mode else 'gen_nrz_hs_protocol'
            expected={prefix+'.'+s for s in (('src_fsm_q','dst_fsm_q') if mode else ('src_req_q','dst_ack_q'))}
            observed=set()
            for row in crossings:
                names={a['name'] for a in row['source_q_aliases']}
                launch=names & expected
                if len(launch)!=1 or not row['source_location'] or not row['destination_location']:
                    raise ValueError(name+': source trace missing')
                signal=next(iter(launch));observed.add(signal)
                channel='req' if signal.rsplit('.',1)[1].startswith('src_') else 'ack'
                capture=prefix+'.'+channel+'_sync.u_sync_1.d_i'
                launch_clock='clk_src_i' if channel=='req' else 'clk_dst_i'
                capture_clock='clk_dst_i' if channel=='req' else 'clk_src_i'
                if (row['source_clock']!=str(ports[launch_clock]['bits'][0]) or
                        row['destination_clock']!=str(ports[capture_clock]['bits'][0])):
                    raise ValueError(name+': wrong launch/capture clock')
                if {'name':capture,'offset':0} not in row['destination_d_aliases']:
                    raise ValueError(name+': wrong capture stage')
            if observed!=expected:
                raise ValueError(name+': missing handshake direction')
            summaries.append(dict(configuration=name,qualification='UNKNOWN',crossings=2,
                                  unknowns=sum(r['classification']=='UNKNOWN' for r in rows),
                                  launch_signals=sorted(observed)))
        if subprocess.check_output(['git','status','--porcelain'],cwd=ot,text=True):
            raise ValueError('application tree changed')
        (out/'summary.json').write_text(json.dumps(dict(opentitan=PIN,
            scope='generic synthesis topology; assertions and metastability unverified',
            synthesis_define=True,simulation_define=False,configurations=summaries),indent=2)+'\n')
        print('UNKNOWN: request/acknowledge topology traced; protocol/reset safety unverified')
        return 2
    except (OSError,ValueError,subprocess.SubprocessError) as error:
        print('pilot: '+str(error),file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
