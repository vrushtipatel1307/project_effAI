# Public phone research evidence

This index describes the Android evidence published from the local research workspace. The main data are descriptive single observations, not the full repeated protocol. Model weights, compiled runtimes, credentials, device connection identifiers, personal process inventories and transient lock/cache files are excluded. Reproducible retrieval/build instructions, runtime/model hashes and frozen source snapshots are included.

## Main results

- [Verified device and measurement boundaries](android-device.md): realme RMX3930/T612, Android 14, 5.63 GiB OS-visible RAM; user identifies the phone as C61.
- [Complete USB main session](../results/android-20261115-presentation-usb/): 24 main configurations, all raw prompts, exact token arrays, requests, SSE streams, result JSON, server logs, sensor samples, frozen plan/config/models and source hashes. Includes the selected-build warm-up and first-run checkpoint audit.
- [Android summary, plots and audit](../analysis/android-20261115-presentation-usb/).
- [24 matched Mac/Android observations](../analysis/two-device-android-20261115-presentation-usb/): CSV/JSON, coverage and exact-workload audit, comparison and figure. Both devices have n=1 per configuration.

Largest 1.5B Q8_0 workload (2,048 input / 512 output): 463.64 s request wall, 2.993 runtime decode tokens/s and 1,677 MiB sampled peak RSS on the phone. At the same workload Q4_K_M observed 420.60 s, 3.583 tokens/s and 1,292 MiB. These describe the tested conditions; quality was not measured.

## Earlier and diagnostic evidence

| Directory under `results/` | Purpose / status |
| --- | --- |
| `android-readiness-20261115` | Selected read-only hardware/software inventory; identifiers omitted at collection |
| `android-20261115-setup` | Generic and selected-build logs, checksums, NDK/CMake evidence, console records, counter/profiler/corpus probes |
| `android-thermal-diagnostic-20261115` | Thermal behavior diagnostic; not a controlled main observation |
| `android-20261115-smoke`, `-smoke-v2` | Early instrumentation/gate attempts; not main results |
| `android-20261115-smoke-v3`, `-smoke-dotprod` | Validated small real workloads; analysis in matching `analysis/` directories |
| `android-20261115-pilot`, `-pilot-v2`, `-pilot-dotprod` | Largest-condition feasibility/gate evidence for generic/selected builds; do not pool with main results |
| `android-20261115-presentation` | Earlier interrupted wireless attempt; excluded from headline USB matrix |

The setup power trace uses Android power counters/rails only; its readings remain unvalidated for inference energy. Source trace and query outputs are retained as diagnostic evidence, not a valid energy result. Held-out quality corpus retrieval and checksum records do not imply perplexity was executed.

## Reproduction and integrity

Run from the repository root, with dependencies in `requirements.txt` installed:

```sh
python3 analysis/analyze_android.py --session android-20261115-presentation-usb
python3 analysis/compare_devices.py --android-session android-20261115-presentation-usb
```

Analysis requires no device or model weights. Runtime execution instructions are in [android-device.md](android-device.md), [android-handoff.md](android-handoff.md) and [protocol.md](protocol.md). Scripts include `scripts/build_android.sh`, `scripts/run_android_study.py`, `scripts/android_status.py` and `scripts/fetch_quality_corpus.py`; the frozen raw-session harness snapshots remain the historical execution evidence.

[Publication manifest](phone-publication-manifest.json) lists each included phone evidence/source file, size and SHA-256. Retained raw file bytes match the original local snapshot. Generated analysis plots may depend on local plotting-library versions; validate numerical observations and audit coverage as well as file hashes.

## Interpretation limits

One observation per configuration; no SD, significance, repeatability or strict stabilization claim. Phone was USB-powered and charging; HAL SoC proxy is not calibrated core temperature. All recorded thermal statuses were nominal; temperature alone does not establish throttling. Android inference energy/J per token/tokens per watt are unavailable. Sampled process RSS and sensors have platform-specific boundaries. Request wall excludes startup and prompt preparation; host SSE includes transport. Full controlled repeats, focused KV-cache comparison, validated power, operator attribution/overhead and model-quality evaluation remain incomplete.
