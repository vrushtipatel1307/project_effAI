# Two-device exploratory observations

Matched configurations: **24/24**. Both devices have **n=1 per configuration**; no SD, repeatability or significance claim.

Matched prompt text, exact token IDs, and full request JSON are checked across devices. See audit.json for coverage and identity issues. Runtime prefill/decode rates are preferred over host arrival proxies. Native CPU build settings, thermal history, power conditions, operating systems and sensor/sampling boundaries differ. These are observed system results, not an isolated causal hardware experiment.

| Model / quant | Input / output | Mac prefill tok/s | Android prefill tok/s | Mac decode tok/s | Android decode tok/s |
| --- | --- | ---: | ---: | ---: | ---: |
| qwen05_q4 | 256 / 128 | 575.79 | 26.53 | 81.77 | 10.77 |
| qwen05_q4 | 256 / 512 | 572.41 | 26.69 | 79.09 | 10.39 |
| qwen05_q4 | 1024 / 128 | 426.86 | 23.07 | 72.41 | 9.10 |
| qwen05_q4 | 1024 / 512 | 423.73 | 23.57 | 69.83 | 8.85 |
| qwen05_q4 | 2048 / 128 | 306.10 | 20.06 | 61.79 | 7.72 |
| qwen05_q4 | 2048 / 512 | 305.83 | 20.31 | 60.15 | 7.48 |
| qwen05_q8 | 256 / 128 | 590.74 | 31.37 | 83.66 | 11.34 |
| qwen05_q8 | 256 / 512 | 597.05 | 31.37 | 79.70 | 10.70 |
| qwen05_q8 | 1024 / 128 | 430.92 | 27.00 | 71.79 | 9.44 |
| qwen05_q8 | 1024 / 512 | 429.16 | 26.96 | 69.57 | 9.02 |
| qwen05_q8 | 2048 / 128 | 315.54 | 23.00 | 63.37 | 7.79 |
| qwen05_q8 | 2048 / 512 | 313.38 | 23.01 | 61.42 | 7.48 |
| qwen15_q4 | 256 / 128 | 155.81 | 8.74 | 38.45 | 5.27 |
| qwen15_q4 | 256 / 512 | 155.51 | 9.78 | 30.60 | 5.28 |
| qwen15_q4 | 1024 / 128 | 129.97 | 8.79 | 32.94 | 4.65 |
| qwen15_q4 | 1024 / 512 | 119.71 | 8.71 | 32.83 | 4.42 |
| qwen15_q4 | 2048 / 128 | 110.48 | 7.54 | 30.56 | 3.74 |
| qwen15_q4 | 2048 / 512 | 115.72 | 7.38 | 30.40 | 3.58 |
| qwen15_q8 | 256 / 128 | 174.39 | 8.91 | 29.71 | 4.30 |
| qwen15_q8 | 256 / 512 | 184.35 | 8.62 | 28.40 | 3.54 |
| qwen15_q8 | 1024 / 128 | 151.16 | 8.15 | 27.51 | 3.73 |
| qwen15_q8 | 1024 / 512 | 155.69 | 8.15 | 27.37 | 3.62 |
| qwen15_q8 | 2048 / 128 | 132.85 | 7.06 | 26.34 | 3.13 |
| qwen15_q8 | 2048 / 512 | 141.00 | 7.00 | 27.26 | 2.99 |

Energy is unavailable on Android for inference and cannot be compared with the Mac component estimates. Raw record paths are retained for every row.
