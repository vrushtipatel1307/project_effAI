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

## Selected CPU build and largest-case status

The generic ARMv8-a largest-case warm-up completed 2,048 input / 512 output tokens with all exact-count/cache/context/stop checks passing (543.08 s, decode 2.7985 tokens/s). It is not a measured main observation. The phone reports `asimddp`, `fphp`, and `asimdhp`; a separate `armv8.2-a+dotprod+fp16` build has passed a small real-prompt smoke and startup logs confirm `DOTPROD=1` and `FP16_VA=1`. Main results must use one consistent validated build; do not pool generic and optimized observations.

The optimized binary is `llama-server-cpu-c80a55ba`, SHA-256 `c80a55ba73c0ef7154e7a53af3979052b144d7c2295ab4ca3884a678b66d4efa`. A largest-condition selected-build warm-up completed before the presentation matrix. The full controlled pilot remains a future requirement; the presentation matrix did not claim strict stabilization.

## Reproduction

See [Android execution instructions](android-handoff.md). The selected-build largest warm-up and inherited idle baseline are retained in `results/android-20261115-pilot-dotprod/` and `results/android-20261115-pilot-v2/`; these are diagnostic provenance, excluded from the headline 24 main observations. Full controlled repeats require a successful two-repeat pilot and strict stabilization; the exploratory session does not satisfy that gate.

## Presentation matrix results — 2026-11-16

The user-approved Android presentation session `android-20261115-presentation-usb` completed **24/24 unique main configurations once each** on the selected CPU/DOTPROD/FP16 build. Independent analysis validated all 24 observations with exact input/output counts, stop-limit, no truncation, no prompt-cache reuse, and runtime-rate denominators; no main record failed. The cross-device audit matched all 24 Mac configurations with identical prompt text, token IDs, and full request JSON. These are exploratory n=1 points: no standard deviations, repeatability, significance, or strict thermal-stabilization claim.

The largest condition completed for both 1.5B quantizations. Qwen2.5-1.5B Q8_0 at 2,048 input / 512 output took 463.64 s request wall, with runtime decode 2.993 tokens/s and sampled peak process RSS 1,677 MiB. Q4_K_M at the same workload took 420.60 s, decoded 3.583 tokens/s, and sampled 1,292 MiB RSS. These results support runtime feasibility for the tested configuration on this phone, not a guarantee under other workloads or background-memory conditions. Across the six matched 1.5B Q4/Q8 cases, Q4 had higher decode throughput and lower sampled RSS, but prefill did not improve in every case. Perplexity/quality remains unmeasured.

At fixed 512 output tokens, longer prompts reduced prefill and decode throughput and increased request time in the observed cases. For example, 1.5B Q4 decode changed from 5.280 tokens/s at 256 input tokens to 3.583 at 2,048; request wall changed from 123.18 s to 420.60 s. The 3,072-position context capacity and F16 KV type were fixed, so this is not a KV-cache-quantization comparison. Sampled RSS did not vary monotonically with prompt length and is not a lifetime maximum.

During the main session the phone was USB-powered and charging. Thermal status remained nominal; HAL SoC-proxy maxima ranged from 77.638°C to 88.216°C across main records. The HAL sensor is not independently calibrated, and observed temperatures varied with workload order. Android energy, J/token, and tokens/s/W are unavailable: sysfs counters were denied, charging counters/voltage and generic Perfetto rails are unvalidated. Request wall excludes model startup and client prompt/template preparation; host SSE arrival intervals include USB transport. Runtime prefill/decode are the primary performance metrics.

Audited machine-readable results and plots: [Android summary and files](../analysis/android-20261115-presentation-usb/SUMMARY.md), [matched two-device comparison](../analysis/two-device-android-20261115-presentation-usb/COMPARISON.md), and raw evidence under `results/android-20261115-presentation-usb/`. The full repeated Mac and Android protocols, quality/perplexity, KV-cache comparison, profiler overhead, and validated power measurement remain pending.

## Runtime startup

Launch from `/data/local/tmp/effai`; backend discovery from Android shell's root working directory failed on inaccessible `/init`. Use explicit `GGML_NATIVE=OFF` and the verified target CPU architecture. The historical NDK identified itself as r27-beta1; retained CMake/build logs identify compile options. Power counters, quality evaluation, and function/operator attribution have not been validated as study outcomes.
