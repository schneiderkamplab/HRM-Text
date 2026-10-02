"""Build the proposed registry from the pinned, CPU-inspected EuroEval catalog."""
import ast
from collections import Counter
import hashlib
import json
from pathlib import Path
import yaml

LANGUAGES = dict(nl='dutch', nb='norwegian', nn='norwegian', sv='swedish',
    is_='icelandic', fo='faroese', pl='polish', de='german', fr='french', es='spanish',
    it='italian', cs='czech', pt_pt='portuguese', fi='finnish', el='greek',
    ro='romanian', uk='ukrainian', et='estonian', ca='catalan')
LANGUAGES['is'] = LANGUAGES.pop('is_')
METRICS = {'sentiment-classification':'macro_f1', 'linguistic-acceptability':'macro_f1',
    'named-entity-recognition':'micro_f1', 'reading-comprehension':'f1',
    'summarization':'chr_f3pp', 'knowledge':'accuracy', 'common-sense-reasoning':'accuracy',
    'instruction-following':'instruction_accuracy', 'tool-calling':'tool_calling_accuracy',
    'european-values':'european_values'}
PYTHON = '/work/mimir/.home/.cache/uv/archive-v0/xPmpbGur3kEaUYAJ/bin/python'


def build(research):
    current = research['current']['datasets']
    installed = research['installed']['18.1.0']['datasets']
    old = research['installed']['17.3.0']['datasets']
    commit = research['commit']
    entries = []
    for language, module in LANGUAGES.items():
        code = 'pt-pt' if language=='pt_pt' else language
        for task, metric in METRICS.items():
            available = [d for d in current.values() if d['module']==module and
                d['task_category']==task and not d.get('unofficial') and code in d['language_codes']]
            scope = 'variant_specific' if language in ('nb','nn','pt_pt') else 'language_specific'
            # Generic Portuguese instruction following is not a verified pt-PT task.
            if not available and language=='pt_pt' and task=='instruction-following':
                available = [current['multi-ifeval-pt']]
                scope = 'generic_portuguese_variant_unverified'
            entry = dict(language=language, dataset=None, metric_key=None, metric_name=metric,
                task=task, category=task, include_in_average=False, status='coverage_gap',
                source_refs=['https://euroeval.com/datasets/'+module],
                support_basis='Official catalog registration, not remote dataset accessibility or clean-training proof.')
            if not available:
                entry['reason']='No official dataset for this language/category in the pinned current catalog.'
                entry['installed_18_1_supported']=False
                entries.append(entry)
                continue
            # Keep one official dataset per language/category, in upstream order.
            cfg=available[0];name=cfg['name'];local=installed.get(name)
            if local is None:raise ValueError('Selected dataset absent from cached 18.1.0: '+name)
            if local['task_category']!=task:raise ValueError('Task category changed across versions')
            labels=local['language_codes']
            if language in ('nb','nn') and 'nb' in labels and 'nn' in labels:
                scope='shared_norwegian_not_variant_isolated'
            notes=[]
            include=task!='european-values' and scope not in (
                'shared_norwegian_not_variant_isolated','generic_portuguese_variant_unverified')
            status='supported'
            if scope=='shared_norwegian_not_variant_isolated':
                notes.append('Shared Norwegian corpus: one evaluation only; not two independent NB/NN scores.')
            if scope=='generic_portuguese_variant_unverified':
                status='variant_unverified'
                notes.append('Official config lists pt only, not pt-pt. Do not claim European-Portuguese-only coverage.')
            if task=='european-values':
                notes.append('Values alignment is diagnostic, not a capability/accuracy headline average.')
            risks=['full_training_overlap_not_audited']
            if name=='norquad':
                status='contamination_flagged';include=False
                risks.append('norquad_training_inclusion_and_known_passage_overlap')
                notes.append('DFM12 authorized all 1886 Wikipedia-train candidates; 1071 share passages with upstream validation/test, zero exact question matches in prior review. This does not prove EuroEval-mini question leakage or clearance.')
            if name in ('multi-wiki-qa-nb','multi-wiki-qa-nn'):
                notes.append('Alternative to NorQuAD, but requires its own overlap review; not automatically clean.')
            entry.update(dataset=name, metric_key=f"euroeval/{'_'.join(labels)}/{task}/{name}/{metric}",
                include_in_average=include,status=status,datasets=[name],deduplication_key=name,
                group_id=language+'__'+name, euroeval_result_languages=labels,language_scope=scope,
                source_dataset=local['source'], source_url='https://huggingface.co/datasets/'+local['source'],
                installed_18_1_supported=True,installed_17_3_supported=name in old,
                upstream_official=True, contamination_flags=risks, notes=notes,
                candidate_alternatives=[d['name'] for d in available[1:]],
                metrics_code_symbols=local['metrics'],
                installed_code_sha256=research['installed']['18.1.0']['file_sha256']['dataset_configs/'+module+'.py'],
                source_refs=entry['source_refs']+[cfg['code_ref'],
                    'https://github.com/EuroEval/EuroEval/blob/'+commit+'/src/euroeval/tasks.py',
                    'https://huggingface.co/datasets/'+local['source']])
            entries.append(entry)
    catalog_path=Path('eval_scheduler/eval_scheduler/catalog.py')
    baseline=[]
    for node in ast.parse(catalog_path.read_text()).body:
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='EUROEVAL_GROUPS' for t in node.targets):
            baseline=ast.literal_eval(node.value)
    controls=[]
    for name in baseline:
        cfg=installed[name];task=cfg['task_category'];metric=METRICS[task]
        controls.append(dict(language=cfg['language_codes'][0],dataset=name,task=task,
            metric_key=f"euroeval/{'_'.join(cfg['language_codes'])}/{task}/{name}/{metric}",
            installed_18_1_supported=True,preserve_existing=True,
            current_upstream_official=not current[name].get('unofficial',False)))
    summary={language:dict(supported=sum(e['dataset'] is not None for e in entries if e['language']==language),
        average_eligible=sum(e['include_in_average'] for e in entries if e['language']==language),
        gaps=[e['category'] for e in entries if e['language']==language and e['dataset'] is None]) for language in LANGUAGES}
    return dict(schema='dfm12-euroeval-multilingual-v1', researched_at='2026-09-30',
        activation='proposed_registry_only_no_active_plan_modified',languages=list(LANGUAGES),
        categories=list(METRICS), entries=entries,coverage=summary,existing_da_en_groups=controls,
        selection_policy='One official dataset per language/category, first in pinned upstream order; all alternatives listed. Keep one dataset per execution group. Existing DA/EN groups unchanged.',
        execution=dict(python=PYTHON, euroeval_bin=PYTHON+' '+str(Path('scripts/euroeval_api_no_flash_attn_guard.py').resolve()),
            version='18.1.0',help_smoke_passed=True, no_environment_changes=True,
            dataset_arguments=['--dataset','{dataset}'],do_not_combine_dataset_with=['--language','--task'],
            deduplicate_by='deduplication_key', run_statuses=['supported','contamination_flagged','variant_unverified'],
            contamination_policy='Run flagged diagnostics if scheduled, never label them clean or include in clean averages.',
            data_access_preflight='Not performed: catalog support does not prove remote split accessibility.',
            requested_checkpoints=['epoch_10_baseline','step_2900000','all_future_checkpoints'],
            checkpoint_launch_authorized_here=False,
            comparisons='Keep tokenizer/chat-template/EMA choice, bootstrap iterations, dataset revisions and scorer version matched across checkpoints.'),
        source_evidence=dict(official_site='https://euroeval.com/datasets',
            official_index='https://euroeval.com/llms.txt',upstream_commit=commit,upstream_version='18.2.0',
            upstream_file_sha256=research['current']['file_sha256'],
            cached_18_1=dict(path=research['installed']['18.1.0']['path'],file_sha256=research['installed']['18.1.0']['file_sha256']),
            hrm_base=dict(version='17.3.0',path=research['installed']['17.3.0']['path']),
            existing_suite_path=str(catalog_path),existing_suite_sha256=hashlib.sha256(catalog_path.read_bytes()).hexdigest()),
        recommendations=[
            'Retain existing English 10 groups: SST5, ScaLA, CoNLL, SQuAD, CNN/DailyMail, UK knowledge, HellaSwag, IFEval, BFCL-v2 and VaLEU. No extra English EuroEval group is required for baseline category parity.',
            'BFCL-v2 is registered only for English; do not relabel it as native tool calling in the other 19 languages.',
            'NorQuAD remains visible as contaminated diagnostic. Alternatives multi-wiki-qa-nb/nn exist but are unofficial and not decontaminated.',
            'FLEURS training inclusion creates a known FLORES-lineage risk; translation tasks are outside this baseline-parity registry.',
            'Upstream now prefers DaLA over ScaLA-da and Winogrande-da over HellaSwag-da; retain existing historical DA tasks for comparisons rather than silently replacing them.',
            'Current official knowledge alternatives need not measure the same culture/content as Danish citizen tests or English Life-in-the-UK; category parity is not identical difficulty.',
            'No benchmark-clean claims for Wikipedia-derived tasks: DynaWord, European Wikipedia and generated grounded data require future exact/semantic overlap review.'],
        contamination_evidence=['wiki/pages/dfm12-norwegian-dynainstruct.md',
            'data/dfm12/norwegian-benchmark-review-20260925/review.json'])


if __name__=='__main__':
    result=build(json.loads(Path('/tmp/dfm12-euroeval-research.json').read_text()))
    Path('config/euroeval_dfm12_multilingual.yaml').write_text(yaml.safe_dump(result,sort_keys=False,allow_unicode=False))
    print('entries',len(result['entries']),'statuses',dict(Counter(e['status'] for e in result['entries'])))
    print(json.dumps(result['coverage'],indent=2))
