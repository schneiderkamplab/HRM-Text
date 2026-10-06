"""Prepare additive DaLA-v2 population identities; never write W&B or old configs."""
import argparse
import copy
import json
from pathlib import Path

OLD21 = 'da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split()


def prepare(base):
    populations = []
    for source in base['populations']:
        if source['id'] not in ('dfm13_multilingual_v1', 'dfm13_all_languages_v1'):
            continue
        target = copy.deepcopy(source)
        target['id'] = source['id'].replace('_v1', '_v2')
        for lang in OLD21:
            if lang not in target['metrics']: continue
            old_la = 'dfm_eval/dala'+('' if lang=='da' else '_'+lang)+'/semantic_v1/macro_f1'
            old_gec = 'dfm_eval/gec_dala'+('' if lang=='da' else '_'+lang)+'/exact_match/mean'
            found = set()
            for binding in target['metrics'][lang].values():
                if binding and binding['key'] == old_la:
                    binding['key'] = f'dfm_eval/dala_v2_{lang}/semantic_v1/macro_f1'; found.add('la')
                if binding and binding['key'] == old_gec:
                    binding['key'] = f'dfm_eval/gec_dala_v2_{lang}/exact_match/mean'; found.add('gec')
            if found != {'la','gec'}: raise ValueError('Missing exact old bindings: '+lang)
        populations.append(target)
    if len(populations) != 2: raise ValueError('Expected32/34 base definitions')
    return dict(schema_version=1,populations=populations)


def raw_mapping():
    return dict(overall_weighting_preserved=True, sync_pause_step=3154500,
        replacements=[], append_panels=[dict(key=key,title=f'{lang} accepted DaLA v2 {label}',axis='dfm_eval/epoch')
        for lang in OLD21 for label,key in [('acceptability',f'dfm_eval/dala_v2_{lang}/semantic_v1/macro_f1'),
                                           ('GEC',f'dfm_eval/gec_dala_v2_{lang}/exact_match/mean')]],
        coordination='Exact task names proposed to Tesla; confirm before application',
        evidence_policy={'kind':'additional_raw_metrics'})


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--panel-mapping',type=Path,required=True);a=p.parse_args()
    result=prepare(json.loads(a.base.read_text()))
    for path,data in [(a.output,result),(a.panel_mapping,raw_mapping())]:
        with path.open('x') as f:json.dump(data,f,indent=2);f.write('\n')
