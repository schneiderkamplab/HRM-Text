"""Frozen untouched EN/JA campaign preparation; source review precedes generation."""
import argparse
from pathlib import Path
from dfm12.io import rows, load, file_hash, digest, lock, write_json
from scripts.dfm16_story_calibration import immutable, immutable_rows
from scripts.dfm16_staged_experiment import CODE, verify
from scripts.dfm16_staged_validation import freeze, cohort, verify_freeze

BASE=Path('data/dfm16/staged-stories-v3-20261029')
PRECISION=Path('data/dfm16/staged-stories-precision-v4-20261029')
ROOT=Path('data/dfm16/staged-stories-validation-v7-20261029')
REPOS={'en':'SimpleStories/SimpleStories','ja':'SimpleStories/SimpleStories-JA'}
SEEDS={'en':202610290601,'ja':202610290602}


def initialize(root):
    verify(BASE)
    software={p:file_hash(Path(p)) for p in (*CODE,'scripts/dfm16_staged_precision.py',__file__)}
    protocol=dict(languages=['en','ja'],generator='odin',reviewers=['flash','qwen27b'],policy='both',
        english_checks='base plus all paragraph/precondition checks, conjunctive per reviewer',
        japanese_checks='base',software=software,seeds=SEEDS,
        supplementary_seeds={k:v+100 for k,v in SEEDS.items()},
        population='Pinned original target-language training stories with 180–900 Unicode code points, excluding all historical source pools and inspected families.',
        source_review='Read complete source; retain original text; manually validate facts, QA slots, topic and rewrite preconditions before generation. No guessed repairs. Unusable source remains unresolved in sampled cohort; no replacement.',
        templates=str(BASE/'templates/native-requests.json'),
        supplementary='One additional balanced 800 cohort per language only if blinded initial class counts have fewer than 300 clear or 100 definite defects. Trigger before judging; never repeat.',
        sample_per_language=800,per_task=160,manual_reference='provisional assistant-manual',
        labels_before_votes=True,first_and_corrected_separate=True,
        false_acceptance_upper95_lt=.05,clean_withholding_upper95_le=.20,
        production_authorized=False,requested_capacity_split='4 generation / 4 auditing; existing servers unchanged; no throughput claim')
    immutable(root/'protocol.json',protocol)
    screen=load(BASE/'decisions/generator-screen.json')
    selection=load(BASE/'decisions/policy-selection.json')
    for language in REPOS:
        artifacts=[BASE/'design.json',BASE/'sources/reviewed.jsonl',BASE/'labels/manual-labels.jsonl',
            BASE/'sources/controls.jsonl',BASE/'votes/votes.jsonl',BASE/'sources/excluded-families.jsonl',
            BASE/'sources/inspected-candidate-inventory.jsonl',BASE/'sources/source-process.json',
            root/'protocol.json',Path('scripts/dfm16_staged_precision.py'),Path(__file__)]
        if language=='en':
            evidence=load(PRECISION/'report.json')['languages']['en']['precision_both']
            policy_report=dict(policy='both',reports={'both':evidence},evidence=str(PRECISION/'report.json'))
            artifacts += [PRECISION/'report.json',PRECISION/'scored.jsonl',PRECISION/'checks.jsonl']
        else:
            policy_report=selection['languages'][language] if 'languages' in selection else selection[language]
        immutable(root/language/'development-policy.json',policy_report)
        artifacts.append(root/language/'development-policy.json')
        freeze(root,language,'odin','both',artifacts,screen,policy_report)


def draw(root,language):
    verify_freeze(root,language)
    protocol=load(root/'protocol.json')
    for path,expected in protocol['software'].items():
        if file_hash(Path(path))!=expected:raise ValueError('changed frozen software')
    directory=Path('data/dfm16/expansion-v1/downloads')/REPOS[language].replace('/','__')
    snapshot=directory/'snapshot'
    revision=load(directory/'source.json')['revision']
    pool=[];pins={}
    for path in sorted(snapshot.rglob('*.parquet')):
        if 'train' not in str(path):continue
        pins[str(path)]=file_hash(path)
        for i,row in enumerate(rows(path)):
            text=row.get('story','')
            if not 180<=len(text)<=900:continue
            pool.append(dict(family=digest(text),language=language,text=text,
                provenance=dict(repo_id=REPOS[language],revision=revision,file=str(path.relative_to(snapshot)),row=i)))
    immutable(root/language/'source-pool-receipt.json',dict(files=pins,eligible_before_exclusion=len(pool),revision=revision))
    selected=cohort(root,language,pool,set(),SEEDS[language])
    write_json(root/language/'status.json',dict(phase='sampled_awaiting_source_review',sampled=len(selected),sources_reviewed=0,generated=0,judged=0,qualified=False))
    return len(selected)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['freeze','draw']);parser.add_argument('--root',type=Path,default=ROOT)
    args=parser.parse_args()
    with lock(args.root/'.controller.lock'):
        if args.action=='freeze':initialize(args.root)
        else:
            for language in REPOS:print(language,draw(args.root,language),flush=True)
