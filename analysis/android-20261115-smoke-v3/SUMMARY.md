# Android experiment audit

Session: `android-20261115-smoke-v3`. Validated main observations in this session: 0/0; unique main configurations: 0/0.
Configurations with three observations: 0. Failed/invalid records: 0. The adopted complete Android matrix requires 24 configurations and 72 main observations; smoke and pilot sessions are separate.

Each observation is rechecked against its saved prompt, request, final SSE event, output stream count, exact token budgets, no-cache and no-truncation conditions, stop type, strict gate, and runtime rate denominators.

Memory uses sampled process RSS in MiB (KiB / 1024); sample peak is not an OS lifetime maximum. CPU percent uses one core = 100%, so four threads can exceed 100%. Temperature is the HAL SoC proxy. Energy, decode J/token, and tokens/s/W are unavailable.

Host first/inter-token arrivals include wireless ADB transport. Runtime prefill and decode are the preferred performance measurements. Charging, screen-off state, stock DVFS, missing ambient measurement, and thermal service limitations accompany conclusions.

Mac comparison must retain the existing n=1 exploratory limitation. Android repeats do not retroactively validate the Mac protocol.
