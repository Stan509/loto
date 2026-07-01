import sys
from core.rollout_cohorts import is_canary_device, is_phase3_device

N = 10000
canary = 0
phase3 = 0
bad = 0
for i in range(N):
    device_id = f"device_{i}"
    if is_canary_device(device_id):
        canary += 1
    if is_phase3_device(device_id):
        phase3 += 1
    # Ensure canary subset of phase3
    if is_canary_device(device_id) and not is_phase3_device(device_id):
        bad += 1

print(f"CANARY count: {canary} ({canary/N:.2%})")
print(f"PHASE3 count: {phase3} ({phase3/N:.2%})")
print(f"CANARY not in PHASE3: {bad}")
if bad != 0:
    sys.exit(1)
if not (0.045 <= canary/N <= 0.055):
    sys.exit(1)
if not (0.24 <= phase3/N <= 0.26):
    sys.exit(1)
print("Cohort validation passed")
