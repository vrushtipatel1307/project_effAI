# Android device and measurement readiness

Inspection date: 2026-11-15. User identifies the phone as a **realme C61**. Wireless ADB confirms the following selected properties; identifiers and personal app inventories are excluded from project evidence.

| Field | Observed value / boundary |
| --- | --- |
| Manufacturer/model | realme / RMX3930; device code RE6054 |
| SoC | T612 |
| OS / ABI | Android 14, API 34, arm64-v8a |
| CPU | 8 online CPUs; stock `uscfreq` governor; no frequency/affinity locks |
| OS-visible RAM | 5,905,952 KiB = 5.63 GiB; consistent with a marketed 6 GB SKU, not a chip-level physical-RAM measurement |
| Initially available RAM | 3,629,236 KiB = 3.46 GiB; a changing snapshot |
| Swap | 3,661,820 KiB total reported; `/proc/swaps` denied, backing unverified; do not count virtual RAM as physical RAM |
| Power | USB charging; initially 4–5%, later increasing; per-run battery/charge state retained |
| Runtime | Pinned llama.cpp `79967ec596c0dacfd2251b085a57e79df292b1cc`, ARM64 CPU build, 4 threads, static project/C++ libraries |
| Thermal source | Current HAL `soc-thmzone` type 0; SoC proxy, not independently calibrated core temperature |
| Raw sysfs thermal/battery | Permission denied; no root/security override attempted |
| Timing boundary | Main presentation session uses runtime prefill/decode plus host SSE first/inter-token arrival proxies over USB ADB; earlier smoke and setup sessions used wireless ADB |
| Memory/utilization | Sampled process RSS in KiB, process CPU with one core = 100%, aggregate CPU activity, CPU policy frequencies; PSS snapshots before/after |
| Energy | Unavailable for inference: charging, no external meter, unvalidated generic Perfetto power rails and battery counters |

Read-only inventory: [device-inspection.txt](../results/android-readiness-20261115/device-inspection.txt). Runtime build/checksum evidence: [setup](../results/android-20261115-setup/). A successful build or device inventory does not establish the full matrix's fit.

## First validated real workload

`android-20261115-smoke-v3` completed Qwen2.5-0.5B Q4_K_M with 256 formatted input tokens and 128 forced output tokens. Independent audit confirms exact prompt/request/output counts, limit stop, no truncation, no cache reuse, runtime rate denominators, and CPU/F16/context startup logs. It is **instrumentation smoke only**, with no strict stabilization claim and no main-matrix observation.

Measured runtime prefill: 11.99913 s / 21.33488 tokens/s; decode: 16.584655 s / 7.71798 tokens/s. Request sample peak RSS: 573,648 KiB (560.2 MiB); peak HAL SoC temperature: 70.414°C. Do not generalize this single small case to the largest condition.

## Selected CPU build and largest-case status

The generic ARMv8-a largest-case warm-up completed 2,048 input / 512 output tokens with all exact-count/cache/context/stop checks passing (543.08 s, decode 2.7985 tokens/s). It is not a measured main observation. The phone reports `asimddp`, `fphp`, and `asimdhp`; a separate `armv8.2-a+dotprod+fp16` build has passed a small real-prompt smoke and startup logs confirm `DOTPROD=1` and `FP16_VA=1`. Main results must use one consistent validated build; do not pool generic and optimized observations.

The optimized binary is `llama-server-cpu-c80a55ba`, SHA-256 `c80a55ba73c0ef7154e7a53af3979052b144d7c2295ab4ca3884a678b66d4efa`. A largest-condition selected-build warm-up completed before the presentation matrix. The full controlled pilot remains a future requirement; the presentation matrix did not claim strict stabilization.

## Autonomous experiment commands

The current operator is authorized to control the phone and execute tests. Keep the phone powered and wireless debugging connected. The runner turns the screen off, retains stock CPU/thermal policies, records the charging boundary, and serializes experiments with a lock.

```sh
# Resolve the connected authorized target first; do not publish its identifier.
python3 scripts/run_android_study.py --target '<ADB target>' \
  --session android-YYYYMMDD-smoke --stage smoke

# Current user-approved starting guard is 14% while charging.
python3 scripts/run_android_study.py --target '<ADB target>' \
  --session android-20261115-pilot-dotprod --stage pilot --minimum-battery 14 \
  --binary llama-server-cpu-c80a55ba \
  --idle-reference-session android-20261115-pilot-v2

python3 scripts/run_android_study.py --target '<ADB target>' \
  --session android-20261115-controlled --stage full --minimum-battery 14 \
  --pilot-session android-20261115-pilot-dotprod \
  --binary llama-server-cpu-c80a55ba

python3 analysis/analyze_android.py --session android-20261115-controlled
```

