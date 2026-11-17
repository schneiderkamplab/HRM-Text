"""Conservative immutable source-family exclusion inventory and source receipts."""
from pathlib import Path
from dfm12.io import file_hash,rows,load
from scripts.dfm16_story_calibration import immutable,immutable_rows,sha


def inventory(root,pools):
    """Exclude entire prior seed pools, even rows never inspected or generated.

    This over-excludes deliberately. All earlier SimpleStories experiments in
    this repository derive from these pinned pools. Additional evidence files
    must be supplied when that provenance assumption changes.
    """
    families=set()
    pins={}
    for path in pools:
        pins[str(path)]=file_hash(path)
        for r in rows(path):
            family=r.get('family') or r.get('provenance',{}).get('source_family')
            if not family:raise ValueError('family missing in exclusion input')
            families.add(family)
    immutable_rows(root/'sources/excluded-families.jsonl',[dict(family=f) for f in sorted(families)])
    immutable(root/'sources/exclusion-receipt.json',dict(inputs=pins,families=len(families),
        family_file_sha256=file_hash(root/'sources/excluded-families.jsonl'),
        policy='Conservatively exclude all historical source pools plus all supplied inspected/development inventories.'))
    return families


def verify_novelty(root,sources):
    receipt=load(root/'sources/exclusion-receipt.json')
    for path,digest in receipt['inputs'].items():
        if file_hash(Path(path))!=digest:raise ValueError('exclusion evidence changed')
    path=root/'sources/excluded-families.jsonl'
    if file_hash(path)!=receipt['family_file_sha256']:raise ValueError('exclusion inventory changed')
    excluded={r['family'] for r in rows(path)}
    if any(s['family'] in excluded for s in sources):raise ValueError('previously used source family')
    return sha(receipt)
