"""Isolated HTTP/native parity using the tiny suspension checkpoint."""
import argparse,json,os,shutil,socket,subprocess,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import requests,yaml
from tokenizers import Tokenizer,models,pre_tokenizers


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    root=args.output.resolve();root.mkdir(parents=True,exist_ok=False)
    ckpt=root/'checkpoint';ckpt.mkdir()
    source=ROOT/'logs/diagnostics/embla/cuda-suspend-v5/baseline/checkpoints'
    for name in ['all_config.yaml','train_metadata.yaml','checkpoint_state_step_6.json','unsharded_step_6.pt']:
        shutil.copyfile(source/name,ckpt/name)
    vocabulary={'<unk>':0,'<turn|>':1,'<bos>':2,'<pad>':3,**{f't{i}':i for i in range(4,256)}}
    tokenizer=Tokenizer(models.WordLevel(vocabulary,unk_token='<unk>'));tokenizer.pre_tokenizer=pre_tokenizers.WhitespaceSplit()
    tokpath=root/'tokenizer.json';tokenizer.save(str(tokpath))
    template=root/'template.jinja';template.write_text('{{ messages[0]["content"] }}')
    metadata=yaml.safe_load((ckpt/'train_metadata.yaml').read_text())
    metadata['tokenizer_info']={'tokenizer_path':str(tokpath),'chat_template_path':str(template),
        'template_mode':'jinja_chat_template','enable_thinking':False,'eos':'<turn|>'}
    (ckpt/'train_metadata.yaml').write_text(yaml.safe_dump(metadata))
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    log=(root/'server.log').open('w')
    command=[sys.executable,str(ROOT/'scripts/hrm_openai_server.py'),'--ckpt-path',str(ckpt),'--ckpt-tag','step_6',
             '--host','127.0.0.1','--port',str(port),'--model-name','embla-smoke','--batch-size','2','--max-context','64','--no-ema']
    process=subprocess.Popen(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
    try:
        url=f'http://127.0.0.1:{port}'
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError(f'Server exited {process.returncode}; inspect {root}/server.log')
            try:
                if requests.get(url+'/health',timeout=1).ok:break
            except requests.RequestException:pass
            time.sleep(1)
        else:raise TimeoutError('Server startup timeout')
        prompts=['t4 t5 t6','t7 t8']
        responses=[]
        for prompt in prompts:
            response=requests.post(url+'/v1/completions',json={'model':'embla-smoke','prompt':prompt,'max_tokens':3,'temperature':0},timeout=90)
            response.raise_for_status();responses.append(response.json()['choices'][0]['text'])
        from evaluation.engines import SimpleEngine
        expected=SimpleEngine(str(ckpt),ckpt_tag='step_6',ckpt_use_ema=False).generate(prompts,batch_size=2,max_context=64,max_tokens=3)
        if responses!=expected:raise AssertionError((responses,expected))
        (root/'result.json').write_text(json.dumps({'passed':True,'responses':responses,'native':expected,'scope':'small native HTTP greedy parity'},indent=2))
        print(json.dumps({'passed':True,'responses':responses}))
    finally:
        process.terminate()
        try:process.wait(timeout=15)
        except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
if __name__=='__main__':main()
