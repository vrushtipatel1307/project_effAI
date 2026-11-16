#!/usr/bin/env python3
"""Verify retained raw bytes, frozen input hashes, and analyzed matrix coverage."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'docs/evidence-manifest.json').read_text())
    errors = []
    listed = {row['path'] for row in manifest['files']}
    actual = {str(p.relative_to(ROOT)) for p in (ROOT / 'results').rglob('*') if p.is_file() and p.name not in {'study.lock', 'android-study.lock'}}
    for name in sorted(actual ^ listed):
        errors.append(f'raw path mismatch: {name}')
    for row in manifest['files']:
        path = ROOT / row['path']
        if not path.is_file() or path.stat().st_size != row['bytes'] or digest(path) != row['sha256']:
            errors.append(f'raw integrity mismatch: {row["path"]}')
    sessions = ['mac-20261113-presentation-v2', 'android-20261115-presentation-usb']
    for session in sessions:
        folder = ROOT / 'results' / session
        provenance = json.loads((folder / 'provenance.json').read_text())
        for key, name in [('harness_sha256', 'harness.py'), ('core_harness_sha256', 'core-harness.py'), ('study_sha256', 'study.json'), ('models_sha256', 'models.json'), ('corpus_sha256', 'corpus-v1.txt')]:
            if key in provenance and digest(folder / name) != provenance[key]:
                errors.append(f'frozen {key} mismatch: {session}')
        rows = json.loads((ROOT / 'analysis' / session / 'validated_runs.json').read_text())
        rows = [r for r in rows if r.get('phase', 'main') == 'main']
        keys = {(r['model_id'], r['input_tokens'], r['output_tokens'], r['cache_type']) for r in rows}
        if len(rows) != 24 or len(keys) != 24:
            errors.append(f'expected 24 unique main observations: {session}')
    paired = json.loads((ROOT / 'analysis/two-device-android-20261115-presentation-usb/audit.json').read_text())
    if not paired['all_24_matched'] or paired['workload_identity_issues']:
        errors.append('paired workload audit failed')
    if errors:
        raise SystemExit('\n'.join(errors))
    print(f'PASS: {len(listed)} raw files match SHA-256; frozen inputs match; 24 observations/device and 24 identical workload pairs.')


if __name__ == '__main__':
    main()
