import pytest
import torch
from transformers import AutoModelForCausalLM
from models.embla.model import EmblaTrainingModel
from models.embla.export import export_pretrained
from test_embla_model import tiny_config


@pytest.mark.parametrize('kernels',[False,True])
@pytest.mark.parametrize('prefix,loops',[(False,1),(True,1),(True,4)])
def test_portable_export(tmp_path,prefix,loops,kernels):
    model=EmblaTrainingModel(tiny_config(),prefix_lm=prefix,decoder_loops=loops,fa4_window=kernels,fused_relu=kernels,fused_sparse=kernels,single_topk=kernels)
    export_pretrained(model,tmp_path)
    restored=AutoModelForCausalLM.from_pretrained(tmp_path,trust_remote_code=True)
    assert not restored.model.fa4_window and not restored.model.fused_relu and not restored.model.fused_sparse
    ids=torch.tensor([[1,2,3,4]])
    prompt=torch.tensor([[True,True,False,False]]) if prefix else None
    torch.testing.assert_close(model(ids,prompt_mask=prompt),restored(ids,prompt_mask=prompt).logits,atol=1e-7,rtol=1e-6)


def test_prefix_generation_keeps_original_prompt_length():
    from models.embla.hf import EmblaExperimentForCausalLM
    cfg=tiny_config();cfg.prefix_lm=True;cfg.decoder_loops=2
    model=EmblaExperimentForCausalLM(cfg).eval()
    ids=torch.tensor([[1,2,3]])
    generated=model.generate(ids,max_new_tokens=2,do_sample=False,pad_token_id=0,eos_token_id=None)
    expected=ids
    with torch.no_grad():
        for _ in range(2):
            logits=model(expected,prefix_lengths=torch.tensor([3])).logits
            expected=torch.cat((expected,logits[:,-1].argmax(-1)[:,None]),-1)
    torch.testing.assert_close(generated,expected)
