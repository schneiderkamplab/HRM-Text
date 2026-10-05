"""Explicit final W4 top-up quotas; no mutations of an active campaign."""
from collections import defaultdict

VERSION = 'wave4-final-topup-v1'
TARGET = 735000


def plan(groups, recoveries=None):
    """Allocate LB's remaining 35K budget above immutable accepted floors.

    Attempt limits refer to original family targets, never the new deficit or
    attempts already expended. Completed groups receive no increased budget.
    """
    languages = defaultdict(list)
    seen = set()
    for source in groups:
        row = dict(source)
        key = row['language'], row['family']
        if key in seen:
            raise ValueError('Duplicate group')
        seen.add(key)
        if row['active'] or min(row['accepted'], row['attempts'], row['target']) < 0:
            raise ValueError('Require drained, nonnegative counters')
        original = row.get('original_target', row['target'])
        if type(original) is not int or original <= 0 or row['accepted'] > original:
            raise ValueError('Invalid original target or acceptance floor')
        row['original_target'] = original
        languages[row['language']].append(row)
    if len(languages) != 11 or 'lb' not in languages or len(seen) != 66:
        raise ValueError('Expected all eleven languages and six families')
    result = []
    for language, rows in sorted(languages.items()):
        rows.sort(key=lambda r: r['family'])
        if sum(r['original_target'] for r in rows) != 70000:
            raise ValueError('Original language quota must be 70000')
        total = 35000 if language == 'lb' else 70000
        floors = sum(r['accepted'] for r in rows)
        if floors > total:
            raise ValueError('Accepted floor exceeds language target; never discard accepts')
        if language == 'lb':
            # Water-fill toward half quotas, freezing any family above its share.
            targets = {r['family']: r['accepted'] for r in rows}
            remaining = total - floors
            while remaining:
                eligible = [r for r in rows if targets[r['family']] < r['original_target']]
                if not eligible:
                    raise ValueError('Cannot allocate language target')
                if recoveries is not None:
                    covered = [r for r in eligible if targets[r['family']] <
                        r['accepted'] + recoveries.get((language,r['family']),0)]
                    if covered:
                        eligible = covered
                chosen = min(eligible, key=lambda r: (
                    targets[r['family']] / r['original_target'], r['family']))
                targets[chosen['family']] += 1
                remaining -= 1
        else:
            targets = {r['family']: r['original_target'] for r in rows}
        for row in rows:
            row['target'] = targets[row['family']]
            underfilled = row['accepted'] < row['target']
            row['attempt_limit'] = (12 if underfilled else 6) * row['original_target']
            if row['attempts'] > row['attempt_limit']:
                raise ValueError('Historical attempts exceed authorized ceiling')
            row['accepted_floor'] = row['accepted']
            row['topup_eligible'] = underfilled and row['attempts'] < row['attempt_limit']
            result.append(row)
    if sum(r['target'] for r in result) != TARGET:
        raise ValueError('Target sum mismatch')
    return result
