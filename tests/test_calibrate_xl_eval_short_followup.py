import json
from scripts import calibrate_xl_eval_short_followup as f


def test_1024_sequences_without_1024_graph_capture():
    args=f.command(1,59201,.95)
    assert args[args.index('--max-num-seqs')+1]=='1024'
    assert json.loads(args[-1])=={'max_cudagraph_capture_size':512}
    assert '--enforce-eager' not in args
    assert args[args.index('--max-num-batched-tokens')+1]=='16384'
