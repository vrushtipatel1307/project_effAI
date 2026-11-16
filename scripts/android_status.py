#!/usr/bin/env python3
"""Read progress evidence without contacting/disturbing the Android device."""
import argparse
import json
from pathlib import Path

ap=argparse.ArgumentParser();ap.add_argument('--session',required=True);args=ap.parse_args()
root=Path(__file__).resolve().parents[1];s=root/'results'/args.session

def last_json(path):
    if not path.exists() or not path.stat().st_size:return None
    with path.open('rb') as f:
        f.seek(max(0,path.stat().st_size-32768));lines=f.read().splitlines()
    for line in reversed(lines):
        try:return json.loads(line)
        except json.JSONDecodeError:pass
    return None

records=[json.loads(p.read_text()) for p in (s/'runs').glob('*/result.json')]
phase='idle_preparation';detail={}
folders=list((s/'runs').glob('*'))
if folders:
    latest=max(folders,key=lambda p:p.stat().st_mtime)
    detail['latest_run_id']=latest.name
    if (latest/'result.json').exists():phase=json.loads((latest/'result.json').read_text())['status']
    elif (latest/'stream.jsonl').exists():phase='request';e=last_json(latest/'stream.jsonl');detail['last_event_elapsed_seconds']=e.get('elapsed_seconds') if e else None;detail['reported_output_tokens_so_far']=e.get('event',{}).get('tokens_predicted') if e else 0
    elif (latest/'auxiliary-warmup.json').exists():phase='cooldown_after_warmup'
    elif (latest/'auxiliary-warmup-stream.jsonl').exists():phase='warmup';e=last_json(latest/'auxiliary-warmup-stream.jsonl');detail['last_event_elapsed_seconds']=e.get('elapsed_seconds') if e else None;detail['reported_output_tokens_so_far']=e.get('event',{}).get('tokens_predicted') if e else 0
    elif (latest/'server.txt').exists():phase='model_startup_or_prompt_preparation'
sample=last_json(s/'sensors.jsonl') or {}
print(json.dumps({'session':args.session,'phase':phase,'completed_main':sum(r.get('status')=='ok' and r['task']['phase']=='main' for r in records),'completed_pilot':sum(r.get('status')=='ok' and r['task']['phase']=='pilot' for r in records),'failed_or_interrupted':sum(r.get('status')!='ok' for r in records),'latest_sample_at':sample.get('captured_at'),'soc_c':sample.get('soc_temperature_celsius'),'thermal_status':sample.get('thermal_status'),'battery':sample.get('battery'),'rss_mib':sample.get('process_memory_kib',{}).get('VmRSS',0)/1024,**detail},indent=2))
