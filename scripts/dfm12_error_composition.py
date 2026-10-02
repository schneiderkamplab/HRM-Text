"""Read-only sampled DaLA correction exposure and explicit corruption metadata."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import yaml

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dfm12.io import file_hash, load, write_json

LANGUAGES=('da','en','nb','nn','sv','is','fo','nl','pl','de','fr','es','it','cs','pt_pt','fi','et','ca','el','ro','uk')
BINS=('0','1','2','3','4+','unknown')
CATEGORIES=('spelling','grammar','unclassified')
GRAMMAR_TYPES=frozenset(('adjective_definite','adjective_gender','adjective_number','adjective_case',
    'determiner_gender','determiner_number','determiner_case','governed_infinitive','perfect_verb_form',
    'pronoun_case','preposition_case','verb_number_agreement','verb_person_agreement','subject_verb_agreement',
    'demonstrative_number','do_support_form','modal_verb_form','noun_number','perfect_participle',
    'article_number','article_gender','adjective_inflection','verb_form','grammar'))
BUILD=ROOT/'data/dfm12/training-build-completed-campaign-20260929'
TOKENS=ROOT/'data/tokenized_dfm12_additions-completed-campaign-20260929'
SAMPLED=ROOT/'data/sampled_dfm12_xl_epoch11_noidentity_additions'
ACTIVE=ROOT/'data/sampled_dfm12_xl_epoch11_noidentity'
DALA=Path('/work/mimir/DaLA')


def lines(path):
    with (gzip.open(path,'rt') if str(path).endswith('.gz') else Path(path).open()) as f:
        for line in f:
            yield json.loads(line)


def pair_key(original, corrupted):
    return hashlib.sha256(json.dumps([original,corrupted],ensure_ascii=False).encode()).digest()


def annotation(pair):
    edits=pair.get('edits')
    if not isinstance(edits,list) or not edits:
        return None
    original,corrupted=pair['original'],pair['corrupted']
    cursor=0; chunks=[]; values=[]
    for e in sorted(edits,key=lambda e:e['start']):
        a,b=e['start'],e['end']
        if not cursor<=a<=b<=len(original) or original[a:b]!=e['original']:
            return None
        if corrupted[e['corrupted_start']:e['corrupted_end']]!=e['replacement']:
            return None
        chunks.extend((original[cursor:a],e['replacement']));cursor=b
        values.append((e.get('rule_id'),e.get('corruption_type'),e['original'],e['replacement']))
    chunks.append(original[cursor:])
    return tuple(values) if ''.join(chunks)==corrupted else None


def insert_lookup(lookup,key,value):
    # Identical text with conflicting annotations is unknown, never an arbitrary winner.
    if key in lookup and lookup[key]!=value:
        lookup[key]=None
    else:
        lookup[key]=value


def producer_path(lang):
    if lang in ('nb','nn','sv','fo','pl','is'):
        return DALA/'la_output/six_language_candidates_recovery_v1'/lang/'train/pairs.jsonl'
    if lang in ('en','nl'):
        name='english-common-pile' if lang=='en' else 'dutch-dynaword'
        return DALA/f'export-upload/dala-{name}/provenance/train.pairs.jsonl.gz'
    code=lang.replace('_','-')
    return DALA/f'export-upload/european-audited-20260928/dala-{code}-audited/provenance/train.pairs.jsonl.gz'


def load_annotations(path):
    lookup={}; count=0
    for pair in lines(path):
        if pair.get('split')!='train':
            raise ValueError('Non-train producer metadata')
        original,corrupted=pair['original'],pair['corrupted']
        insert_lookup(lookup,pair_key(original,original),())
        insert_lookup(lookup,pair_key(original,corrupted),annotation(pair))
        count+=1
    return lookup,count


def empty_language():
    return dict(correction_rows=0,correction_tokens=0,pct_all_training_rows=0.0,pct_all_training_tokens=0.0,
        mistake_count_rows={k:0 for k in BINS},mistake_count_pct_within_correction={k:None for k in BINS},
        distinct_rule_ids=None,distinct_edit_pairs=None,corruption_type_edit_occurrences={},
        coverage_notes=[],scope='Identified sampled DFM12 DaLA additions only; inherited coverage missing',
        total_correction_rows_including_inherited=None,
        categories={category:dict(rows=0,tokens=0,pct_all_training_rows=0.0,pct_all_training_tokens=0.0,
            pct_within_correction_rows=None,distinct_rule_ids=None,distinct_edit_pairs=None) for category in CATEGORIES})


def category_of(category):
    if category=='spelling':return 'spelling'
    if category in GRAMMAR_TYPES:return 'grammar'
    return 'unclassified'


def add_row(stats,edits,weight,tokens,rules,edit_pairs,types,category_rules=None,category_pairs=None):
    if not weight:return
    stats['correction_rows']+=int(weight);stats['correction_tokens']+=int(tokens)
    memberships=set()
    if edits is None:
        bucket='unknown'
        memberships.add('unclassified')
    else:
        count=len(edits);bucket=str(count) if count<4 else '4+'
        for rule,category,original,replacement in edits:
            if rule:rules.add(rule)
            edit_pairs.add((original,replacement))
            types[category or 'unknown']+=int(weight)
            group=category_of(category);memberships.add(group)
            if category_rules is not None and rule:category_rules[group].add(rule)
            if category_pairs is not None:category_pairs[group].add((original,replacement))
    stats['mistake_count_rows'][bucket]+=int(weight)
    for group in memberships:
        stats['categories'][group]['rows']+=int(weight)
        stats['categories'][group]['tokens']+=int(tokens)


def make_report():
    receipt=load(ACTIVE/'build-receipt.json');epoch=receipt['epochs'][0]
    rows=int(epoch['base_rows']+epoch['added_rows']);tokens=int(load(ACTIVE/'metadata.json')['total_length'])
    if len(np.load(ACTIVE/'epoch_10/inst_len.npy',mmap_mode='r'))!=rows:
        raise ValueError('Active epoch row count differs from receipt')
    return dict(schema_version=1,status='in_progress',
        denominators=dict(sampled_rows=rows,sampled_tokens=tokens,dataset=str(ACTIVE),epoch='epoch_10',
            inherited_rows=int(epoch['base_rows']),addition_rows=int(epoch['added_rows'])),
        definitions=dict(correction_rows='Sampled row occurrences whose accepted student task is correction. Acceptability rows excluded.',
            mistake_count='Number of explicit producer edits, not edit distance. Zero requires an exact producer clean-control match.',
            distinct_rule_ids='Distinct nonempty producer edit.rule_id values among sampled annotated corrupted correction rows; lower bound when coverage partial.',
            distinct_edit_pairs='Distinct exact (original edit span, replacement edit span) strings; NOT whole-sentence pairs and NOT edit distance.',
            percentages='100 * sampled identified correction row/token exposure divided by whole active training row/token denominator.',
            distribution_denominator='All identified sampled correction rows in this language, including clean controls and unknown annotations.',
            categories='Spelling is explicit corruption_type=spelling. Grammar uses the enumerated morphology/syntax label allowlist. Other labels and missing annotations are unclassified. Mixed rows/tokens count in both categories; categories are not additive. Clean controls count in neither.',
            grammar_type_allowlist=sorted(GRAMMAR_TYPES),
            annotation_join='Exact (target original sentence, input sentence) join to train-only producer pairs; conflicts unknown.',
            limitations='Not a complete whole-corpus correction census. Inherited base and non-DaLA embedded correction instructions lack complete local attribution.'),
        languages={lang:empty_language() for lang in LANGUAGES},components=[],evidence=[],
        missing_coverage=[dict(scope='inherited_DFM11_base',rows=int(epoch['base_rows']),
            reason='Local transferred sampled base lacks the complete tokenized source-boundary/row provenance map; Danish DaLA and Folketing correction metadata cannot be joined to active sampled rows reliably.')])


def sampled_index():
    starts=np.load(SAMPLED/'epoch_0/inst_start.npy',mmap_mode='r')
    prompt=np.load(SAMPLED/'epoch_0/inst_len.npy',mmap_mode='r')
    response=np.load(SAMPLED/'epoch_0/resp_len.npy',mmap_mode='r')
    order=np.argsort(starts,kind='stable')
    return np.asarray(starts[order]),np.asarray(prompt[order]+response[order])


def directory_ranges():
    policy=yaml.safe_load((ROOT/'data/dfm12/xl-epoch11-noidentity/prefix_config.yaml').read_text())
    result=[];offset=0
    for path in sorted(TOKENS.iterdir()):
        if not path.is_dir() or not any(path.name.startswith(p['prefix']) for p in policy):continue
        n=len(np.load(path/'tokens.npy',mmap_mode='r'))
        result.append((path,offset,offset+n));offset+=n
    if offset!=len(np.load(SAMPLED/'tokens.npy',mmap_mode='r')):
        raise ValueError('Source token offset inventory mismatch')
    return result


TV2_GRAMMAR=frozenset(('flip_en_et_suffix','flip_indefinite_article','corrupt_noun_r',
    'corrupt_verb_r','corrupt_ende_ene','flip_pronouns','corrupt_adjective_r',
    'flip_han_hun_to_det','flip_ligge_laegge','flip_nogle_nogen','flip_som_der','corrupt_genitive'))


def inherited_observation(component,row,raw=None):
    """Return explicit scope/count/type; never infer errors by edit distance."""
    if component.startswith('giannor_tv2r_instruction__giannor_gec_dala_tv2r_it__'):
        rule=row.get('corruption_type'); pair=None
        category='spelling' if rule=='corrupt_spelling' else 'grammar' if rule in TV2_GRAMMAR else 'unclassified'
        count=1 if rule else 0 if row.get('target_equals_input_sentence') else None
        if raw is not None:
            _,split,index=row['row_id'].rsplit(':',2)
            sample=raw['samples'][int(index)]
            messages=[dict(role='user',content=raw['direction'].strip()+'\n\n'+sample['content'].strip()),
                      dict(role='assistant',content=sample['response'].strip())]
            h=hashlib.sha256(json.dumps(messages,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest()
            if h!=row['messages_sha256']:
                raise ValueError('TV2R raw/converted row mismatch: '+row['row_id'])
            a,b=sample.get('affected_token_1'),sample.get('affected_token_2')
            original,corrupted=sample['response'].strip(),sample['content'].strip()
            count=1 if rule else 0 if original==corrupted else None
            if isinstance(a,str) and a and isinstance(b,str):
                # Confirm an explicitly declared pair, not a diff-derived pair.
                positions=(i for i in range(len(original)) if original.startswith(a,i))
                if any(original[:i]+b+original[i+len(a):]==corrupted for i in positions):pair=(a,b)
        return 'da','TV2R correction',count,category,rule,pair
    if component.startswith('dfm11-folketingets-dokumenter-error-correction__'):
        count=row.get('metadata',{}).get('dfm11_repair',{}).get('declared_ocr_edits')
        if isinstance(count,bool) or not isinstance(count,int) or count<0:count=None
        return 'da','OCR correction',count,'unclassified',None,None
    if 'denoising__' in component:
        return ('en' if component.startswith('common-pile') else 'da'),'denoising',None,'unclassified',None,None
    if component.startswith('posttrain_coedit__'):
        return 'en','CoEdit editing',None,'unclassified',None,None
    if component.startswith('dfm8-synthetic-danish-summarization-rewrite-controls__'):
        prompt=(row.get('user_prefix') or row.get('prompt_prefix') or '').lower().strip()
        # Restrict the mixed summary/title/editing source to identifiable editing requests.
        if prompt.startswith(('omskriv','omformuler','ret ')) or prompt.startswith('kan du skrive denne tekst om'):
            return 'da','synthetic rewrite',None,'unclassified',None,None
    return None


def add_inherited_observation(stats,obs,weight,tokens,rules,pairs,category_rules,category_pairs):
    if not weight:return
    _,_,count,category,rule,pair=obs
    stats['correction_rows']+=int(weight);stats['correction_tokens']+=int(tokens)
    bucket='unknown' if count is None else str(count) if count<4 else '4+'
    stats['mistake_count_rows'][bucket]+=int(weight)
    if count!=0:
        stats['categories'][category]['rows']+=int(weight)
        stats['categories'][category]['tokens']+=int(tokens)
    if rule:
        rules.add(rule);category_rules[category].add(rule)
        types=stats['corruption_type_edit_occurrences']
        types[rule]=types.get(rule,0)+int(weight)
    if pair:
        pairs.add(pair);category_pairs[category].add(pair)


def augment_inherited(report,root):
    if 'inherited_recovery' in report:raise ValueError('Already augmented; use the preserved additions-only report')
    receipt=root/'sampled_error_rows/receipt.json'
    verified=load(receipt)
    if (verified.get('schema')!='dfm11-sampled-error-row-counts-v1'
            or verified.get('status')!='complete_tokenized_ordinal_counts_raw_source_alignment_not_claimed'
            or verified.get('sampled_start_and_length_checks') is not True
            or verified.get('selected_epoch')!='data/sampled_dfm11/epoch_0'
            or verified.get('source_map_sha256')!=file_hash(root/'source-map.json')):
        raise ValueError('Missing or invalid verified inherited sampled-index receipt')
    verified_outputs={s['component']:s for s in verified['outputs']}
    manifest_paths=[root/p/'manifest.json' for p in ('error_metadata','coedit_metadata','rewrite_metadata')]
    inventory={};missing=[]
    for path in manifest_paths:
        if not path.exists():continue
        manifest=load(path)
        missing.extend(manifest.get('missing',[]))
        for s in manifest['sources']:inventory[s['component']]=(path.parent,s)
        report['evidence'].append(dict(path=str(path),sha256=file_hash(path)))
    recovered_warnings=[x for x in missing if any(x.startswith(c+':') for c in inventory)]
    missing=[x for x in missing if x not in recovered_warnings]
    additions={};diversity={};components=[]
    def accumulate(obs,weight,tokens):
        lang=obs[0]
        if lang not in additions:
            additions[lang]=empty_language()
            diversity[lang]=(set(),set(),{c:set() for c in CATEGORIES},{c:set() for c in CATEGORIES})
        add_inherited_observation(additions[lang],obs,weight,tokens,*diversity[lang])
    for component,(directory,source) in sorted(inventory.items()):
        index_path=root/'sampled_error_rows'/(component+'.npz')
        if not index_path.exists() or component not in verified_outputs:
            missing.append(component+': no sampled ordinal receipt');continue
        if file_hash(index_path)!=verified_outputs[component]['sha256']:
            raise ValueError('Sampled ordinal file hash mismatch: '+component)
        path=directory/source['metadata']
        if file_hash(path)!=source['metadata_sha256']:raise ValueError('Metadata hash mismatch: '+str(path))
        with np.load(index_path,allow_pickle=False) as indices:
            weights=indices['sampled_multiplicity'];tokens=indices['rendered_tokens']
            if not np.array_equal(indices['tokenized_ordinal'],np.arange(len(weights))):
                raise ValueError('Non-contiguous tokenized ordinals')
            # Equality plus one target per source row rules out silent skipped/expanded ordinal shifts.
            single=True;candidate_count=0
            for r in lines(path):
                targets=1 if r.get('condition')=='direct' and 'response' in r else r.get('nonempty_assistant_messages',r.get('assistant_messages',0))
                single &= targets in (0,1)
                candidate_count+=targets
            if not single or candidate_count!=len(weights):
                reason=component+f': source target alignment unresolved ({candidate_count} candidates vs {len(weights)} targets)'
                missing.append(reason)
                # Uniform correction sources still have exact aggregate exposure, but
                # assigning per-row corruption annotations would shift after skips.
                uniform=inherited_observation(component,{})
                if uniform is not None:
                    obs=(*uniform[:2],None,'unclassified',None,None)
                    n=int(weights.sum());nt=int(tokens.sum())
                    accumulate(obs,n,nt)
                    components.append(dict(component=component,source_rows=source['rows'],tokenized_targets=len(weights),
                        sampled_correction_rows=n,sampled_correction_tokens=nt,source=source['source'],
                        source_sha256=source['source_sha256'],metadata_sha256=source['metadata_sha256'],
                        ordinal_npz_sha256=file_hash(index_path),alignment='Uniform correction task exposure only; per-row annotations unknown after tokenizer skips'))
                continue
            raw=None
            if 'giannor_gec_dala_tv2r_it__' in component:
                split=component.rsplit('__',1)[-1].split('.')[0]
                raw_path=root/'raw/giannor_gec_dala_tv2r_it'/('val.json' if split=='validation' else split+'.json')
                raw=load(raw_path)
                report['evidence'].append(dict(path=str(raw_path),sha256=file_hash(raw_path)))
            ordinal=0;selected=0;exposure=0;subtypes=Counter()
            for r in lines(path):
                targets=1 if r.get('condition')=='direct' and 'response' in r else r.get('nonempty_assistant_messages',r.get('assistant_messages',0))
                if not targets:continue
                weight,nt=int(weights[ordinal]),int(tokens[ordinal]);ordinal+=1
                obs=inherited_observation(component,r,raw)
                if obs is None or not weight:continue
                accumulate(obs,weight,nt)
                selected+=weight;exposure+=nt;subtypes[obs[1]]+=weight
            components.append(dict(component=component,source_rows=source['rows'],tokenized_targets=len(weights),
                sampled_correction_rows=selected,sampled_correction_tokens=exposure,subtypes=dict(subtypes),
                source=source['source'],source_sha256=source['source_sha256'],metadata_sha256=source['metadata_sha256'],
                ordinal_npz_sha256=file_hash(index_path),alignment='Single-target expansion count equals tokenized count; no skipped target or expansion shift'))
    for lang,extra in additions.items():
        previous=report['languages'][lang]
        if previous['correction_rows'] is None:previous=empty_language();report['languages'][lang]=previous
        rules,pairs,category_rules,category_pairs=diversity[lang]
        # Only Danish gains new explicit pairs; English inherited edits have no pair annotations.
        if previous.get('distinct_edit_pairs') and pairs:raise ValueError('Cannot union unavailable prior pair identities')
        for key in ('correction_rows','correction_tokens'):previous[key]+=extra[key]
        for b in BINS:previous['mistake_count_rows'][b]+=extra['mistake_count_rows'][b]
        previous['rule_ids']=sorted(set(previous.get('rule_ids',[]))|rules)
        previous['distinct_rule_ids']=len(previous['rule_ids'])
        previous['distinct_edit_pairs']=(previous['distinct_edit_pairs'] or 0)+len(pairs)
        for key,value in extra['corruption_type_edit_occurrences'].items():
            previous['corruption_type_edit_occurrences'][key]=previous['corruption_type_edit_occurrences'].get(key,0)+value
        for category in CATEGORIES:
            s=previous['categories'][category];e=extra['categories'][category]
            for key in ('rows','tokens'):s[key]+=e[key]
            s['rule_ids']=sorted(set(s.get('rule_ids',[]))|category_rules[category])
            s['distinct_rule_ids']=len(s['rule_ids'])
            s['distinct_edit_pairs']=(s['distinct_edit_pairs'] or 0)+len(category_pairs[category])
            s['pct_all_training_rows']=100*s['rows']/report['denominators']['sampled_rows']
            s['pct_all_training_tokens']=100*s['tokens']/report['denominators']['sampled_tokens']
            s['pct_within_correction_rows']=100*s['rows']/previous['correction_rows']
        previous.update(status='complete_identified_sources',scope='Identified additions and aligned inherited correction/editing tasks; unresolved sources explicitly excluded',
            distinct_counts_are_lower_bounds=True,
            pct_all_training_rows=100*previous['correction_rows']/report['denominators']['sampled_rows'],
            pct_all_training_tokens=100*previous['correction_tokens']/report['denominators']['sampled_tokens'],
            mistake_count_pct_within_correction={b:100*v/previous['correction_rows'] for b,v in previous['mistake_count_rows'].items()},
            coverage_notes=['Includes known correction/editing tasks with unknown annotations; denoising/OCR are not automatically spelling or grammar.',
                'TV2R explicit affected-token pairs count only when they exactly reconstruct the corrupted sentence. No diff inference.',
                'Producer correction counts are not human-certified linguistic error counts. Residual alignment and mixed-task gaps are in inherited_recovery.missing.'])
        if lang not in report['completed_languages']:report['completed_languages'].append(lang)
    report['inherited_recovery']=dict(root=str(root),receipt_sha256=file_hash(receipt),components=components,missing=missing,
        superseded_extraction_warnings=recovered_warnings,
        implementation_sha256=file_hash(Path(__file__)),
        extraction_implementation_sha256=file_hash(ROOT/'scripts/recover_dfm11_error_provenance.py'))
    report['missing_coverage_before_recovery']=report['missing_coverage']
    report['missing_coverage']=[dict(scope='inherited annotation/alignment residuals',reason=x) for x in missing]
    report['missing_coverage'].append(dict(scope='mixed/general instruction tasks',
        reason='Only explicit correction/editing source families and recognizable rewrite requests counted; this is not an exhaustive semantic classification of all training prompts.'))
    report['definitions']['correction_rows']='Sampled correction/editing row occurrences, including identified inherited correction, CoEdit, denoising and explicit rewrite requests; acceptability and ordinary summarization excluded.'
    report['definitions']['inherited_categories']='TV2R corrupt_spelling maps to spelling; enumerated morphology/syntax rules map to grammar; flip_far_for remains unclassified. OCR, denoising, and editing without error taxonomy remain unclassified.'
    report['definitions']['tv2_grammar_rules']=sorted(TV2_GRAMMAR)
    report['definitions']['inherited_mistake_count']='TV2R named single corruption or explicit clean control; Folketing stored declared_ocr_edits only with verified ordinal alignment; all other counts unknown.'
    report['definitions']['limitations']='Identified correction/editing source exposure, not an exhaustive semantic census. Inherited task exposure can be exact while error type/count annotations remain unknown; see residual coverage entries.'
    report['status']='complete_with_explicit_missing_inherited_coverage'
    report['identified_correction_rows']=sum(r['correction_rows'] or 0 for r in report['languages'].values())
    report['identified_correction_tokens']=sum(r['correction_tokens'] or 0 for r in report['languages'].values())
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/reports/dfm12_error_composition.json')
    parser.add_argument('--cache-dir',type=Path,default=ROOT/'docs/reports/dfm12_error_composition_cache')
    parser.add_argument('--augment-report',type=Path,help='Preserved additions-only report; avoids rescanning producer corpora')
    parser.add_argument('--inherited-root',type=Path)
    args=parser.parse_args()
    if args.augment_report:
        if not args.inherited_root:parser.error('--augment-report requires --inherited-root')
        if args.output.resolve()==args.augment_report.resolve():parser.error('Preserve the input report; choose another output path')
        write_json(args.output,augment_inherited(load(args.augment_report),args.inherited_root))
        print('Augmented',args.output,flush=True);return
    report=make_report()
    for p in (ACTIVE/'build-receipt.json',ACTIVE/'metadata.json',BUILD/'sources.json',Path(__file__)):
        report['evidence'].append(dict(path=str(p),sha256=file_hash(p)))
    # Publish an explicit partial schema immediately; never disguise incomplete languages as zero.
    report['completed_languages']=[]
    for entry in report['languages'].values():entry['status']='pending'
    report['languages']['da'].update(status='unknown_inherited',correction_rows=None,correction_tokens=None,
        pct_all_training_rows=None,pct_all_training_tokens=None,mistake_count_rows={k:None for k in BINS},
        coverage_notes=['Inherited Danish source attribution unavailable; these are unknown, not zero.'])
    for category in report['languages']['da']['categories'].values():
        for key in category:category[key]=None
    write_json(args.output,report)
    print('Indexing sampled additions (read-only)',flush=True)
    starts,lengths=sampled_index();ranges=directory_ranges()
    if len(starts)!=report['denominators']['addition_rows']:
        raise ValueError('Addition sample row count mismatch')
    sources=load(BUILD/'sources.json')
    cache_inputs={str(p):file_hash(p) for p in (Path(__file__),BUILD/'sources.json',
        SAMPLED/'epoch_0/inst_start.npy',SAMPLED/'epoch_0/inst_len.npy',SAMPLED/'epoch_0/resp_len.npy')}
    report['evidence'].extend(dict(path=p,sha256=h) for p,h in cache_inputs.items())
    for lang in LANGUAGES:
        if lang=='da':continue
        code=lang.replace('_','-')
        names=[s['name'] for s in sources if s['name'] in (f'dfm12-dala-{code}-correction',f'dfm12-dala-{code}')]
        metadata_path=producer_path(lang);stats=report['languages'][lang]
        if not names or not metadata_path.exists():
            stats.update(status='missing_source',coverage_notes=['No precise producer/accepted source inventory found.'])
            continue
        metadata_hash=file_hash(metadata_path)
        cache_path=args.cache_dir/(lang+'.json')
        if cache_path.exists():
            cached=load(cache_path)
            if (cached['inputs']==cache_inputs and cached['evidence']['sha256']==metadata_hash
                    and all(file_hash(c['file'])==c['sha256'] for c in cached['components'])):
                report['languages'][lang]=cached['result'];report['components'].extend(cached['components'])
                report['evidence'].append(cached['evidence']);report['completed_languages'].append(lang)
                write_json(args.output,report);print('Cached',lang,flush=True);continue
        print('Scanning',lang,str(metadata_path),flush=True)
        lookup,pair_count=load_annotations(metadata_path)
        rules=set();edit_pairs=set();types=Counter();component_records=[]
        category_rules={c:set() for c in CATEGORIES};category_pairs={c:set() for c in CATEGORIES}
        for directory,lo,hi in ranges:
            name,sep,filename=directory.name.partition('__')
            if name not in names:continue
            path=BUILD/'accepted_inputs'/name/filename
            if not path.exists():raise ValueError('Accepted input missing: '+str(path))
            left,right=np.searchsorted(starts,[lo,hi])
            sampled_starts=starts[left:right]-lo
            original_starts=np.load(directory/'inst_start.npy',mmap_mode='r')
            index=np.searchsorted(original_starts,sampled_starts)
            if len(index) and (index.max()>=len(original_starts) or not np.array_equal(original_starts[index],sampled_starts)):
                raise ValueError('Sampled row does not match original tokenized boundary')
            weights=np.bincount(index,minlength=len(original_starts))
            token_weights=np.bincount(index,weights=lengths[left:right],minlength=len(original_starts)).astype(np.uint64)
            rows_read=0;before=stats['correction_rows']
            for ordinal,row in enumerate(lines(path)):
                rows_read+=1
                if ordinal>=len(weights):raise ValueError('Tokenizer/export row alignment lost')
                if row.get('task')!='correction' or not weights[ordinal]:continue
                messages=row['messages'];text=messages[0]['content'].partition('\n\n')[2]
                target=messages[-1]['content']
                edits=lookup.get(pair_key(target,text))
                add_row(stats,edits,weights[ordinal],token_weights[ordinal],rules,edit_pairs,types,category_rules,category_pairs)
            if rows_read!=len(original_starts):raise ValueError('Tokenizer skipped source rows; ordinal join is unsafe')
            component_records.append(dict(component=name,file=str(path),sha256=file_hash(path),
                accepted_rows=rows_read,sampled_correction_rows=stats['correction_rows']-before))
        stats.update(status='complete_identified_additions',distinct_rule_ids=len(rules),distinct_edit_pairs=len(edit_pairs),
            distinct_counts_are_lower_bounds=bool(stats['mistake_count_rows']['unknown']),
            rule_ids=sorted(rules),corruption_type_edit_occurrences=dict(sorted(types.items())),
            pct_all_training_rows=100*stats['correction_rows']/report['denominators']['sampled_rows'],
            pct_all_training_tokens=100*stats['correction_tokens']/report['denominators']['sampled_tokens'])
        stats['mistake_count_pct_within_correction']={k:100*v/stats['correction_rows'] if stats['correction_rows'] else None for k,v in stats['mistake_count_rows'].items()}
        for category in CATEGORIES:
            value=stats['categories'][category]
            value.update(pct_all_training_rows=100*value['rows']/report['denominators']['sampled_rows'],
                pct_all_training_tokens=100*value['tokens']/report['denominators']['sampled_tokens'],
                pct_within_correction_rows=100*value['rows']/stats['correction_rows'] if stats['correction_rows'] else None,
                distinct_rule_ids=len(category_rules[category]),distinct_edit_pairs=len(category_pairs[category]),
                rule_ids=sorted(category_rules[category]))
        stats['coverage_notes']=['Inherited correction exposure remains unassigned; reported exposure is an identified lower bound.',
            'Distinct counts refer only to sampled correction rows with unambiguous producer annotations.']
        assert sum(stats['mistake_count_rows'].values())==stats['correction_rows']
        report['components'].extend(component_records)
        evidence=dict(path=str(metadata_path),sha256=metadata_hash,producer_train_pairs=pair_count)
        report['evidence'].append(evidence)
        write_json(cache_path,dict(inputs=cache_inputs,result=stats,components=component_records,evidence=evidence))
        report['completed_languages'].append(lang)
        write_json(args.output,report)
        print(lang,stats['correction_rows'],stats['mistake_count_rows'],flush=True)
        del lookup
    report['status']='complete_with_explicit_missing_inherited_coverage'
    report['identified_correction_rows']=sum(v['correction_rows'] or 0 for v in report['languages'].values())
    report['identified_correction_tokens']=sum(v['correction_tokens'] or 0 for v in report['languages'].values())
    write_json(args.output,report)
    print('Complete',args.output,flush=True)


if __name__=='__main__':main()
