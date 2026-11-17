from types import SimpleNamespace
from eval_scheduler import runtime


def test_semantic_headline_dispatches_dedicated_publisher(tmp_path,monkeypatch):
    captured={}
    def run(argv,**kwargs):
        captured['argv']=argv;return 0
    monkeypatch.setattr(runtime,'run_command',run)
    job=SimpleNamespace(metadata={'average_prefix':'headline_danish_semantic_v1','semantic_manifest':'/manifest.json','semantic_model':'mimir-v1.8','python_bin':'/python'},log_dir=str(tmp_path))
    assert runtime.run_average(job)==0
    assert captured['argv']==['/python','scripts/log_danish_semantic_headline.py','--manifest','/manifest.json','--model','mimir-v1.8']
