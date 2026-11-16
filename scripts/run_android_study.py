#!/usr/bin/env python3
"""ADB-controlled CPU experiment, preserving Android evidence and strict gates.

No root, battery simulation, cache dropping, CPU locking, or thermal overrides.
Network first/inter-token latencies are host arrival proxies. Energy unavailable.
"""
import argparse
import collections
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import signal
import statistics
import subprocess
import threading
import time
import urllib.request
import run_study as core

ROOT = core.ROOT
ADB = str(Path.home()/'Library/Android/sdk/platform-tools/adb')
REMOTE = '/data/local/tmp/effai'
BINARY = 'llama-server-cpu-3759169a'
HOST_PORT = 8091
STOP = threading.Event()


def log(s):
    print(core.utc(), s, flush=True)


class Device:
    def __init__(self, target):
        self.target = target
        self.selector=['-d'] if target=='USB' else ['-s',target]
        self.transport='USB ADB forward' if target=='USB' else 'wireless ADB forward'
    def adb(self, *args, timeout=20, check=True):
        p = subprocess.run([ADB, *self.selector, *args], capture_output=True, text=True, timeout=timeout)
        if check and p.returncode:
            raise RuntimeError(f'ADB {args[0]} failed: {p.stderr.strip()} {p.stdout[:300]}')
        return p
    def shell(self, s, timeout=20, check=True):
        return self.adb('shell', s, timeout=timeout, check=check).stdout


# Selected metrics only: no app inventory, account information, serials, or network identifiers.
PROBE = r'''echo __THERMAL__
dumpsys thermalservice
echo __BATTERY__
dumpsys battery
echo __MEMORY__
cat /proc/meminfo
echo __CPU__
head -n 1 /proc/stat
echo __FREQUENCY__
for p in /sys/devices/system/cpu/cpufreq/policy*; do echo "$p"; cat "$p/scaling_cur_freq" "$p/scaling_max_freq" "$p/cpuinfo_max_freq"; done
echo __PROCESS__
if test -r /data/local/tmp/effai/effai-study.pid; then
p=$(cat /data/local/tmp/effai/effai-study.pid)
if test -r /proc/$p/status; then cat /proc/$p/status; cat /proc/$p/stat; fi
fi'''


def parse_sample(raw):
    sections = re.split(r'^__(\w+)__\s*$', raw, flags=re.M)
    parts = dict(zip(sections[1::2], sections[2::2]))
    thermal = parts.get('THERMAL', '')
    current = thermal.split('Current temperatures from HAL:', 1)[-1].split('Current cooling devices', 1)[0] if 'Current temperatures from HAL:' in thermal else ''
    temps = {}
    for value, kind, name, status in re.findall(r'Temperature\{mValue=([\d.+-]+), mType=(-?\d+), mName=([^,]+), mStatus=(\d+)\}', current):
        temps[name.strip()] = {'celsius':float(value), 'type':int(kind), 'status':int(status)}
    status = re.search(r'^Thermal Status:\s*(\d+)', thermal, re.M)
    bat = parts.get('BATTERY', '')
    def number(label):
        m=re.search(r'^\s*'+re.escape(label)+r':\s*(-?\d+)', bat, re.M)
        return int(m[1]) if m else None
    memory = {k:int(v) for k,v in re.findall(r'^(\w+):\s*(\d+) kB', parts.get('MEMORY',''), re.M)}
    process = parts.get('PROCESS','')
    pmem = {k:int(v) for k,v in re.findall(r'^(VmRSS|VmHWM|VmSize|VmSwap):\s*(\d+) kB', process, re.M)}
    th = re.search(r'^Threads:\s*(\d+)',process,re.M)
    # /proc/PID/stat comm can include spaces, so split after its final close parenthesis.
    statline=next((x for x in process.splitlines() if re.match(r'^\d+ \(',x)),None)
    ticks=None
    if statline:
        fields=statline.rsplit(')',1)[1].split()
        ticks=int(fields[11])+int(fields[12]) # fields 14/15, relative to state (field 3).
    cpu=parts.get('CPU','').strip().split()
    freq=[]
    for policy,cur,maximum,hardware in re.findall(r'/sys/devices/system/cpu/cpufreq/(policy\d+)\s+(\d+)\s+(\d+)\s+(\d+)',parts.get('FREQUENCY','')):
        freq.append({'policy':policy,'current_khz':int(cur),'scaling_max_khz':int(maximum),'hardware_max_khz':int(hardware)})
    return {'temperatures':temps,'thermal_status':int(status[1]) if status else None,
            'soc_temperature_celsius':temps.get('soc-thmzone',{}).get('celsius'),
            'battery':{'level_percent':number('level'),'status':number('status'),'voltage_reported_unvalidated':number('voltage'),
                       'charge_counter_reported':number('Charge counter'),'temperature_celsius':number('temperature')/10 if number('temperature') is not None else None,
                       'usb_powered':'USB powered: true' in bat,'ac_powered':'AC powered: true' in bat},
            'memory_kib':memory,'process_memory_kib':pmem,'process_threads':int(th[1]) if th else None,
            'process_cpu_ticks':ticks,'cpu_ticks':[int(x) for x in cpu[1:]] if cpu and cpu[0]=='cpu' else None,
            'cpu_frequency':freq}


