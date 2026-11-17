"""Prefetch the pinned native FP8 GLM checkpoint without using GPUs."""
import json
from pathlib import Path
from huggingface_hub import snapshot_download
root=Path('logs/dfm16/glm-handoff-20261030')
pin=json.loads((root/'model-pin.json').read_text())
path=snapshot_download(pin['repo'],revision=pin['revision'],local_dir='/work/dfm/models/GLM-5.3-Flash',max_workers=8)
(root/'download-complete.json').write_text(json.dumps(dict(pin,path=path))+'\n')
