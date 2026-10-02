"""Read-only diagnostics of stored epoch-10 multilingual acceptability answers."""
import json
from collections import Counter
from pathlib import Path
import unicodedata
import zipfile

from scripts.merge_dfm_eval_shards import macro_f1

NATIVE = {
    'es': {'sí':'correct','si':'correct','no':'incorrect'},
    'el': {'ναι':'correct','όχι':'incorrect','οχι':'incorrect'},
    'pt_pt': {'sim':'correct','não':'incorrect','nao':'incorrect'},
    'en': {}, 'de': {'ja':'correct','nein':'incorrect'},
    'sv': {'ja':'correct','nej':'incorrect'},
}


def normalize(text):
    text = unicodedata.normalize('NFC', text).strip().casefold()
    # Diagnostic only: allow surrounding punctuation, never extract labels
    # from longer prose or pick one label from a conflicting answer.
    while text and unicodedata.category(text[0]).startswith('P'):
        text = text[1:].strip()
    while text and unicodedata.category(text[-1]).startswith('P'):
        text = text[:-1].strip()
    return text


def main():
    root = Path('logs/dfm_evals/dfm12_multilingual/epoch_10')
    results = []
    for directory in sorted(root.glob('dala_*')):
        language = directory.name.removeprefix('dala_')
        archives = sorted(directory.glob('shard_*/epoch_10/inspect/*.eval'))
        if len(archives) != 4:
            raise ValueError(f'Expected four archives: {directory}')
        records = []
        for path in archives:
            with zipfile.ZipFile(path) as archive:
                for name in archive.namelist():
                    if name.startswith('samples/') and name.endswith('.json'):
                        records.append(json.loads(archive.read(name)))
        assert len(records) == 2000
        assert len({r['id'] for r in records}) == 2000
        pairs = {'strict': [], 'punctuation': [], 'native': []}
        counts = Counter(); stops = Counter(); outputs = Counter()
        examples = {}; native_confusion = Counter()
        for r in records:
            text = r['output']['completion']; target = r['target']
            outputs[text] += 1
            strict = {'yes':'correct','no':'incorrect'}.get(text.strip().casefold())
            saved = r['scores']['linguistic-acceptability']['metadata']['prediction']
            assert strict == saved
            clean = normalize(text)
            punctuation = {'yes':'correct','no':'incorrect'}.get(clean)
            native = ({'yes':'correct','no':'incorrect', **NATIVE.get(language,{})}).get(clean)
            for name,prediction in [('strict',strict),('punctuation',punctuation),('native',native)]:
                pairs[name].append((target,prediction))
                counts[name+'_invalid'] += prediction is None
                counts[name+'_correct'] += prediction == target
            bucket = 'strict_label' if strict else ('punctuation_only' if punctuation else ('native_label' if native else 'other'))
            counts[bucket] += 1
            native_confusion[f'{target}->{native}'] += 1
            if bucket not in examples:
                examples[bucket] = dict(id=r['id'],prompt=r['input'],answer=text,target=target,
                                        native_prediction=native)
            if native and native != target and 'wrong_semantic_label' not in examples:
                examples['wrong_semantic_label'] = dict(id=r['id'],prompt=r['input'],answer=text,target=target)
            for choice in r['output'].get('choices',[]):
                stops[choice.get('stop_reason','unknown')] += 1
        f1={name:macro_f1(p,['correct','incorrect'])*100 for name,p in pairs.items()}
        stored=json.loads((directory/'merged_metrics.json').read_text())
        metrics=stored.get('metrics',stored)
        key=f'dfm_eval/dala_{language}/linguistic-acceptability/dfm_evals_macro_f1'
        assert abs(f1['strict']/100-metrics[key]) < 1e-8
        result=dict(language=language,n=len(records),native_aliases_tested=language in NATIVE,
                    f1_percent=f1,counts=dict(counts),top_outputs=outputs.most_common(12),
                    targets=dict(Counter(r['target'] for r in records)),
                    stop_reasons=dict(stops),native_confusion=dict(native_confusion),examples=examples)
        results.append(result)
        print(language, 'F1', {k:round(v,2) for k,v in f1.items()},
              'invalid', counts['strict_invalid'], 'top',outputs.most_common(3),flush=True)
    dest=Path('logs/diagnostics/epoch10_dala_label_formats')
    dest.mkdir(parents=True,exist_ok=True)
    (dest/'report.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    lines=['# Epoch-10 DaLA Label-Format Investigation','',
           'Read-only counterfactual scoring of stored generations. No production scores changed.', '',
           '| Language | Strict F1 | Punctuation-tolerant F1 | Native-label F1 | Strict invalid |',
           '|---|---:|---:|---:|---:|']
    for r in results:
        f=r['f1_percent']
        native=f"{f['native']:.2f}" if r['native_aliases_tested'] else 'not tested'
        lines.append(f"| {r['language']} | {f['strict']:.2f} | {f['punctuation']:.2f} | {native} | {r['counts']['strict_invalid']}/2000 |")
    for r in results:
        if r['language'] not in NATIVE:continue
        lines += ['', '## '+r['language'], '', 'Top answers: '+repr(r['top_outputs']), '']
        for bucket,e in r['examples'].items():
            lines += ['### '+bucket, '', '```text',str(e['prompt']),'```',
                      'Answer: '+repr(e['answer'])+'; target: '+e['target'], '']
    (dest/'report.md').write_text('\n'.join(lines)+'\n')
    print(dest)


if __name__=='__main__':
    main()