class Monitor:
    def __init__(self, device, path, interval=2):
        self.device=device; self.path=path; self.interval=interval
        self.samples=collections.deque(maxlen=5000); self.lock=threading.Lock();self.stop_event=threading.Event()
        self.thread=threading.Thread(target=self.collect,daemon=True)
        self.hz=int(device.shell('getconf CLK_TCK').strip());self.abort_non_nominal=False
    def start(self): self.thread.start()
    def collect(self):
        previous=None
        with self.path.open('a',buffering=1) as f:
            while not self.stop_event.is_set():
                before=time.monotonic()
                try:
                    raw=self.device.shell(PROBE,timeout=15)
                    sample=parse_sample(raw)
                    sample.update(unix=time.time(),monotonic=time.monotonic(),captured_at=core.utc(),probe_wall_seconds=time.monotonic()-before)
                    sample['raw_thermal_current_section']=raw.split('__THERMAL__',1)[-1].split('__BATTERY__',1)[0]
                    if self.abort_non_nominal and sample.get('thermal_status') not in (None,0):
                        sample['safety_stop']='exploratory scope requires nominal system thermal status'
                        STOP.set();core.STOP.set()
                    if (sample.get('thermal_status') is not None and sample['thermal_status'] >= 3) or (sample.get('soc_temperature_celsius') or 0) >= 90 or (sample.get('battery',{}).get('temperature_celsius') or 0) >= 45 or (sample.get('battery',{}).get('level_percent') is not None and sample['battery']['level_percent'] <= 3):
                        sample['safety_stop']='operator stop: thermal status >=3, SoC >=90C, battery >=45C, or charge <=3%'
                        STOP.set();core.STOP.set()
                    if previous:
                        elapsed=sample['monotonic']-previous['monotonic']
                        a=sample['cpu_ticks'];b=previous.get('cpu_ticks')
                        if a and b:
                            delta=[x-y for x,y in zip(a,b)];total=sum(delta[:8]);idle=delta[3]+delta[4]
                            sample['system_cpu_active_ratio']=(total-idle)/total if total>0 else None
                        a=sample.get('process_cpu_ticks');b=previous.get('process_cpu_ticks')
                        if a is not None and b is not None and a>=b:
                            sample['process_cpu_percent_one_core_100']=(a-b)/self.hz/elapsed*100
                    previous=sample
                except Exception as e:
                    sample={'unix':time.time(),'monotonic':time.monotonic(),'captured_at':core.utc(),'error':str(e)}
                f.write(json.dumps(sample,allow_nan=False)+'\n')
                with self.lock:self.samples.append(sample)
                self.stop_event.wait(max(.05,self.interval-(time.monotonic()-before)))
    def window(self, seconds):
        with self.lock:return [s for s in self.samples if time.monotonic()-s['monotonic']<=seconds]
    def latest(self):
        with self.lock:return self.samples[-1] if self.samples else None
    def stop(self):
        self.stop_event.set();self.thread.join(timeout=20)


