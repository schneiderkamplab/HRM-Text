"""Transparent preliminary matrix-FLOP ledger, not profiler qualification.

Counts forward+backward GEMMs (6 FLOPs per active weight/token), attention
recomputation and selection. Scalar operations, optimizer and radix histograms
are explicitly not included; these estimates must not freeze launch dimensions.
"""
import argparse,json,math
from pathlib import Path


def ledger(width,loops,mean_tokens,mean_pack_square,mean_pairs,vocab=262144):
    # Original ratios: dense f=d, routed f=d/4, shared f=d/2; 96 experts, top8.
    dense=math.ceil(width/64)*64
    routed=math.ceil(width/4/64)*64
    shared=math.ceil(width/2/64)*64
    local,full,sparse=15,1+4*loops,12*loops
    calls=16+16*loops
    # Q/O in every layer; K/V are projected once per physical full/window layer.
    projections=2*width*width*calls + 2*width*(width//4)*local + 2*width*(width//8)*5
    mlp=2*width*dense + (calls-1)*(2*width*(8*routed+shared)+96*width)
    engram=2*width*16*128
    matrix=6*mean_tokens*(projections+mlp+engram+width*vocab)
    # Full custom backward: forward QK/PV + recompute QK/PV + backward QK/dQ/dK/dV.
    full_attention=16*width*full*mean_pack_square
    selection=2*width*(4*loops)*mean_pack_square
    # Upper bound includes unused sparse slots and symmetric prompt local band.
    gathered=16*width*mean_tokens*(local*255+sparse*1152)
    return dict(width=width,loops=loops,dense=dense,routed=routed,shared=shared,
                projection_mlp_head=matrix,full_attention=full_attention,selection=selection,
                gathered_upper_bound=gathered,total_upper_bound=matrix+full_attention+selection+gathered)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('batches',type=Path);ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();frozen=json.loads(args.batches.read_text())
    rows=frozen['batches'];nt=0;pair_causal=0;pair_prefix=0;document_square=0
    for batch in rows:
        for p,a in zip(batch['prompt_lengths'],batch['answer_lengths']):
            n=p+a-1;nt+=n;document_square+=n*n;pair_causal+=n*(n+1)/2;pair_prefix+=n*(n+1)/2+p*(p-1)/2
    tokens=nt/len(rows)
    # Actual rank assignment is not reconstructed here; balanced-pack approximation.
    pack_square=sum((r['global_batch_totlen']/8)**2*8 for r in rows)/len(rows)
    d=1024;f=2816
    basematrix=6*tokens*(48*(5*d*d+3*d*f)+d*262144)
    baselines={mode:basematrix+16*d*48*pairs/len(rows) for mode,pairs in [('causal',pair_causal),('prefixlm',pair_prefix)]}
    candidates=[ledger(w,l,tokens,document_square/len(rows),0) for l in (1,4) for w in range(512,2049,256)]
    for row in candidates:row['relative_to_transformer_prefix']=row['total_upper_bound']/baselines['prefixlm']
    result={'qualification':False,'limitations':['matrix-only estimate','balanced rank approximation','gathered attention upper bound','no profiler cross-check','scalar/router balancing/optimizer excluded'],
            'global_batches':len(rows),'mean_tokens':tokens,'transformer48':baselines,'candidates':candidates}
    args.output.write_text(json.dumps(result,indent=2));print(json.dumps(result,indent=2))
if __name__=='__main__':main()
