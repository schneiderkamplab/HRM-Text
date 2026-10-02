"""Apply the conservative 2026-09-24 source review, not blanket ELRC approval."""
from pathlib import Path
import urllib.request
import yaml

from .io import load, lock, write_json, digest

APPROVED = {
    ('ELRC-2707-EMEA', 'v1'): 'cc-by-4.0',
    ('ELRC-2725-EMEA', 'v1'): 'cc-by-4.0',
    ('ELRC-401-Swedish_Labour_Part2', 'v1'): 'public-domain',
    ('ELRC-406-Swedish_Labour_Part1', 'v1'): 'public-domain',
    ('ELRC-403-Rights_Arrested', 'v1'): 'cc-by-4.0',
    ('ELRC-518-www.regjeringen.no', 'v1'): 'cc-by-4.0',
    ('ELRC-84-Dutch_Government', 'v1'): 'cc0-1.0',
}
MINED = {'ParaCrawl', 'MultiParaCrawl', 'CCMatrix', 'CCAligned', 'MultiCCAligned',
         'NLLB', 'WikiMatrix', 'HPLT', 'MultiHPLT', 'XLEnt', 'wikimedia', 'Wikipedia'}
LOW_PRIORITY = {'Ubuntu', 'GNOME', 'KDE4', 'KDEdoc', 'PHP', 'translatewiki',
                'tldr-pages', 'LinguaTools-WikiTitles', 'OpenSubtitles', 'bible-uedin', 'Tanzil'}


def main():
    root = Path('data/dfm12/opus')
    # Do not mutate the inventory behind an active preparation campaign.
    with lock(root.parent / '.cpu-translations.lock'), lock(root / '.inventory.lock'):
        inventory = load(root / 'inventory.json')
        original = digest(inventory)
        write_json(root / ('inventory-before-review-' + original[:12] + '.json'), inventory)
        decisions = []
        for pair, item in inventory['pairs'].items():
            for entry in item['corpora']:
                name, version = entry['corpus'], entry['version']
                key = name, version
                if key in APPROVED:
                    evidence = load(root / 'review_evidence' / name / version / 'info.json')
                    observed = evidence['metadata']['license'].lower()
                    expected = APPROVED[key]
                    if observed.replace('publicdomain', 'public-domain') != expected:
                        raise ValueError(f'License evidence changed: {key}')
                    parent_url = f"https://raw.githubusercontent.com/Helsinki-NLP/OPUS/{evidence['revision']}/corpus/{name}/info.yaml"
                    with urllib.request.urlopen(parent_url, timeout=30) as response:
                        parent = yaml.safe_load(response.read())
                    write_json(root / 'review_evidence' / name / version / 'parent.json',
                               {'url': parent_url, 'metadata': parent})
                    entry.update(status='approved', license=expected, license_evidence=evidence['url'],
                                 quality_review='Named institutional translation corpus; candidate preparation only. Audit alignment, language variant, PDF artifacts and usefulness.',
                                 source_description=parent.get('description'), review_date='2026-09-24')
                elif name in MINED:
                    entry.update(status='excluded_quality', review_reason='Avoid web/encyclopedia-mined alignments; no volume-driven backfill.')
                elif name in LOW_PRIORITY:
                    entry.update(status='excluded_quality', review_reason='Software fragments, titles, subtitles or narrow religious text not selected for this prose translation mix.')
                elif name != 'Tatoeba':
                    entry.update(status='license_review', review_reason='No blanket approval: verify content rights, provenance, alignment quality and benchmark overlap.')
                    if name == 'ELRC-EMEA':
                        entry['review_reason'] = 'Conflicting parent BY-NC versus release BY metadata; use reviewed numbered releases only.'
                decisions.append({'pair': pair, 'corpus': name, 'version': version,
                                  'status': entry['status'], 'license': entry.get('license'),
                                  'reason': entry.get('review_reason', entry.get('quality_review', 'Existing Tatoeba approval'))})
        write_json(root / 'inventory.json', inventory)
        write_json(root / 'review-decisions.json', decisions)
        from collections import Counter
        print(Counter(d['status'] for d in decisions))


if __name__ == '__main__':
    main()
