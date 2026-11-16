# Android experiment audit

Session: `android-20261115-presentation-usb`. Validated main observations in this session: 24/24; unique main configurations: 24/24.
Configurations with three observations: 0. Failed/invalid records: 0. The preserved repeated protocol would require 72 main observations; the current presentation scope is 24 once each. Smoke and pilot sessions are separate.

Each observation is rechecked against its saved prompt, request, final SSE event, output stream count, exact token budgets, no-cache and no-truncation conditions, stop type, frozen thermal policy, and runtime rate denominators.

Memory uses sampled process RSS in MiB (KiB / 1024); sample peak is not an OS lifetime maximum. CPU percent uses one core = 100%, so four threads can exceed 100%. Temperature is the HAL SoC proxy. Energy, decode J/token, and tokens/s/W are unavailable.

Context capacity is 3,072 positions; prompt plus returned output is a separate logical budget. The final tokens_cached field reports occupied KV positions, excluding the final returned token if it was not evaluated into KV. F16 KV allocation capacity is fixed across the main matrix. Request wall time starts from an already tokenized prompt and excludes model startup and client template/tokenization preparation; it is not full application launch-to-answer latency.

Host first/inter-token arrivals include USB ADB forward. Runtime prefill and decode are the preferred performance measurements. Charging, screen-off state, stock DVFS, missing ambient measurement, and thermal service limitations accompany conclusions.

Current Android and Mac matrices are exploratory n=1; no SD, repeatability, significance, or strict thermal-control claim.
