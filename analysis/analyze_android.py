#!/usr/bin/env python3
"""Independently audit Android request evidence and aggregate measured repeats."""
import argparse
import collections
import csv
import datetime as dt
import json
import math
from pathlib import Path
import statistics
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import run_study as core

ROOT=core.ROOT


def audit(path, samples, planned, models, exploratory=False):
    r=json.loads(path.read_text()); t=r['task'];folder=path.parent
    errors=[]
    if r.get('status')!='ok':return r,['status_'+r.get('status','missing')]
    req=json.loads((folder/'request.json').read_text());prompt=json.loads((folder/'prompt.json').read_text())
    events=[json.loads(x) for x in (folder/'stream.jsonl').read_text().splitlines()]
    final=events[-1]['event'];tm=final.get('timings',{})
    counts=sum(len(e['event'].get('tokens',[])) for e in events if not e['event'].get('stop'))
    checks={'prompt_exact':len(prompt['tokens'])==t['input_tokens']==len(req['prompt'])==final.get('tokens_evaluated')==tm.get('prompt_n'),
            'output_exact':t['output_tokens']==final.get('tokens_predicted')==tm.get('predicted_n')==counts,
            'prompt_matches_request':req['prompt']==prompt['tokens'],
            'limit_stop':final.get('stop_type')=='limit','no_truncation':final.get('truncated') is False,
            'cache_disabled':req.get('cache_prompt') is False and tm.get('cache_n')==0,
            'context_fits':t['input_tokens']+t['output_tokens']<=3072,
            'preload_gate':r.get('preload_gate',{}).get('accepted') is True or (exploratory and (r.get('preload_gate',{}).get('proceeding_under_exploratory_scope') or (r.get('preload_gate',{}).get('skipped') and r['preload_gate'].get('exploratory')))),
            'request_gate':r.get('request_gate',{}).get('accepted') is True or (exploratory and r.get('request_gate',{}).get('skipped') and r['request_gate'].get('exploratory') and r['request_gate'].get('thermal_status_before')==0),
            'prefill_rate_units':math.isclose(tm.get('prompt_per_second',0),tm.get('prompt_n',0)/(tm.get('prompt_ms',0)/1000),rel_tol=1e-7),
            'decode_rate_units':math.isclose(tm.get('predicted_per_second',0),tm.get('predicted_n',0)/(tm.get('predicted_ms',0)/1000),rel_tol=1e-7)}
    checks['matches_frozen_plan']=planned.get(t['id'])==t
    checks['matches_frozen_model']=models.get(t['model_id'])==r.get('model')
    server=path.parents[2]/r['server_log']
    startup=server.read_text()
    checks['cpu_context_cache_startup']=bool('CPU_Mapped model buffer' in startup and 'CPU KV buffer' in startup and 'K (f16)' in startup and 'V (f16)' in startup and __import__('re').search(r'n_ctx\s*=\s*3072',startup)) if t['cache_type']=='f16' else bool('CPU_Mapped model buffer' in startup and 'K (q8_0)' in startup and 'V (q8_0)' in startup)
    if t['phase']!='smoke' and not exploratory:
        gate=r.get('request_gate',{})
        end=dt.datetime.fromisoformat(gate['at']).timestamp()
        window=[s for s in samples if end-62<=s.get('unix',0)<=end]
        vals=[s['soc_temperature_celsius'] for s in window if s.get('soc_temperature_celsius') is not None]
        active=[s['system_cpu_active_ratio'] for s in window if s.get('system_cpu_active_ratio') is not None]
        checks['strict_temperature_recomputed']=bool(gate.get('strict_stabilization_required') and len(vals)>=25 and max(vals)-min(vals)<=1.00001 and statistics.mean(vals)<=gate['idle_baseline_celsius']+2.00001 and window[-1]['unix']-window[0]['unix']>=57.5)
        checks['idle_and_status_recomputed']=bool(window and all(s.get('thermal_status')==0 for s in window) and active and statistics.mean(active)<=.35001)
    errors=[k for k,v in checks.items() if not v]
    return r,errors


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--session',required=True);args=ap.parse_args()
    s=ROOT/'results'/args.session;out=ROOT/'analysis'/args.session;out.mkdir(parents=True,exist_ok=True)
    provenance=json.loads((s/'provenance.json').read_text());plan=json.loads((s/'plan.json').read_text()) if (s/'plan.json').exists() else []
    exploratory=provenance['adaptation'].get('scope')=='exploratory-presentation'
    transport=provenance['adaptation'].get('transport','wireless ADB forward')
    required_gap=provenance['adaptation'].get('minimum_repeat_gap_seconds',120)
    planned={t['id']:t for t in plan};models={m['id']:m for m in json.loads((s/'models.json').read_text())}
    samples=[json.loads(x) for x in (s/'sensors.jsonl').read_text().splitlines()]
    all_records=[json.loads(p.read_text()) for p in (s/'runs').glob('*/result.json')]
    gap_errors=set();repeat_gaps=[]
    for r in all_records:
        if r.get('status')!='ok' or r['task'].get('phase') not in ('main','kv'):continue
        t=r['task'];key=(t['model_id'],t['input_tokens'],t['output_tokens'],t['cache_type'])
        preceding=[p for p in all_records if p is not r and p.get('status')=='ok' and p.get('request_start_unix',1e20)<r['request_start_unix'] and (p['task']['model_id'],p['task']['input_tokens'],p['task']['output_tokens'],p['task']['cache_type'])==key]
        if preceding:
            gap=r['request_start_unix']-max(p['request_end_unix'] for p in preceding);repeat_gaps.append(gap)
            if gap<required_gap:gap_errors.add(r['run_id'])
    valid=[];failures=[];seen=set();raw=[]
    for p in sorted((s/'runs').glob('*/result.json')):
        r,errors=audit(p,samples,planned,models,exploratory);raw.append(r)
        if r['run_id'] in gap_errors:errors.append('repeat_gap_below_frozen_requirement')
        if errors:failures.append({'record':str(p.relative_to(ROOT)),'errors':errors});continue
        if r['task']['id'] in seen:raise RuntimeError('multiple valid observations for same planned task')
        seen.add(r['task']['id']);t=r['task'];tm=r['runtime_timings']
        valid.append({'run_id':r['run_id'],'record_path':str(p.relative_to(ROOT)),'phase':t['phase'],'model_id':t['model_id'],
                      'input_tokens':t['input_tokens'],'output_tokens':t['output_tokens'],'cache_type':t['cache_type'],'repetition':t['repetition'],
                      'context_capacity_tokens':3072,'logical_prompt_plus_output_tokens':t['input_tokens']+t['output_tokens'],
                      'final_occupied_kv_positions_reported':r['final'].get('tokens_cached'),
                      'prefill_seconds':tm['prompt_ms']/1000,'prefill_tokens_per_second':tm['prompt_per_second'],
                      'decode_seconds':tm['predicted_ms']/1000,'decode_tokens_per_second':tm['predicted_per_second'],
                      'request_wall_seconds':r['request_wall_seconds'],'ttft_host_arrival_seconds':r['ttft_seconds'],
                      'itl_host_arrival_median_seconds':r['itl_median_seconds'],
                      'sampled_peak_rss_mib':r['sampled_peak_rss_kib']/1024 if r.get('sampled_peak_rss_kib') is not None else None,
                      'peak_soc_temperature_celsius':r.get('peak_soc_temperature_celsius'),
                      'mean_process_cpu_percent_one_core_100':r.get('mean_process_cpu_percent_one_core_100'),
                      'minimum_mem_available_mib':r['minimum_mem_available_kib']/1024 if r.get('minimum_mem_available_kib') is not None else None,
                      'thermal_statuses':','.join(map(str,r.get('thermal_statuses',[]))),
                      'request_energy_joules':None})
    grouped=collections.defaultdict(list)
    for r in valid:
        if r['phase']=='main':grouped[(r['model_id'],r['input_tokens'],r['output_tokens'],r['cache_type'])].append(r)
    aggregates=[]
    metrics=['prefill_seconds','prefill_tokens_per_second','decode_seconds','decode_tokens_per_second','request_wall_seconds','ttft_host_arrival_seconds','itl_host_arrival_median_seconds','sampled_peak_rss_mib','peak_soc_temperature_celsius','mean_process_cpu_percent_one_core_100']
    for key,rows in sorted(grouped.items()):
        a=dict(zip(['model_id','input_tokens','output_tokens','cache_type'],key));a['n']=len(rows)
        for metric in metrics:
            vals=[r[metric] for r in rows if r[metric] is not None]
            a[metric+'_mean']=statistics.mean(vals) if vals else None
            a[metric+'_sd']=statistics.stdev(vals) if len(vals)>1 else None
        a['source_run_ids']=[r['run_id'] for r in rows];aggregates.append(a)
    kv=[]
    for cache in ['f16','q8_0']:
        rows=[r for r in valid if r['model_id']=='qwen15_q4' and r['input_tokens']==2048 and r['output_tokens']==128 and r['cache_type']==cache and r['phase'] in ('main','kv')]
        if rows:
            k={'model_id':'qwen15_q4','input_tokens':2048,'output_tokens':128,'cache_type':cache,'n':len(rows),'source_run_ids':[r['run_id'] for r in rows]}
            for metric in metrics:
                vals=[r[metric] for r in rows if r[metric] is not None]
                k[metric+'_mean']=statistics.mean(vals) if vals else None;k[metric+'_sd']=statistics.stdev(vals) if len(vals)>1 else None
            kv.append(k)
    missing=[t['id'] for t in plan if t['id'] not in seen]
    report={'session':args.session,'planned_tasks':len(plan),'validated_tasks':len(seen),'validated_main_observations':sum(r['phase']=='main' for r in valid),
            'scope':provenance['adaptation'].get('scope'),'aggregation':'one observation/configuration; no SD, repeatability, or significance claim' if exploratory else 'means and sample SD across available valid repeats; coverage audited',
            'unique_main_configurations':len(grouped),'configurations_with_three_observations':sum(len(v)==3 for v in grouped.values()),
            'expected_main_configurations':len({(t['model_id'],t['input_tokens'],t['output_tokens'],t['cache_type']) for t in plan if t['phase']=='main'}),
            'expected_main_observations':sum(t['phase']=='main' for t in plan),
            'adopted_full_matrix_configurations':24,'adopted_full_matrix_observations':72,'missing_tasks':missing,'invalid_or_failed_records':failures,
            'minimum_repeat_gap_seconds':min(repeat_gaps) if repeat_gaps else None,'energy_status':'unavailable: no validated meter/counter; charging',
            'latency_boundary':'host-side SSE arrival over '+transport+'; not internal TTFT/ITL',
            'temperature_boundary':'current HAL soc-thmzone type0 SoC proxy; sensor calibration/freshness not independently verified',
            'device':'realme RMX3930/T612, Android14/API34, 5.63GiB OS-visible RAM; user identifies as C61',
            'comparability':'Mac main matrix is exploratory n=1 without strict stabilization; do not pool devices or claim a controlled study',
            'provenance':provenance}
    core.save(out/'audit.json',report);core.save(out/'validated_runs.json',valid);core.save(out/'aggregates.json',aggregates);core.save(out/'kv_comparison.json',kv)
    for name,rows in [('validated_runs.csv',valid),('aggregates.csv',aggregates)]:
        if rows:
            with (out/name).open('w',newline='') as f:
                w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    lines=['# Android experiment audit','',f"Session: `{args.session}`. Validated main observations in this session: {report['validated_main_observations']}/{report['expected_main_observations']}; unique main configurations: {len(grouped)}/{report['expected_main_configurations']}.",
           f"Configurations with three observations: {report['configurations_with_three_observations']}. Failed/invalid records: {len(failures)}. The preserved repeated protocol would require 72 main observations; the current presentation scope is 24 once each. Smoke and pilot sessions are separate.",'',
           'Each observation is rechecked against its saved prompt, request, final SSE event, output stream count, exact token budgets, no-cache and no-truncation conditions, stop type, frozen thermal policy, and runtime rate denominators.',
           '', 'Memory uses sampled process RSS in MiB (KiB / 1024); sample peak is not an OS lifetime maximum. CPU percent uses one core = 100%, so four threads can exceed 100%. Temperature is the HAL SoC proxy. Energy, decode J/token, and tokens/s/W are unavailable.',
           '', 'Context capacity is 3,072 positions; prompt plus returned output is a separate logical budget. The final tokens_cached field reports occupied KV positions, excluding the final returned token if it was not evaluated into KV. F16 KV allocation capacity is fixed across the main matrix. Request wall time starts from an already tokenized prompt and excludes model startup and client template/tokenization preparation; it is not full application launch-to-answer latency.',
           '', 'Host first/inter-token arrivals include '+transport+'. Runtime prefill and decode are the preferred performance measurements. Charging, screen-off state, stock DVFS, missing ambient measurement, and thermal service limitations accompany conclusions.',
           '', ('Current Android and Mac matrices are exploratory n=1; no SD, repeatability, significance, or strict thermal-control claim.' if exploratory else 'Mac comparison must retain the existing n=1 exploratory limitation. Android repeats do not retroactively validate the Mac protocol.'),'']
    (out/'SUMMARY.md').write_text('\n'.join(lines))
    if grouped or samples:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    if grouped:
        fig,axs=plt.subplots(2,2,figsize=(11,7.5),sharex=True)
        for row,output in enumerate([128,512]):
            for col,prefix in enumerate(['qwen05','qwen15']):
                ax=axs[row,col]
                for quant,marker in [('q4','o'),('q8','s')]:
                    rows=[a for a in aggregates if a['model_id']==prefix+'_'+quant and a['output_tokens']==output];rows.sort(key=lambda a:a['input_tokens'])
                    if rows:
                        ax.errorbar([a['input_tokens'] for a in rows],[a['decode_tokens_per_second_mean'] for a in rows],yerr=[a['decode_tokens_per_second_sd'] if a['decode_tokens_per_second_sd'] is not None else math.nan for a in rows],marker=marker,capsize=3,label=quant.upper())
                ax.set(title=f"{'0.5B' if prefix=='qwen05' else '1.5B'} · {output} output tokens",xlabel='Actual input tokens',ylabel='Runtime decode tokens/s')
                ax.set_xticks([256,1024,2048]);ax.grid(alpha=.2)
                if ax.lines:ax.legend()
        fig.suptitle('Android CPU exploratory single pass: n=1 per configuration; no SD' if exploratory else 'Android CPU: means; sample SD bars where n ≥ 2 (see coverage audit)')
        fig.tight_layout();fig.savefig(out/'decode_throughput.png',dpi=200);plt.close(fig)
        fig,axs=plt.subplots(2,2,figsize=(11,7.5))
        charts=[('prefill_seconds','Runtime prefill (s)'),('request_wall_seconds','Request wall time (s)'),('sampled_peak_rss_mib','Sampled peak process RSS (MiB)'),('peak_soc_temperature_celsius','Peak HAL SoC temperature (°C)')]
        for ax,(metric,label) in zip(axs.flat,charts):
            for prefix,style in [('qwen05','-'),('qwen15','--')]:
                for quant,marker in [('q4','o'),('q8','s')]:
                    rows=sorted([a for a in aggregates if a['model_id']==prefix+'_'+quant and a['output_tokens']==512 and a[metric+'_mean'] is not None],key=lambda a:a['input_tokens'])
                    if rows:
                        ax.errorbar([a['input_tokens'] for a in rows],[a[metric+'_mean'] for a in rows],yerr=[a[metric+'_sd'] if a[metric+'_sd'] is not None else math.nan for a in rows],linestyle=style,marker=marker,capsize=3,label=f"{'0.5B' if prefix=='qwen05' else '1.5B'} {quant.upper()}")
            ax.set(xlabel='Actual input tokens',ylabel=label);ax.set_xticks([256,1024,2048]);ax.grid(alpha=.2)
            if ax.lines:ax.legend(fontsize=8)
        fig.suptitle('Android CPU, 512 output tokens: one observation per configuration' if exploratory else 'Android CPU, 512 output tokens: means and sample SD where available')
        fig.tight_layout();fig.savefig(out/'latency_memory_thermal.png',dpi=200);plt.close(fig)
    if samples:
        good=[x for x in samples if x.get('soc_temperature_celsius') is not None]
        if good:
            start=good[0]['unix'];fig,axs=plt.subplots(3,1,figsize=(12,8),sharex=True)
            axs[0].plot([(x['unix']-start)/60 for x in good],[x['soc_temperature_celsius'] for x in good],lw=.8,color='#007d82',label='Current HAL SoC')
            axs[0].plot([(x['unix']-start)/60 for x in good],[x.get('battery',{}).get('temperature_celsius') for x in good],lw=.8,color='#b66d2b',label='Battery')
            baseline_record=json.loads((s/'idle-baseline.json').read_text()) if (s/'idle-baseline.json').exists() else {}
            baseline=baseline_record.get('reference_used_celsius',baseline_record.get('mean_celsius'))
            if baseline is not None:axs[0].axhline(baseline+2,ls=':',color='#555555',label=('Smoke observation + 2°C' if provenance['adaptation']['stage']=='smoke' else 'Fixed idle reference + 2°C'))
            axs[0].set_ylabel('Temperature (°C)');axs[0].legend(loc='upper right',fontsize=8)
            cpu=[x for x in good if x.get('process_cpu_percent_one_core_100') is not None]
            axs[1].plot([(x['unix']-start)/60 for x in cpu],[x['process_cpu_percent_one_core_100'] for x in cpu],lw=.7,color='#142e3a');axs[1].set_ylabel('Process CPU %\n(one core = 100%)')
            mem=[x for x in good if x.get('process_memory_kib',{}).get('VmRSS') is not None]
            axs[2].plot([(x['unix']-start)/60 for x in mem],[x['process_memory_kib']['VmRSS']/1024 for x in mem],lw=.8,color='#6367a4');axs[2].set_ylabel('Process RSS (MiB)');axs[2].set_xlabel('Session elapsed time (minutes)')
            for ax in axs:
                ax.grid(alpha=.2)
                for r in raw:
                    if r.get('task',{}).get('phase')=='main' and r.get('request_start_unix') is not None and r.get('request_end_unix') is not None:
                        ax.axvspan((r['request_start_unix']-start)/60,(r['request_end_unix']-start)/60,color='#007d82',alpha=.08)
            title='Instrumentation smoke telemetry; no strict thermal-control claim' if provenance['adaptation']['stage']=='smoke' else 'Android session telemetry; shaded intervals are main measured requests'
            fig.suptitle(title)
            fig.tight_layout();fig.savefig(out/'session_telemetry.png',dpi=180);plt.close(fig)
    print(json.dumps({k:v for k,v in report.items() if k!='provenance'},indent=2))


if __name__=='__main__':main()
