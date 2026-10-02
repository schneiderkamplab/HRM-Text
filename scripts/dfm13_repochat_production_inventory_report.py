"""Additive planning report; no snapshots, inference, or admission."""
from collections import Counter
from pathlib import Path
from scripts import dfm13_repochat_calibration as b

ROOT = Path('data/dfm13/repochat-production-inventory-20261001-v1')
# Prompt-only manual inspection, not source validation or semantic acceptance.
MANUAL_PREFIXES = '''3e67fe7ac0 78ddffa9ed 59f4d3d571 81c5762da4 ae4288727d
6182f6372f 23c12e6d91 987c013128 6e19507d0c 02533e8f71 877835c7ba
58dd8022a0 e77fd200e5 329dc6f7a2 4cb4eaa70f 18bb2b0de9 268b45ec1c
cb8fe9b12d 3a54d3f71f 9082742e3a 04766e2d24 5035d94de1 d789a5389b'''.split()


def report(root=ROOT):
    inventory = b.load(root / 'inventory.json')
    summary = b.load(root / 'summary.json')
    availability = b.load(root / 'availability.json')
    for name in ('inventory', 'availability'):
        if summary[name + '_sha256'] != b.file_sha(root / (name + '.json')):
            raise ValueError('inventory report input drift')
    tasks = [t for t in inventory['tasks'] if not t['previously_inventoried']]
    manual = []
    for prefix in MANUAL_PREFIXES:
        matches = [t for t in tasks if t['id'].startswith(prefix)]
        if len(matches) != 1:
            raise ValueError('manual prefix is not unique')
        t = matches[0]
        manual.append(dict(t, public_metadata=availability[t['repository']],
                           scope_disposition='descriptive_qa_source_preflight_required',
                           admission=False))
    priority = [t for t in manual if t['public_metadata']['status'] == 'public_head_available']
    extra = [t for t in priority if not t['scope'].startswith('qa_')]
    result = dict(input_summary_sha256=b.file_sha(root / 'summary.json'), implementation_sha256=b.file_sha(__file__),
                  manually_screened_qa=len(manual), public_manually_screened_qa=len(priority),
                  additional_nonlexical_public_qa=len(extra), manually_screened_tasks=manual,
                  prospective_public_qa_pool=summary['qa_public_head_candidates'] + len(extra),
                  production_estimate={'candidate_planning_range': [100, 200], 'confidence': 'low',
                                       'basis': 'Heuristic scheduling allowance within the accessible QA shortlist, not a statistical yield estimate. Full source and scope checks remain. Usage/manual backlog may expand capacity.',
                                       'accepted_conversations': None},
                  preparation_plan={'distinct_repository_workers': 4, 'maximum_workers': 8,
                                    'initial_prompt_screened_batch': len(priority), 'subsequent_batch_max': 100,
                                    'commit_authority': 'availability.json public HEAD commit; never resolve a new HEAD silently',
                                    'repository_single_writer_lock': True,
                                    'compressed_limit_bytes': 128 * 1024**2, 'expanded_limit_bytes': 1024**3,
                                    'per_file_limit_bytes': 1024**2, 'member_limit': 100000,
                                    'download_url': 'https://codeload.github.com/{repository}/tar.gz/{pinned_commit}',
                                    'safety': 'Reuse safe extract/list/search/read only, reject traversal and links, exclude credentials, no code execution; preserve exact failures rather than silently replace tasks.',
                                    'quality_gate': 'Wait for assigned independent three-draft/fresh12 review; inspect scope and source sufficiency, native grounded rollout, independent claim/source verification, manual stratified sampling. Complex code remains held; no automatic admission.'},
                  current_inference_launched=False, snapshots_downloaded_by_inventory=0, admission=False)
    b.save(root / 'production-plan.json', result)
    print({k: v for k, v in result.items() if k not in ('manually_screened_tasks', 'preparation_plan')})


if __name__ == '__main__':
    report()
