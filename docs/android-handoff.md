# Reproduce the Android CPU experiment

Run commands from the repository root on a Mac with Android SDK platform-tools, NDK, CMake, Python, Git, and curl. Enable USB debugging and authorize the connected phone. The runner expects ADB at `$HOME/Library/Android/sdk/platform-tools/adb`; `--target USB` selects one attached USB device. Use the verified [device inventory and limits](android-device.md) before interpreting results.

## Build and transfer

Download/check all four model files and extract the pinned llama.cpp source. `build_runtime.sh` also builds the Mac runtime. The recorded phone supports dotprod/FP16; use `armv8-a` for devices without those verified CPU features and label their results separately.

```sh
python3 scripts/fetch_models.py
sh scripts/build_runtime.sh
export ANDROID_NDK="$HOME/Library/Android/sdk/ndk/<installed-version>"
export EFFAI_ANDROID_CPU_ARCH='armv8.2-a+dotprod+fp16'
export EFFAI_ANDROID_BUILD_DIR="$HOME/.cache/effai/runtime/llama.cpp-79967ec596c0dacfd2251b085a57e79df292b1cc/build-android-dotprod"
sh scripts/build_android.sh

export PATH="$HOME/Library/Android/sdk/platform-tools:$PATH"
binary_sha=$(shasum -a 256 "$EFFAI_ANDROID_BUILD_DIR/bin/llama-server" | cut -d ' ' -f 1)
binary_name="llama-server-cpu-$(printf '%s' "$binary_sha" | cut -c 1-8)"
adb -d shell mkdir -p /data/local/tmp/effai
adb -d push "$EFFAI_ANDROID_BUILD_DIR/bin/llama-server" "/data/local/tmp/effai/$binary_name"
adb -d shell chmod 755 "/data/local/tmp/effai/$binary_name"
for model in "$HOME"/.cache/effai/models/*.gguf; do
  adb -d push "$model" /data/local/tmp/effai/
done
adb -d shell "cd /data/local/tmp/effai && sha256sum $binary_name *.gguf"
```

Compare device model hashes with `configs/models.json` and the binary hash with `binary_sha`. The historical selected binary had SHA-256 `c80a55ba73c0ef7154e7a53af3979052b144d7c2295ab4ca3884a678b66d4efa`; a different compiler may change it. Use the content-addressed name of your own build throughout a new session. Record NDK revision, build logs, and CMake cache; the retained historical logs used NDK r27-beta1. Confirm CPU/F16 startup settings in the logs, rather than inferring them from the build command.

## Validate monitoring and the largest workload

```sh
python3 scripts/run_android_study.py --target USB --binary "$binary_name" \
  --session android-NEW-smoke --stage smoke
python3 analysis/analyze_android.py --session android-NEW-smoke
python3 scripts/run_android_study.py --target USB --binary "$binary_name" \
  --session android-NEW-pilot --stage pilot --minimum-battery 15
```

The smoke is instrumentation only. The pilot measures a fresh idle reference, then attempts two largest-condition repetitions with strict gates. It can stop or wait when thermal conditions fail; this is evidence, not a completed repeated pilot. For an exploratory matrix, the runner requires a saved successful largest-condition auxiliary warm-up with exact 2,048/512 counts, matching runtime/model/corpus hashes, and a valid idle reference. Inspect `results/android-NEW-pilot/` before proceeding. Preserve failures and do not bypass gates or reuse another binary's warm-up.

## Run the 24-case exploratory matrix

```sh
python3 scripts/run_android_study.py --target USB --binary "$binary_name" \
  --session android-NEW-presentation --stage presentation --minimum-battery 15 \
  --pilot-session android-NEW-pilot --idle-reference-session android-NEW-pilot
python3 analysis/analyze_android.py --session android-NEW-presentation
python3 analysis/compare_devices.py --android-session android-NEW-presentation
```

The final command compares against the saved Mac session by default; add `--mac-session mac-NEW-presentation` after analyzing your own matching Mac run. Exploratory runs use bounded thermal observations, one warm-up per loaded model block, one observation per configuration, and no SD or stabilization claim. Keep the screen off and record charging, ambient conditions, background load, available sensors, and all failures. Android inference energy remains unavailable without independently validated measurement.

For the separate controlled protocol, `--stage full --pilot-session android-NEW-pilot` requires two successful largest-condition pilot records and matching provenance, and retains strict gates and repeat spacing. This is future work, not the published experiment. The raw frozen session sources preserve historical execution; current entry points are under `scripts/`. Never overwrite the published sessions when reproducing measurements.
