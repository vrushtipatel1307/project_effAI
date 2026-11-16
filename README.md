# Small language model efficiency testbed

This repository supports a two-device study of Qwen2.5 inference efficiency on an Apple M1 MacBook Air and an Android phone. It contains pinned configurations, source/build and model retrieval scripts, exact-token prompt construction, per-run evidence capture, analysis, and project deliverables.

## Evidence status

Both exploratory CPU sessions are complete: **24/24 unique Mac configurations and 24/24 unique Android configurations**, one observation per configuration on each device. All 24 pairs match prompt text, exact token IDs and complete request JSON. Main audits validate exact token counts, stop limits, no truncation, no prompt reuse and timing denominators.

Start with the [public phone research index](docs/phone-research.md), [device inventory](docs/android-device.md), [Android summary](analysis/android-20261115-presentation-usb/SUMMARY.md) and [matched comparison](analysis/two-device-android-20261115-presentation-usb/COMPARISON.md). Raw evidence includes the completed USB session, earlier setup/pilots and unsuccessful wireless attempts; they are labeled separately and are not pooled.

These are descriptive **n=1** observations. No SD, significance, repeatability or strict thermal-stabilization claim is supported. Android energy is unavailable; the phone was USB charging. Native kernels, OS, power and thermal histories differ, so comparisons describe the tested systems rather than isolated hardware effects.

The complete controlled protocol remains in `configs/study.json` and `docs/protocol.md`: 24 configurations per device, three measured repetitions/configuration after warm-up, a two-minute minimum gap and a strict thermal gate. The full 144-request repeated study, focused KV comparison, validated Android energy, quality and operator/overhead studies remain pending.

## Selected workload

- Models: Qwen2.5-0.5B-Instruct and Qwen2.5-1.5B-Instruct.
- Weights: official Q4_K_M and Q8_0 GGUF files; exact revisions and SHA-256 values are in `configs/models.json`.
- Inputs: 256, 1,024, and 2,048 actual formatted tokens.
- Outputs: 128 and 512 tokens; the harness forces fixed output budgets and disables prompt-prefix reuse.
- Runtime: llama.cpp commit `79967ec596c0dacfd2251b085a57e79df292b1cc`, CPU baseline, four threads, one request, F16 KV cache, 3,072 context positions.

The exact formatted token arrays, runtime output counts, stream events, timings, logs, sampled RSS, and monitoring data are retained per run. Client first-token and inter-token metrics are SSE arrival proxies, not internal kernel timings. macOS component-power estimates are not whole-device wall power. Read `docs/protocol.md` before interpreting any figure.

## Reproduce on the Mac

Requires Python 3, CMake, a C/C++ toolchain, Git/curl, and the pinned runtime build options. Large files stay outside Git in the local cache.

```sh
python3 scripts/fetch_models.py
sh scripts/build_runtime.sh
python3 scripts/run_study.py --session mac-YYYYMMDD-presentation-v1 \
  --study-config configs/presentation-pilot.json
python3 analysis/analyze.py --session mac-YYYYMMDD-presentation-v1
```

Use a new session identifier for a changed config, runtime, corpus, manifest, or harness. An existing session checks its frozen provenance before resuming. Keep the raw run folders intact. The output analysis lists coverage and failures before reporting descriptive one-observation comparisons.

## Android

The measured phone is realme RMX3930/T612 (user identifies it as C61), Android 14, with 5.63 GiB OS-visible RAM. Read [device inventory and execution boundaries](docs/android-device.md) before reproducing an experiment. Use a new session ID and record a fresh device inventory; the historical sessions must remain unchanged.

Reanalyze the saved evidence without a phone or model downloads:

```sh
python3 -m pip install -r requirements.txt
python3 analysis/analyze_android.py --session android-20261115-presentation-usb
python3 analysis/compare_devices.py --android-session android-20261115-presentation-usb
```

## Project files

- `configs/`: adopted exploratory and full repeated study settings, model manifest.
- `prompts/`: versioned source corpus.
- `scripts/`: model retrieval, runtime builds, benchmark harness, Android client recorder.
- `results/`: immutable raw session evidence; GGUF weights are excluded.
- `analysis/`: traceable summaries and plots derived from session JSON.
- `docs/`: protocol and Android handoff.
- `deliverables/source/`: editable report and slide sources, result snapshot, and renderer.
- `deliverables/output/`: rendered 16-page report, 17-slide PDF, and speaker notes.
- `deliverables/validation/`: report and slide PDF render review. The previously created local demo was rejected for publication by the user; its video, source, and review files are excluded. A replacement is pending.

## Completion checklist

- Mac presentation pilot: complete, 24/24 unique single observations; n=1 per configuration.
- Android presentation matrix: complete, 24/24 exploratory observations; 24/24 exact matched pairs with Mac.
- Full controlled repetitions and remaining focused studies: pending.
- Report PDF and slide PDF: rendered and visually reviewed.
- Demo video: prior local version rejected by the user and not published; replacement pending.
- Phone evidence publication: see docs/phone-research.md and its checksum manifest. iCollege submission is not verified.

Rebuild the report and slide PDFs with `python3 deliverables/source/build_artifacts.py`. The prior local demo build was rejected by the user and is not part of this published testbed; replacement pending.

The course repository is [github.com/addiee13/project_effAI](https://github.com/addiee13/project_effAI). Local isolated-worktree changes are not proof that the public GitHub copy contains the final work; verify publication separately.