Pilot and full stages require a 60-second current-HAL window with range at most 1°C, mean at most idle+2°C, nominal thermal status, low mean aggregate CPU activity, fresh samples, battery at least the frozen starting threshold (user-approved 14% for the current session), and at least 120 seconds between repeated configurations. No platform CPU-power idle threshold can be asserted because a trustworthy Android power source is unavailable; this adaptation is frozen explicitly. Operator abort thresholds are recorded as operator policy, not manufacturer thermal ratings. Missing sensors or gate failures remain evidence and do not silently become controlled results.

The full controlled pilot is the largest case twice: Qwen2.5-1.5B Q8_0, 2,048 input and 512 output tokens, F16 KV, 3,072 context capacity. The full main study requires 72 measured requests across 24 configurations, with warm-ups. Paired monitoring-overhead and focused KV-cache runs remain separately labeled. Perplexity and native-function/operator profiling are separate diagnostic/quality work.

## Presentation matrix results — 2026-11-16

The user-approved Android presentation session `android-20261115-presentation-usb` completed **24/24 unique main configurations once each** on the selected CPU/DOTPROD/FP16 build. Independent analysis validated all 24 observations with exact input/output counts, stop-limit, no truncation, no prompt-cache reuse, and runtime-rate denominators; no main record failed. The cross-device audit matched all 24 Mac configurations with identical prompt text, token IDs, and full request JSON. These are exploratory n=1 points: no standard deviations, repeatability, significance, or strict thermal-stabilization claim.

The largest condition completed for both 1.5B quantizations. Qwen2.5-1.5B Q8_0 at 2,048 input / 512 output took 463.64 s request wall, with runtime decode 2.993 tokens/s and sampled peak process RSS 1,677 MiB. Q4_K_M at the same workload took 420.60 s, decoded 3.583 tokens/s, and sampled 1,292 MiB RSS. These results support runtime feasibility for the tested configuration on this phone, not a guarantee under other workloads or background-memory conditions. Across the six matched 1.5B Q4/Q8 cases, Q4 had higher decode throughput and lower sampled RSS, but prefill did not improve in every case. Perplexity/quality remains unmeasured.

At fixed 512 output tokens, longer prompts reduced prefill and decode throughput and increased request time in the observed cases. For example, 1.5B Q4 decode changed from 5.280 tokens/s at 256 input tokens to 3.583 at 2,048; request wall changed from 123.18 s to 420.60 s. The 3,072-position context capacity and F16 KV type were fixed, so this is not a KV-cache-quantization comparison. Sampled RSS did not vary monotonically with prompt length and is not a lifetime maximum.

During the main session the phone was USB-powered and charging. Thermal status remained nominal; HAL SoC-proxy maxima ranged from 77.638°C to 88.216°C across main records. The HAL sensor is not independently calibrated, and observed temperatures varied with workload order. Android energy, J/token, and tokens/s/W are unavailable: sysfs counters were denied, charging counters/voltage and generic Perfetto rails are unvalidated. Request wall excludes model startup and client prompt/template preparation; host SSE arrival intervals include USB transport. Runtime prefill/decode are the primary performance metrics.

Audited machine-readable results and plots: [Android summary and files](../analysis/android-20261115-presentation-usb/SUMMARY.md), [matched two-device comparison](../analysis/two-device-android-20261115-presentation-usb/COMPARISON.md), and raw evidence under `results/android-20261115-presentation-usb/`. The full repeated Mac and Android protocols, quality/perplexity, KV-cache comparison, profiler overhead, and validated power measurement remain pending.

## Operational lessons

- Launch native binaries from `/data/local/tmp/effai`. Backend directory discovery from Android shell's default root cwd failed while trying to stat inaccessible `/init`; changing cwd resolved startup without a security change.
- Build with explicit `GGML_NATIVE=OFF` and a recorded target CPU architecture rather than inheriting Apple host CPU assumptions. The script defaults to conservative `armv8-a`; this phone's selected build uses its verified `armv8.2-a+dotprod+fp16` features in a separate build directory. The installed NDK identifies itself as **r27-beta1**, not a final release; record the source.properties and complete CMake cache.
- Use current HAL temperatures, not the older cached section of `dumpsys thermalservice`.
- Perfetto v34 rejects `BATTERY_COUNTER_VOLTAGE`; a version-compatible config is retained. Feed config via stdin because its SELinux domain cannot open the shell-owned config file. Generic Rail1/Rail2/Rail3 readings alone do not validate physical energy measurement.
- `simpleperf stat` succeeds for a shell child process. A real model profile still needs its own execution/validation; function samples are not an exact per-GGML-operator breakdown.

Do not pool Android repeats with the existing exploratory Mac n=1 matrix or claim a symmetric controlled two-device study. Report, slides, and plots must use the final coverage audit rather than assuming every planned run completed.
