"""Reconcile measured matrix operations across the frozen256-batch sample.

Reports explicit baseline recomputation sensitivity and a scalar-operation
allowance; this does not claim measured GPU throughput or hardware instruction FLOPs.
"""
import hashlib,json
import yaml
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'logs/diagnostics/embla'


def main():
    frozen=json.loads((D/'calibration-batches.json').read_text());N=S=C=P=0
    for b in frozen['batches']:
        for p,a in zip(b['prompt_lengths'],b['answer_lengths']):
            n=p+a-1;N+=n;S+=n*n;C+=n*(n+1)/2;P+=n*(n+1)/2+p*(p-1)/2
    base=6*N*(48*(5*1024**2+3*1024*2816)+1024*262144)
    result={'frozen_batches':len(frozen['batches']),'sample_sha256':hashlib.sha256((D/'calibration-batches.json').read_bytes()).hexdigest(),
            'convention':'FMA=2; executed forward/backward matrix operations including recomputation, selection and all-token head; BF16/FP32 counted equally',
            'baseline_attention_sensitivity':[12,14,16],
            'scalar_allowance_fraction':.01,'scalar_allowance_is_estimate':True,'hardware_qualification':False,'models':{}}
    for label,d,l,probe,mode in [('embla-causal',1536,1,'causal-residual32','causal'),('embla-prefix',1536,1,'prefix-residual32','prefix'),('embla-loop',1024,4,'loop-residual32','prefix')]:
        measured=json.loads((D/f'profile-{probe}.json').read_text())
        candidate_name={'embla-causal':'embla-causal-all','embla-prefix':'embla-prefix-target','embla-loop':'embla-loop-prefix-target'}[label]
        probed=yaml.safe_load((ROOT/measured['config']).read_text())
        candidate=yaml.safe_load((D/'candidate-configs-v5'/f'{candidate_name}.yaml').read_text())
        assert measured['tokens']==32 and measured['finite_loss']
        assert probed['arch']==candidate['arch'], 'Profile architecture differs from candidate'
        quadratic=((18*(1+4*l)+8*l)+14*12*l)*d
        linear=(measured['matrix_flops']-quadratic*32**2)/32
        cost=linear*N+(18*(1+4*l)+8*l)*d*S+14*12*l*d*1024*N
        pairs=C if mode=='causal' else P
        ratios=[cost/(base+c*48*1024*pairs) for c in (12,14,16)]
        lo=min(ratios)/1.01;hi=max(ratios)*1.01
        result['models'][label]={'linear_flops_per_token':linear,'matrix_flops':cost,'ratio_at_14':ratios[1],
            'ratio_sensitivity_with_scalar_allowance':[lo,hi],'within_five_percent':lo>=.95 and hi<=1.05,
            'probe_sha256':hashlib.sha256((D/f'profile-{probe}.json').read_bytes()).hexdigest()}
    manifest=json.loads((D/'candidate-configs-v5/manifest.json').read_text())
    result['config_sha256']={label:hashlib.sha256(Path(candidate['path']).read_bytes()).hexdigest() for label,candidate in zip(('embla-causal','embla-prefix','embla-loop'),manifest['candidates'])}
    result['matrix_match_passed']=all(m['within_five_percent'] for m in result['models'].values())
    result['limitations']=['Scalar allowance is an engineering estimate, not a measured bound.','Full-size device throughput and memory remain separate gates.','Baseline recomputation range covers12–16 GEMM FLOPs per visible attention pair/head dimension.']
    path=D/'compute-match.json';path.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
