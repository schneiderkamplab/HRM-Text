"""Freeze the owner-approved Mimir-Decide additions into DFM16's registry."""
import json
from pathlib import Path


SOURCES = {
    'nvidia/Nemotron-RL-knowledge-mcqa': 'knowledge_mcq',
    'nvidia/OpenScienceReasoning-2': 'native_reasoning_qa',
    'Lexmount/WebJev': 'grounded_action_mcq',
    'osunlp/Mind2Web': 'grounded_action_messages',
    'AgentGym/AgentTraj-L': 'native_agent_trajectory',
    'tasksource/nli4ct': 'evidence_entailment',
    'copenlu/fever_gold_evidence': 'evidence_entailment',
    'LocalLLaMA/typed-decisions': 'typed_decision_messages',
    'ZefanCai/Open-Jev': 'typed_decision_messages',
    'ZefanCai/Open-Jev-v1.1': 'typed_decision_messages',
    'bigcode/commitpackft': 'code_edit_messages',
    'emozilla/quality': 'reading_mcq',
    'qiaojin/PubMedQA': 'grounded_scientific_qa',
}


def main():
    upstream = Path('/work/dfm/mimir-decide')
    receipts = json.loads((upstream / 'reports/data-expansion/collection_receipts.json').read_text())
    entries = []
    for repo, conversion in SOURCES.items():
        receipt = next(r for r in receipts if r['repo'] == repo)
        assert receipt['status'] == 'collected', repo
        files = [f for f in receipt['files'] if not (
            repo == 'LocalLLaMA/typed-decisions' and not f['path'].startswith('all/')
            or repo.startswith('ZefanCai/Open-Jev') and f['path'].startswith('raw/')
            or repo == 'qiaojin/PubMedQA' and f['path'].startswith('pqa_unlabeled/'))]
        name = 'dfm16_' + repo.lower().replace('/', '_').replace('-', '_').replace('.', '_')
        local = upstream / 'data/decision-expansion-v1/raw' / repo.replace('/', '__') / receipt['revision']
        assert all((local / f['path']).is_file() for f in files), repo
        entries.append(dict(name=name, repo_id=repo, revision=receipt['revision'],
                            files=files, local_snapshot=str(local), conversion=conversion,
                            owner_approved=True, repeat=1, status='downloaded_conversion_pending',
                            license_reported=receipt.get('license'),
                            source_review_pending=not receipt.get('license_check', [False])[0],
                            split_policy='upstream_train; unsplit CommitPack requires explicit partition',
                            overlap_check_pending=True))
    registry = dict(version=1, approved_on='2026-10-26', sources=entries,
                    local_sources=[dict(name='dfm16_decision_curriculum',
                        path=str(upstream / 'data/decision-expansion-v1/candidate-pool/candidates.jsonl'),
                        families=['policy_exception', 'deadline', 'tool_constraints', 'state_tracking',
                                  'expected_value', 'record_lookup', 'ordinal_rubric', 'evidence_check'],
                        filter='generated-curriculum and train only', repeat=1,
                        owner_approved=True, status='conversion_pending')],
                    format='Gemma 4 native messages',
                    policy=['Do not reimport inherited DFM decision conversions.',
                            'Deduplicate OpenScience and Nemotron MCQA and overlapping aggregate collections.',
                            'No synthetic rationale from a label; preserve native reasoning where available.',
                            'Retain source terms, provenance and held-out boundaries.'])
    Path('config/dfm16_decision_sources.json').write_text(json.dumps(registry, indent=2) + '\n')
    print(f'Registered {len(entries)} HF sources plus eight-family local curriculum.')


if __name__ == '__main__':
    main()
