#!/usr/bin/env python3
"""Match individual Mac/Android observations; never pool devices or invent SD."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--android-session',required=True);ap.add_argument('--mac-session',default='mac-20261113-presentation-v2');args=ap.parse_args()
    android=json.loads((ROOT/'analysis'/args.android_session/'validated_runs.json').read_text())
    mac=json.loads((ROOT/'analysis'/args.mac_session/'validated_runs.json').read_text())
    def key(r):return (r['model_id'],r['input_tokens'],r['output_tokens'],r['cache_type'])
    aa={key(r):r for r in android if r['phase']=='main'};mm={key(r):r for r in mac}
    if len(aa)!=len([r for r in android if r['phase']=='main']):raise RuntimeError('comparison requires one Android observation per config; do not overwrite repeated records')
    if len(mm)!=len(mac):raise RuntimeError('comparison requires one Mac observation per config')
    out=ROOT/'analysis'/('two-device-'+args.android_session);out.mkdir(parents=True,exist_ok=True)
    paired=[];issues=[]
    for k in sorted(aa.keys()&mm.keys()):
        a=aa[k];m=mm[k]
        af=ROOT/a['record_path'];mf=ROOT/m['record_path']
        aprompt=json.loads((af.parent/'prompt.json').read_text());mprompt=json.loads((mf.parent/'prompt.json').read_text())
        areq=json.loads((af.parent/'request.json').read_text());mreq=json.loads((mf.parent/'request.json').read_text())
        prompt_equal=aprompt['tokens']==mprompt['tokens'] and aprompt['text']==mprompt['text']
        request_equal=areq==mreq
        if not prompt_equal or not request_equal:issues.append({'config':k,'prompt_equal':prompt_equal,'request_equal':request_equal})
        paired.append({'model_id':k[0],'input_tokens':k[1],'output_tokens':k[2],'cache_type':k[3],'n_mac':1,'n_android':1,
                       'prompt_text_and_tokens_identical':prompt_equal,'request_identical':request_equal,
                       'mac_prefill_tokens_per_second':m['prefill_tokens_per_s'],'android_prefill_tokens_per_second':a['prefill_tokens_per_second'],
                       'mac_decode_tokens_per_second':m['decode_tokens_per_s'],'android_decode_tokens_per_second':a['decode_tokens_per_second'],
                       'mac_over_android_prefill_rate':m['prefill_tokens_per_s']/a['prefill_tokens_per_second'],
                       'mac_over_android_decode_rate':m['decode_tokens_per_s']/a['decode_tokens_per_second'],
                       'mac_request_wall_seconds':m['request_wall_s'],'android_request_wall_seconds':a['request_wall_seconds'],
                       'mac_sampled_peak_rss_mib':m['sampled_peak_rss_mib'],'android_sampled_peak_rss_mib':a['sampled_peak_rss_mib'],
                       'mac_source_record':m['record_path'],'android_source_record':a['record_path']})
    audit={'mac_session':args.mac_session,'android_session':args.android_session,'matched_configurations':len(paired),'expected_configurations':24,
           'missing_android_configs':[list(k) for k in sorted(mm.keys()-aa.keys())],'missing_mac_configs':[list(k) for k in sorted(aa.keys()-mm.keys())],
           'workload_identity_issues':issues,'all_24_matched':len(paired)==24 and not issues,
           'interpretation':'two-device descriptive n=1 points, no SD, repeatability, confidence interval, or causal hardware-only claim',
           'timing_boundary':'runtime prefill/decode; wall and arrival metrics include platform/transport/client costs',
           'build_boundary':'same llama.cpp commit/model hashes and CPU workload; platform-specific CPU kernels and compile options (Mac Accelerate, Android verified ARM dotprod/FP16)',
           'memory_boundary':'sampled process RSS, Mac 1s vs Android 2s cadence; not guaranteed lifetime peak; different OS accounting/runtime allocation',
           'thermal_boundary':'Mac CPU average and Android HAL SoC proxy have different sensor locations/calibration; no direct temperature superiority claim',
           'energy_boundary':'Mac component estimates and Android unvalidated/charging counters are not comparable; no cross-device energy ratio'}
    (out/'audit.json').write_text(json.dumps(audit,indent=2)+'\n');(out/'matched_observations.json').write_text(json.dumps(paired,indent=2)+'\n')
    if paired:
        with (out/'matched_observations.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
        rows=['# Two-device exploratory observations','',f"Matched configurations: **{len(paired)}/24**. Both devices have **n=1 per configuration**; no SD, repeatability or significance claim.",'',
              'Matched prompt text, exact token IDs, and full request JSON are checked across devices. See audit.json for coverage and identity issues. Runtime prefill/decode rates are preferred over host arrival proxies. Native CPU build settings, thermal history, power conditions, operating systems and sensor/sampling boundaries differ. These are observed system results, not an isolated causal hardware experiment.','',
              '| Model / quant | Input / output | Mac prefill tok/s | Android prefill tok/s | Mac decode tok/s | Android decode tok/s |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
        for r in paired:
            rows.append(f"| {r['model_id']} | {r['input_tokens']} / {r['output_tokens']} | {r['mac_prefill_tokens_per_second']:.2f} | {r['android_prefill_tokens_per_second']:.2f} | {r['mac_decode_tokens_per_second']:.2f} | {r['android_decode_tokens_per_second']:.2f} |")
        rows+=['','Energy is unavailable on Android for inference and cannot be compared with the Mac component estimates. Raw record paths are retained for every row.']
        (out/'COMPARISON.md').write_text('\n'.join(rows)+'\n')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        subset=[r for r in paired if r['input_tokens']==2048 and r['output_tokens']==512]
        if subset:
            fig,axs=plt.subplots(1,2,figsize=(12,5))
            for ax,metric,label in [(axs[0],'prefill_tokens_per_second','Runtime prefill tokens/s'),(axs[1],'decode_tokens_per_second','Runtime decode tokens/s')]:
                xx=list(range(len(subset)));width=.36
                ax.bar([x-width/2 for x in xx],[r['mac_'+metric] for r in subset],width,label='M1 Mac (n=1)',color='#142e3a')
                ax.bar([x+width/2 for x in xx],[r['android_'+metric] for r in subset],width,label='T612 Android (n=1)',color='#007d82')
                ax.set_xticks(xx,[r['model_id'].replace('qwen05','0.5B').replace('qwen15','1.5B').replace('_',' ') for r in subset]);ax.set_ylabel(label);ax.set_yscale('log');ax.grid(axis='y',alpha=.2);ax.legend(fontsize=8)
            fig.suptitle('Matched 2,048 input / 512 output: descriptive CPU observations; n=1, no SD')
            fig.tight_layout();fig.savefig(out/'largest_condition_comparison.png',dpi=200);plt.close(fig)
    print(json.dumps(audit,indent=2))

if __name__=='__main__':main()
