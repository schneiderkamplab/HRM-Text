"""Export a native Embla core to a self-contained HF remote-code directory."""
from pathlib import Path
import json
import shutil
from .hf import EmblaExperimentForCausalLM


def export_pretrained(core,destination):
    destination=Path(destination)
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Export destination must be empty')
    cfg=core.config
    cfg.decoder_loops=core.decoder_loops
    cfg.prefix_lm=core.prefix_lm
    cfg.use_cache=True
    cfg.architectures=['EmblaExperimentForCausalLM']
    cfg.auto_map={'AutoConfig':'configuration_embla.EmblaConfig',
                 'AutoModelForCausalLM':'embla_hf.EmblaExperimentForCausalLM'}
    model=EmblaExperimentForCausalLM(cfg)
    model.model.load_state_dict(core.state_dict())
    model.save_pretrained(destination,safe_serialization=True)
    root=Path(__file__).parent
    files={'hf.py':'embla_hf.py','model.py':'embla_model.py','engram.py':'embla_engram.py',
           'attention.py':'embla_attention.py','reference.py':'embla_reference.py',
           'upstream/modeling_embla.py':'modeling_embla.py','upstream/configuration_embla.py':'configuration_embla.py'}
    replacements={'.upstream.modeling_embla':'.modeling_embla','.upstream.configuration_embla':'.configuration_embla',
                  'from .model import':'from .embla_model import','from .engram import':'from .embla_engram import',
                  'from .attention import':'from .embla_attention import','from .reference import':'from .embla_reference import'}
    for source,target in files.items():
        text=(root/source).read_text()
        for old,new in replacements.items(): text=text.replace(old,new)
        # Portable inference deliberately uses reference math and does not ship
        # B200-only training kernels. HF scans even imports in disabled branches.
        for optional in ('from .residual import compiled_residual_mix',
                         'from .fa4_window import prepare_window_layout',
                         'from .fa4_window import batched_window_attention',
                         'from .fa4_window import packed_window_attention',
                         'from .sparse_triton import sparse_attention',
                         'from .relu_triton import relu_attention as operation'):
            text=text.replace(optional, "raise RuntimeError('Optimized training kernels are unavailable in portable exports')")
        (destination/target).write_text(text)
    shutil.copyfile(root/'upstream/LICENSE',destination/'LICENSE')
    shutil.copyfile(root/'upstream/source.json',destination/'upstream-source.json')
    (destination/'serving-limitations.json').write_text(json.dumps({'incremental_cache':True,'padding':False,
        'generation':'physical-layer KV cache; last-token decoder prefill','decoder_loops':core.decoder_loops,'prefix_lm':core.prefix_lm},indent=2))
