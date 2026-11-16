#!/usr/bin/env python3
"""Retrieve the fixed WikiText-2 raw test split outside Git, with checksums."""
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

REV='927b3642933080f1b0e811e2f916e14c292992f9'
URL=f'https://huggingface.co/datasets/ggml-org/ci/resolve/{REV}/wikitext-2-raw-v1.zip'
EXPECTED='ef7edb566e3e2b2d31b29c1fdb0c89a4cc683597484c3dc2517919c615435a11'
folder=Path.home()/'.cache/effai/corpora/wikitext-2';folder.mkdir(parents=True,exist_ok=True)
archive=folder/'wikitext-2-raw-v1.zip'
if not archive.exists():
    temp=archive.with_suffix('.zip.download')
    subprocess.run(['curl','--fail','--location','--retry','3','--silent','--show-error','--output',str(temp),URL],check=True)
    temp.replace(archive)
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
if sha(archive)!=EXPECTED:raise RuntimeError('WikiText archive checksum mismatch; preserve downloaded file for investigation')
with zipfile.ZipFile(archive) as z:
    data=z.read('wikitext-2-raw/wiki.test.raw')
test=folder/'wiki.test.raw';test.write_bytes(data)
manifest={'dataset':'WikiText-2 raw','split':'test','archive_url':URL,'archive_sha256':sha(archive),'archive_bytes':archive.stat().st_size,'test_file_sha256':sha(test),'test_bytes':len(data),'test_path':str(test),'source_card':'https://huggingface.co/datasets/Salesforce/wikitext','license':'CC BY-SA 3.0 as specified by WikiText source; preserve attribution','evaluation':'same test text and settings within each checkpoint; perplexity is separate from instruction quality'}
(folder/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
print(json.dumps(manifest,indent=2))
