"""Conservative English QA prefilter for a quarantined experiment, not admission."""
import re
from pathlib import Path
from scripts import dfm13_repochat_calibration as b

EXCLUDE = re.compile(r'\b(implement|implementation|write|create|convert|refactor|fix|patch|modify|change|migrat\w*|build|integrate|integration|integrating|preserv\w*|all|every|complete\w*|exhaustive|unsupported|coverage|vulnerab\w*|exploit\w*)\b', re.I)
NAVIGATION = re.compile(r'\b(where|which file|what file|which director\w*|what director\w*|locate|find the file)\b', re.I)
OVERVIEW = re.compile(r'\b(what (?:is|does) (?:this |the )?(?:repo\w*|project)|(?:explain|describe|summari[sz]e) (?:this |the )?(?:repo\w*|project)|what is (?:this|it) about)\b', re.I)


def category(query):
    if EXCLUDE.search(query):
        return None
    if NAVIGATION.search(query):
        return 'bounded_navigation_candidate'
    if OVERVIEW.search(query):
        return 'repository_overview_candidate'
    return None


def main():
    source = Path('data/downloads/arena_review/repochat-arena-preference-4k/repochat_battles.json')
    root = Path('data/dfm13/repochat-simple-qa-inventory-20261001')
    rows = b.load(source)
    _, inventory = b.select(rows, 1)
    tasks, _ = b.select(rows, inventory['eligible'])
    used = {t['id'] for t in b.load('data/dfm13/repochat-calibration-100-20261001-v3/selection.json')['tasks']}
    candidates = [dict(t, candidate_scope=category(t['query'])) for t in tasks if t['id'] not in used and not b.task_exclusion(t) and category(t['query'])]
    from collections import Counter
    b.save(root / 'inventory.json', {'source': str(source), 'source_sha256': b.file_sha(source), 'implementation_sha256': b.file_sha(__file__), 'candidates': candidates, 'counts': dict(Counter(t['candidate_scope'] for t in candidates)), 'count': len(candidates), 'proposed_next_count': min(100, len(candidates)), 'qualification': 'English lexical prefilter only. Requires task review, pinned snapshot availability, native retrieval, scoped claims and independent assessment. Not a quality or safety classifier.', 'launch_authorized_by_this_receipt': False, 'admission': False})
    print({'root': str(root), 'count': len(candidates), 'counts': dict(Counter(t['candidate_scope'] for t in candidates))})


if __name__ == '__main__':
    main()
