"""Bounded synthetic export/prefill/decode parity check; never uses training checkpoints."""
import os,json,types,argparse
from pathlib import Path
import torch
from safetensors.torch import save_file
from transformers import HrmTextConfig,HrmTextForCausalLM
from models.baselines.transformer_wrapper import TransformerWrapper
from models.baselines.hrm_nocarry_bp_warmup import HierarchicalReasoningModel
from models.lm_head import LMHead
from models.mixedlm import prompt_block_ends
from conversion.convert_to_hf import build_hf_config,convert_state_dict

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--recurrent',action='store_true');args=ap.parse_args()
    torch.manual_seed(19)
    cfg=dict(name='baselines.hrm_nocarry_bp_warmup@HierarchicalReasoningModel' if args.recurrent else 'baselines.transformer_wrapper@TransformerWrapper',n_layers=2,half_layers=True,hidden_size=128,num_heads=4,H_cycles=2,L_cycles=3,bp_min_steps=8,bp_max_steps=8,bp_warmup_ratio=0.,fwd_bwd_dtype='float32',expansion=4.,attn_type='mixedlm',init_type='fixed_normal',init_std=.02,norm_type='pre',norm_eps=1e-6,pos_emb_type='rope',rope_theta=10000.,max_seq_len=128,vocab_size=64)
    native=LMHead(HierarchicalReasoningModel(cfg) if args.recurrent else TransformerWrapper(cfg),cfg)
    tok=types.SimpleNamespace(pad_token_id=0,encode=lambda *a,**k:[7,8],convert_tokens_to_ids=lambda x:60)
    hfcfg=build_hf_config(cfg,tok);hfcfg['architectures']=['MixedLMForCausalLM'];hfcfg['torch_dtype']='bfloat16'
    out=Path('logs/diagnostics/mixedlm-20261115')/('tiny-B' if args.recurrent else 'tiny-T');out.mkdir(parents=True,exist_ok=True)
    (out/'config.json').write_text(json.dumps(hfcfg));weights,_=convert_state_dict(native.state_dict(),cfg,weight_layout='vllm_packed');save_file({k:v.contiguous() for k,v in weights.items()},out/'model.safetensors')
    refcfg=HrmTextConfig(**hfcfg);refcfg._attn_implementation='eager';hf=HrmTextForCausalLM(refcfg).eval();weights,_=convert_state_dict(native.state_dict(),cfg,weight_layout='hf_split');hf.load_state_dict(weights)
    from vllm import LLM,SamplingParams
    llm=LLM(model=str(out),skip_tokenizer_init=True,enforce_eager=True,dtype='bfloat16',max_model_len=128,max_logprobs=64,max_num_seqs=4,max_num_batched_tokens=512,gpu_memory_utilization=.03,kv_cache_memory_bytes=64*1024*1024,enable_prefix_caching=False,enable_chunked_prefill=False,compilation_config={'mode':0})
    prompts=[[1,7,8,2,3,7,8],[1,4,5,7,8],[1,7,8,60,4,7,8]]
    results=llm.generate([{'prompt_token_ids':p} for p in prompts],SamplingParams(temperature=0,max_tokens=3,ignore_eos=True,logprobs=64))
    errors=[]
    for prompt,result in zip(prompts,results):
        generated=list(result.outputs[0].token_ids)
        for step,logprobs in enumerate(result.outputs[0].logprobs):
            ids=prompt+generated[:step];n=len(ids);mask=torch.zeros(n,n,dtype=torch.bool);start=0
            for end in prompt_block_ends(prompt,[7,8],[60]):mask[start:end,:end]=True;start=end
            for i in range(len(prompt),n):mask[i,:i+1]=True
            additive=torch.zeros(1,1,n,n).masked_fill(~mask,float('-inf'))
            with torch.no_grad():expected=hf(torch.tensor([ids]),attention_mask=additive,use_cache=False).logits[0,-1].log_softmax(-1)
            actual=torch.tensor([logprobs[i].logprob for i in range(64)])
            error=float((expected-actual).abs().max());errors.append(error)
            assert error<.035,(args.recurrent,step,error)
            assert generated[step]==int(expected.argmax()),(generated[step],int(expected.argmax()))
    receipt={'recurrent':args.recurrent,'max_logprob_error':max(errors),'prompts':len(prompts),'tokens_checked':len(errors),'passed':True}
    (out/'parity.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
if __name__=='__main__':main()