def gate(monitor, baseline, evidence, earliest=0, timeout=1800, minimum_battery=15, require_stable=True):
    began=time.monotonic();records=[]
    while not STOP.is_set():
        w=monitor.window(62)
        good=[x for x in w if x.get('soc_temperature_celsius') is not None and 'error' not in x]
        vals=[x['soc_temperature_celsius'] for x in good]
        coverage=good[-1]['monotonic']-good[0]['monotonic'] if len(good)>1 else 0
        latest=w[-1] if w else {}
        fresh=bool(w and time.monotonic()-latest['monotonic']<8 and 'error' not in latest)
        nominal=bool(good and all(x['thermal_status']==0 for x in good))
        active=[x['system_cpu_active_ratio'] for x in good if x.get('system_cpu_active_ratio') is not None]
        quiet=bool(active and statistics.mean(active)<=.35)
        stable=coverage>=58 and len(vals)>=25 and max(vals)-min(vals)<=1
        cool=bool(vals and (baseline is None or statistics.mean(vals)<=baseline+2))
        battery=latest.get('battery',{}).get('level_percent',0) or 0
        gap=time.time()>=earliest
        r={'at':core.utc(),'wait_seconds':time.monotonic()-began,'coverage_seconds':coverage,'samples':len(vals),
           'mean_celsius':statistics.mean(vals) if vals else None,'min_celsius':min(vals) if vals else None,'max_celsius':max(vals) if vals else None,
           'idle_baseline_celsius':baseline,'system_cpu_active_ratio_mean':statistics.mean(active) if active else None,
           'fresh':fresh,'thermal_nominal':nominal,'stable':stable,'cool':cool,'quiet':quiet,'repeat_gap_satisfied':gap,
           'battery_percent':battery,'minimum_battery_percent':minimum_battery,
           'strict_stabilization_required':require_stable,
           'accepted':bool(fresh and nominal and (stable if require_stable else coverage>=10) and cool and quiet and gap and battery>=minimum_battery)}
        records.append(r);core.save(evidence,records)
        if r['accepted']:return r
        if r['wait_seconds']>timeout:raise RuntimeError('strict thermal/idle/battery gate timeout; see '+str(evidence))
        if len(records)%6==1:log('Gate: '+json.dumps(r))
        STOP.wait(5)
    raise InterruptedError('stop during gate')


def validate(measured,task):
    final=measured['final'];timing=final['timings']
    checks={'input_exact':final.get('tokens_evaluated')==task['input_tokens'],
            'output_exact':final.get('tokens_predicted')==task['output_tokens'],
            'stream_exact':measured['stream_token_count']==task['output_tokens'],
            'no_truncation':final.get('truncated') is False,
            'no_prompt_cache':timing.get('cache_n',0)==0,
            'limit_stop':final.get('stop_type')=='limit',
            'prefill_denominator':timing.get('prompt_n')==task['input_tokens'],
            'decode_denominator':timing.get('predicted_n')==task['output_tokens']}
    # This pinned server reports predicted_n equal to returned output count.
    # Validate the recorded denominator rather than substituting an assumed n-1.
    return checks


def exploratory_gate(monitor, baseline, evidence, minimum_battery):
    began=time.monotonic();records=[]
    while not STOP.is_set():
        w=monitor.window(32);good=[s for s in w if s.get('soc_temperature_celsius') is not None and 'error' not in s]
        vals=[s['soc_temperature_celsius'] for s in good];latest=monitor.latest() or {}
        coverage=good[-1]['monotonic']-good[0]['monotonic'] if len(good)>1 else 0
        fresh=bool(latest and time.monotonic()-latest['monotonic']<8 and 'error' not in latest)
        nominal=bool(good and all(s.get('thermal_status')==0 for s in good))
        battery=latest.get('battery',{}).get('level_percent',0) or 0
        stable=bool(coverage>=28 and len(vals)>=13 and max(vals)-min(vals)<=10 and statistics.mean(vals)<=baseline+8)
        expired=time.monotonic()-began>=120
        r={'at':core.utc(),'wait_seconds':time.monotonic()-began,'coverage_seconds':coverage,'samples':len(vals),
           'mean_celsius':statistics.mean(vals) if vals else None,'min_celsius':min(vals) if vals else None,'max_celsius':max(vals) if vals else None,
           'idle_baseline_celsius':baseline,'fresh':fresh,'thermal_nominal':nominal,'battery_percent':battery,
           'strict_stabilization_required':False,'accepted':bool(stable and fresh and nominal and battery>=minimum_battery),
           'timeout_expired':expired,'proceeding_under_exploratory_scope':bool(expired and fresh and nominal and battery>=minimum_battery),
           'interpretation':'bounded exploratory thermal observation; never strict stabilization evidence'}
        records.append(r);core.save(evidence,records)
        if r['accepted'] or r['proceeding_under_exploratory_scope']:return r
        if expired and (not fresh or not nominal or battery<minimum_battery):raise RuntimeError('exploratory gate cannot proceed: missing sensors, nonnominal thermal status, or battery below guard')
        STOP.wait(5)
    raise InterruptedError('stop during exploratory observation')


