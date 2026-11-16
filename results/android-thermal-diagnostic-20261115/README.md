# Thermal diagnostic snapshot context

This directory is diagnostic evidence, not benchmark data or proof of an idle-gate failure.

The initial-window replay was captured while checking the user's stabilization question. By then, the live runner had already accepted the strict idle gate at 2026-11-15T23:06:22.898628Z and automatically started the largest-case warm-up. Therefore the 31-sample replay's wide range includes actual model work; calling this an idle fluctuation would be incorrect. Preserve it as an example of why a sample window must be associated with the current experiment phase before drawing conclusions.

The verified idle gate is `../android-20261115-pilot-v2/idle-baseline.json`: mean 32.07077 C, min 31.722 C, max 32.496 C, 60.175 seconds, mean CPU activity 3.67%, thermal status nominal, battery 15% and charging. No sampler reduction, temperature-sensor substitution, thermal-rule relaxation, security override, or device cooling intervention was applied. The diagnosis/remedy investigation stopped because natural settling had already resolved the original gate at this point.
