from types import SimpleNamespace
import numpy as np
import torch
from models.embla.inference import generate
from models.embla.model import EmblaTrainingModel
from test_embla_model import tiny_config


@torch.no_grad()
def test_multiple_requests_keep_caches_separate():
    core=EmblaTrainingModel(tiny_config(),prefix_lm=True,decoder_loops=4).eval()
    ckpt=SimpleNamespace(model=SimpleNamespace(model=core),stop_token_id=lambda:-1,
        tokenize_prompt=lambda text,condition:np.array([int(x) for x in text.split()]),
        decode_generation=lambda tokens,stop:tuple(tokens))
    prompts=[(0,('1 2 3','direct')),(1,('4 5','direct')),(2,('6 7 8 9','direct'))]
    together=dict(generate(ckpt,iter(prompts),12,3,2))
    separately={pid:dict(generate(ckpt,iter([(pid,prompt)]),12,3,1))[pid] for pid,prompt in prompts}
    assert together==separately
    assert all(len(tokens)==3 for tokens in together.values())