class Runner:
    def __init__(self,device,session,study,models,monitor,baseline):
        self.device=device;self.session=session;self.study=study;self.models=models;self.monitor=monitor;self.baseline=baseline
        self.server=None;self.server_key=None;self.logfile=None;self.server_folder=None;self.pid=None
    def close(self):
        if self.pid:
            self.device.shell(f'kill {self.pid}',check=False)
        if self.server:
            try:self.server.wait(timeout=10)
            except subprocess.TimeoutExpired:self.server.terminate();self.server.wait(timeout=10)
        if self.logfile:self.logfile.close()
        self.server=None;self.server_key=None;self.pid=None
    def launch(self,task,folder):
        key=(task['model_id'],task['cache_type'])
        if self.server_key==key and self.server and self.server.poll() is None:
            return {'same_process_reused':True,'startup_ready_seconds':None,'server_log':str(self.server_folder.relative_to(self.session)/'server.txt'),'server_pid':self.pid}
        self.close()
        model=self.models[task['model_id']]
        args=['./'+self.device.binary,'-m',model['filename'],'-c','3072','-t','4','-tb','4','-b','512','-ub','128','-ngl','0','-np','1','-fa','on',
              '-ctk',task['cache_type'],'-ctv',task['cache_type'],'--host','127.0.0.1','--port','8088','--no-webui']
        shell=f'cd {REMOTE} && echo $$ > effai-study.pid && exec '+shlex.join(args)
        self.logfile=(folder/'server.txt').open('w')
        began=time.monotonic()
        self.server=subprocess.Popen([ADB,*self.device.selector,'shell',shell],stdout=self.logfile,stderr=subprocess.STDOUT)
        self.server_folder=folder
        for _ in range(1800):
            if STOP.is_set():raise InterruptedError('stop during startup')
            if self.server.poll() is not None:raise RuntimeError('server exited while loading; see server.txt')
            try:
                with urllib.request.urlopen(core.BASE+'/health',timeout=1) as r:
                    if r.status==200:break
            except Exception:time.sleep(.2)
        else:raise RuntimeError('server startup timeout')
        self.pid=int(self.device.shell(f'cat {REMOTE}/effai-study.pid').strip())
        self.server_key=key
        startup=time.monotonic()-began
        raw=(folder/'server.txt').read_text()
        core.save(folder/'server-props.json',json.load(urllib.request.urlopen(core.BASE+'/props')))
        if 'CPU' not in raw:raise RuntimeError('CPU backend not confirmed in startup log')
        if not re.search(r'n_ctx\s*=\s*3072',raw):raise RuntimeError('3072 context not confirmed in startup log')
        return {'same_process_reused':False,'startup_ready_seconds':startup,'server_command':args,
                'server_log':str(folder.relative_to(self.session)/'server.txt'),'server_pid':self.pid}
    def run(self,task,minimum_battery=15):
        prior=[json.loads(p.read_text()) for p in (self.session/'runs').glob('*/result.json')]
        ok=next((r for r in prior if r.get('task',{}).get('id')==task['id'] and r.get('status')=='ok'),None)
        if ok:return ok
        attempt=len(list((self.session/'runs').glob(task['id']+'-attempt*')))+1
        folder=self.session/'runs'/(task['id']+f'-attempt{attempt}');folder.mkdir(parents=True)
        r={'schema_version':1,'run_id':folder.name,'task':task,'status':'starting','created_at':core.utc(),
           'device':'realme-RMX3930','transport':self.device.transport+'; host SSE arrival proxies',
           'sensor_log':'sensors.jsonl','energy_joules':None,'energy_reason':'No validated device-energy counter; charging; sysfs permission denied',
           'model':self.models[task['model_id']]}
        try:
            exploratory=self.study.get('scope')=='exploratory-presentation'
            matching=[p.get('request_end_unix',0) for p in prior if p.get('task',{}).get('model_id')==task['model_id'] and p['task'].get('input_tokens')==task['input_tokens'] and p['task'].get('output_tokens')==task['output_tokens'] and p['task'].get('cache_type')==task['cache_type']]
            earliest=max(matching,default=0)+self.study['minimum_repeat_gap_seconds']
            same_model=self.server_key==(task['model_id'],task['cache_type']) and self.server and self.server.poll() is None
            if exploratory:
                r['preload_gate']={'skipped':True,'reason':'one bounded thermal observation per loaded model block','exploratory':True} if same_model else exploratory_gate(self.monitor,self.baseline,folder/'preload-gate.json',minimum_battery)
            else:
                r['preload_gate']=gate(self.monitor,self.baseline,folder/'preload-gate.json',earliest,minimum_battery=minimum_battery,require_stable=task['phase']!='smoke')
            r.update(self.launch(task,folder))
            p=core.prompt(task['input_tokens'],folder/'prompt.json',self.session/'corpus-v1.txt')
            req={'prompt':p['tokens'],'n_predict':task['output_tokens'],'temperature':0,'seed':113,'ignore_eos':True,'cache_prompt':False,'stream':True,'return_tokens':True,'timings_per_token':False}
            core.save(folder/'request.json',req)
            # Explicit warmup phases are unmeasured observations retained as evidence.
            # A resumed/new server for a measured case receives a same-case warmup.
            if not r['same_process_reused'] and task['phase'] not in ('warmup','kv_warmup','smoke'):
                warm=core.stream(req,folder/'auxiliary-warmup-stream.jsonl')
                checks=validate(warm,task);core.save(folder/'auxiliary-warmup.json',dict(warm,validation=checks))
                if not all(checks.values()):raise RuntimeError('warmup validation failed: '+str(checks))
                earliest=max(earliest,warm['request_end_unix']+self.study['minimum_repeat_gap_seconds'])
            if exploratory:
                latest=self.monitor.latest() or {}
                if time.monotonic()-latest.get('monotonic',0)>8 or latest.get('thermal_status')!=0 or (latest.get('battery',{}).get('level_percent') or 0)<minimum_battery:raise RuntimeError('fresh nominal thermal and adequate battery evidence required before exploratory request')
                r['request_gate']={'skipped':True,'reason':'user-approved exploratory single pass; continuous monitoring and per-block bounded observation, no strict stabilization claim','exploratory':True,'at':core.utc(),'thermal_status_before':latest['thermal_status'],'soc_temperature_before_celsius':latest.get('soc_temperature_celsius')}
            else:
                r['request_gate']=gate(self.monitor,self.baseline,folder/'request-gate.json',earliest,minimum_battery=minimum_battery,require_stable=task['phase']!='smoke')
            r['process_memory_before']=self.device.shell(f'dumpsys meminfo {self.pid}',check=False)
            core.save(folder/'state.json',r)
            if task.get('instrumentation',True):
                measured=core.stream(req,folder/'stream.jsonl')
            else:
                # Stop only the common sampler for this paired arm and resume after.
                # This measures aggregate ADB monitor cost, not just the RSS field.
                self.monitor.stop()
                try:measured=core.stream(req,folder/'stream.jsonl')
                finally:
                    old=self.monitor
                    self.monitor=Monitor(self.device,old.path,old.interval);self.monitor.start()
            r.update(measured);r['runtime_timings']=measured['final']['timings'];r['validation']=validate(measured,task)
            if not all(r['validation'].values()):raise RuntimeError('request validation failed: '+str(r['validation']))
            r['input_tokens_actual']=measured['final']['tokens_evaluated'];r['output_tokens_actual']=measured['final']['tokens_predicted']
            r['status']='ok'
        except BaseException as e:
            r['status']='interrupted' if isinstance(e,(KeyboardInterrupt,InterruptedError)) else 'failed'
            r['error']={'type':type(e).__name__,'message':str(e)}
            log(task['id']+' FAILED '+str(e))
        finally:
            r['finished_at']=core.utc()
            if self.pid:r['process_memory_after']=self.device.shell(f'dumpsys meminfo {self.pid}',check=False)
            window=[x for x in self.monitor.window(1800) if r.get('request_start_unix',1e20)<=x.get('unix',0)<=r.get('request_end_unix',0)]
            rss=[x.get('process_memory_kib',{}).get('VmRSS') for x in window];rss=[x for x in rss if x is not None]
            temp=[x['soc_temperature_celsius'] for x in window if x.get('soc_temperature_celsius') is not None]
            cpu=[x['process_cpu_percent_one_core_100'] for x in window if x.get('process_cpu_percent_one_core_100') is not None]
            r['request_sensor_sample_count']=len(window);r['sampled_peak_rss_kib']=max(rss) if rss else None
            r['peak_soc_temperature_celsius']=max(temp) if temp else None;r['mean_process_cpu_percent_one_core_100']=statistics.mean(cpu) if cpu else None
            r['thermal_statuses']=sorted({x['thermal_status'] for x in window if x.get('thermal_status') is not None})
            r['minimum_mem_available_kib']=min((x['memory_kib']['MemAvailable'] for x in window if 'MemAvailable' in x.get('memory_kib',{})),default=None)
            core.save(folder/'result.json',r)
            with (self.session/'summary.jsonl').open('a') as f:f.write(json.dumps(r,allow_nan=False)+'\n')
            if r['status']!='ok':self.close()
        return r


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--target',required=True);ap.add_argument('--session',required=True)
    ap.add_argument('--stage',choices=['smoke','pilot','full','presentation'],default='pilot');ap.add_argument('--limit',type=int)
    ap.add_argument('--minimum-battery',type=int,default=15,choices=range(5,101))
    ap.add_argument('--pilot-session',default='android-20261115-pilot')
    ap.add_argument('--binary',default=BINARY,help='Previously verified binary basename inside the benchmark directory')
    ap.add_argument('--idle-reference-session',help='Retain an earlier true-idle baseline rather than resetting it after load')
    args=ap.parse_args();device=Device(args.target);core.BASE=f'http://127.0.0.1:{HOST_PORT}'
    if not re.fullmatch(r'llama-server-cpu-[0-9a-f]{8}',args.binary):raise RuntimeError('expected content-addressed benchmark binary basename')
    device.binary=args.binary
    session=ROOT/'results'/args.session;session.mkdir(parents=True,exist_ok=True);(session/'runs').mkdir(exist_ok=True)
    lock=(ROOT/'results/android-study.lock').open('w');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    study_path=ROOT/('configs/android-presentation-pilot.json' if args.stage=='presentation' else 'configs/study.json')
    study=json.loads(study_path.read_text());models={m['id']:m for m in json.loads((ROOT/'configs/models.json').read_text())}
    adaptation={'platform':'Android','stage':args.stage,'temperature_sensor':'current HAL soc-thmzone type0; SoC proxy, not core junction guarantee',
                'transport':device.transport,
                'monitor_interval_seconds':2,'thermal_window_seconds':study['thermal_rule']['window_seconds'] if args.stage=='presentation' else 60,
                'thermal_range_max_celsius':study['thermal_rule']['maximum_range_celsius'] if args.stage=='presentation' else 1,
                'above_idle_max_celsius':study['thermal_rule']['maximum_above_idle_celsius'] if args.stage=='presentation' else 2,
                'thermal_gate_policy':'one bounded observation per loaded model block; no post-warmup strict gate' if args.stage=='presentation' else 'strict gates before requests (except instrumentation smoke)',
                'idle_mean_system_cpu_active_ratio_max':None if args.stage=='presentation' else .35,'idle_power_rule':'unavailable on Android; not asserted',
                'minimum_repeat_gap_seconds':study['minimum_repeat_gap_seconds'],'minimum_battery_percent':5 if args.stage=='smoke' else args.minimum_battery,
                'energy':'unavailable; charging; no trustworthy counters or external meter',
                'screen':'off during experiment; USB charging; ADB transport recorded; ambient unknown',
                'cpu_policy':'stock DVFS governor, no affinity or frequency locks, 4 runtime threads, CPU only',
                'strict_stabilization_required':args.stage in ('pilot','full'),
                'scope':'exploratory-presentation' if args.stage=='presentation' else ('instrumentation smoke only, no thermal-control claim' if args.stage=='smoke' else 'strict repeated Android experiment')}
    adaptation['operator_stop_policy']={'thermal_status_min':3,'soc_temperature_celsius_min':90,'battery_temperature_celsius_min':45,'battery_percent_max_for_stop':3,'meaning':'conservative operator abort thresholds; not manufacturer-rated limits; stock thermal management remains enabled'}
    reference_session=args.idle_reference_session or (args.pilot_session if args.stage in ('full','presentation') else None)
    reference=None
    if reference_session:
        reference_path=ROOT/'results'/reference_session/'idle-baseline.json'
        original=json.loads(reference_path.read_text())
        reference=original.get('reference_used_celsius',original['mean_celsius'])
        adaptation['idle_reference']={'session':reference_session,'source_baseline_sha256':core.sha(reference_path),'celsius':reference,'reason':'fixed previously validated idle reference; no warmer baseline reset after inference'}
    model_hash_output=device.shell('cd '+REMOTE+' && sha256sum '+shlex.join([m['filename'] for m in models.values()]),timeout=120)
    actual_models={line.split()[1]:line.split()[0] for line in model_hash_output.splitlines() if len(line.split())==2}
    for model in models.values():
        if actual_models.get(model['filename'])!=model['sha256']:raise RuntimeError('device model checksum mismatch: '+model['id'])
    frozen={'harness_sha256':core.sha(Path(__file__)),'core_harness_sha256':core.sha(ROOT/'scripts/run_study.py'),
            'study_sha256':core.sha(study_path),'models_sha256':core.sha(ROOT/'configs/models.json'),
            'corpus_sha256':core.sha(ROOT/'prompts/corpus-v1.txt'),'binary_sha256':device.shell(f'cd {REMOTE} && sha256sum {device.binary}').split()[0],
            'runtime_commit':core.COMMIT,'device_model_checksums':actual_models,'adaptation':adaptation}
    fp=session/'provenance.json'
    if fp.exists() and json.loads(fp.read_text())!=frozen:raise RuntimeError('Frozen provenance changed; use new session ID')
    core.save(fp,frozen);core.save(session/'study.json',study);core.save(session/'models.json',list(models.values()));core.save(session/'platform-adaptation.json',adaptation)
    (session/'harness.py').write_bytes(Path(__file__).read_bytes());(session/'core-harness.py').write_bytes((ROOT/'scripts/run_study.py').read_bytes())
    (session/'corpus-v1.txt').write_bytes((ROOT/'prompts/corpus-v1.txt').read_bytes())
    device.adb('forward',f'tcp:{HOST_PORT}','tcp:8088')
    device.shell('input keyevent 223') # screen off; never unlock or inspect personal UI.
    monitor=Monitor(device,session/'sensors.jsonl');monitor.abort_non_nominal=args.stage=='presentation';monitor.start();runner=None
    try:
        path=session/'idle-baseline.json'
        if path.exists():
            prior=json.loads(path.read_text());baseline=prior.get('reference_used_celsius',prior['mean_celsius'])
        elif args.stage=='presentation':
            if reference is None:raise RuntimeError('presentation requires a previously measured idle reference')
            baseline=reference;core.save(path,{'mean_celsius':reference,'reference_used_celsius':reference,'source_session':reference_session,'new_idle_measurement':False,'scope':'exploratory-presentation'})
        else:
            log('Collecting strict Android idle baseline and charging to minimum battery')
            observed=gate(monitor,reference,session/'idle-stabilization.json',timeout=7200,minimum_battery=adaptation['minimum_battery_percent'],require_stable=args.stage!='smoke')
            baseline=reference if reference is not None else observed['mean_celsius'];observed['reference_used_celsius']=baseline;core.save(path,observed)
        runner=Runner(device,session,study,models,monitor,baseline)
        if args.stage=='smoke':
            tasks=[{'id':'smoke-qwen05_q4-i256-o128','model_id':'qwen05_q4','input_tokens':256,'output_tokens':128,'cache_type':'f16','phase':'smoke','repetition':0}]
        elif args.stage=='pilot':tasks=[x for x in core.plan(study) if x['phase']=='pilot']
        elif args.stage=='presentation':
            pilot_root=ROOT/'results'/args.pilot_session
            pilot_provenance=json.loads((pilot_root/'provenance.json').read_text())
            for key in ['runtime_commit','binary_sha256','corpus_sha256','models_sha256','device_model_checksums']:
                if pilot_provenance.get(key)!=frozen.get(key):raise RuntimeError('largest warmup/presentation provenance mismatch: '+key)
            warmups=[json.loads(p.read_text()) for p in (pilot_root/'runs').glob('pilot-largest-*/auxiliary-warmup.json')]
            if not any(w.get('stream_token_count')==512 and w.get('final',{}).get('tokens_evaluated')==2048 and w.get('validation') and all(w['validation'].values()) for w in warmups):raise RuntimeError('successful exact largest-condition warmup required before exploratory matrix')
            tasks=core.plan(study)
        else:
            pilots=list((ROOT/'results'/args.pilot_session/'runs').glob('pilot-largest-*-attempt*/result.json'))
            pilot_provenance=json.loads((ROOT/'results'/args.pilot_session/'provenance.json').read_text())
            for key in ['runtime_commit','binary_sha256','corpus_sha256','models_sha256','study_sha256','device_model_checksums']:
                if pilot_provenance.get(key)!=frozen.get(key):raise RuntimeError('pilot/main provenance mismatch: '+key)
            passed={json.loads(p.read_text())['task']['id'] for p in pilots if json.loads(p.read_text()).get('status')=='ok'}
            if not {'pilot-largest-0','pilot-largest-1'}<=passed:raise RuntimeError('two largest-condition pilot successes required before full matrix')
            tasks=[x for x in core.plan(study) if x['phase']!='pilot']
        core.save(session/'plan.json',tasks)
        for index,task in enumerate(tasks):
            if STOP.is_set():raise InterruptedError('stop requested')
            log('Starting '+task['id']);r=runner.run(task,minimum_battery=adaptation['minimum_battery_percent']);monitor=runner.monitor
            core.save(session/'progress.json',{'at':core.utc(),'planned':len(tasks),'last_index':index,'last_id':task['id'],'last_status':r['status'],'pid':os.getpid()})
            if r['status']!='ok':raise RuntimeError('Run failed; inspect evidence before resuming')
            log(f"OK {task['id']} wall={r['request_wall_seconds']:.2f}s decode={r['runtime_timings']['predicted_per_second']:.3f} tok/s RSS={r['sampled_peak_rss_kib']} KiB peakSoC={r['peak_soc_temperature_celsius']}")
            if args.stage=='presentation' and index==0:
                marker=session/'first-run-audit-approved.json'
                if not marker.exists():log('First presentation observation complete; retaining server while independent audit validates logs/schema')
                while not marker.exists() and not STOP.is_set():STOP.wait(1)
                if STOP.is_set():raise InterruptedError('stopped while waiting for first-run audit')
                approval=json.loads(marker.read_text())
                if approval.get('approved_run_id')!=r['run_id']:raise RuntimeError('first-run audit marker does not match validated run')
            if args.limit and index+1>=args.limit:break
    finally:
        if runner:runner.close();monitor=runner.monitor
        monitor.stop()
        device.adb('forward','--remove',f'tcp:{HOST_PORT}',check=False)


if __name__=='__main__':
    def stop(sig,frame):STOP.set();core.STOP.set()
    signal.signal(signal.SIGINT,stop);signal.signal(signal.SIGTERM,stop)
    main()
