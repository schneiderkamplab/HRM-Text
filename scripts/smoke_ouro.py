"""Bounded synthetic training and actual vLLM cached-decode validation."""
import argparse,json,types
from pathlib import Path
import torch
from safetensors.torch import save_file
from models.accelerator import set_accelerator_type
from models.baselines.ouro import Ouro
from models.lm_head import LMHead
from conversion.convert_to_hf import build_hf_config,convert_state_dict
from tests.test_ouro import config,batch
OUT=Path('logs/diagnostics/ouro-20261115')


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--training',action='store_true');args=ap.parse_args()
    OUT.mkdir(parents=True,exist_ok=True);torch.manual_seed(191);torch.set_num_threads(1)
    cfg=config();native=LMHead(Ouro(cfg),cfg)
    if args.training:
        set_accelerator_type('sm100');m=native.cuda().bfloat16();compiled=torch.compile(m)
        opt=torch.optim.AdamW(m.parameters(),lr=3e-4);losses=[]
        for step in range(3):
            b={k:v.cuda() for k,v in batch().items()};_,y=compiled(None,b)
            loss=y[2:].float().square().mean();loss.backward()
            assert all(p.grad is not None and torch.isfinite(p.grad).all() for p in m.parameters())
            opt.step();opt.zero_grad();losses.append(float(loss.detach()))
        torch.cuda.synchronize();receipt=dict(passed=True,compiled_updates=3,losses=losses,peak_gpu_bytes=torch.cuda.max_memory_allocated())
        (OUT/'training-smoke.json').write_text(json.dumps(receipt,indent=2));print(receipt);return
    set_accelerator_type('cpu')
    # Exercise export of learned, non-unit normalization weights.
    with torch.no_grad():
        for name,p in native.named_parameters():
            if 'layernorm' in name or 'loop_norm' in name:p.uniform_(.85,1.15)
    tok=types.SimpleNamespace(pad_token_id=0);hfcfg=build_hf_config(cfg,tok);hfcfg['torch_dtype']='bfloat16'
    out=OUT/'tiny';out.mkdir(exist_ok=True);(out/'config.json').write_text(json.dumps(hfcfg))
    weights,_=convert_state_dict(native.state_dict(),cfg);save_file(weights,out/'model.safetensors')
    from vllm import LLM,SamplingParams
    llm=LLM(model=str(out),skip_tokenizer_init=True,enforce_eager=True,dtype='bfloat16',max_model_len=128,max_logprobs=64,max_num_seqs=4,max_num_batched_tokens=512,gpu_memory_utilization=.03,kv_cache_memory_bytes=64*1024*1024,enable_prefix_caching=False,enable_chunked_prefill=False,compilation_config={'mode':0})
    prompts=[[1,2,3],[1,7,8,2,3],[1,4,5,6]];errors=[]
    results=llm.generate([{'prompt_token_ids':p} for p in prompts],SamplingParams(temperature=0,max_tokens=3,ignore_eos=True,logprobs=64))
    for prompt,result in zip(prompts,results):
        generated=list(result.outputs[0].token_ids)
        for step,lp in enumerate(result.outputs[0].logprobs):
            b=batch(torch.tensor(prompt+generated[:step]),len(prompt))
            with torch.no_grad():_,logits=native(None,b);expected=logits[-1].log_softmax(-1)
            actual=torch.tensor([lp[i].logprob for i in range(64)]);error=float((expected-actual).abs().max());errors.append(error)
            assert error<.04,(step,error)
            assert generated[step]==int(expected.argmax()),(generated[step],int(expected.argmax()))
    receipt=dict(passed=True,nontrivial_norm_weights=True,max_logprob_error=max(errors),prompts=len(prompts),tokens_checked=len(errors))
    (OUT/'parity.json').write_text(json.dumps(receipt,indent=2));print(receipt)
if __name__=='__main__':main()
