"""CPU-only punctuation correction; never modifies frozen Search receipts."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from markdown_it import MarkdownIt
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_followup as followup


def check_citations(answer, pages):
    citations = []
    def visit(tokens):
        for token in tokens:
            if token.type in ('link_open', 'image'):
                citations.append(token.attrGet('href' if token.type == 'link_open' else 'src') or '')
            elif token.type in ('html_inline', 'html_block'):
                raise ValueError('HTML citations unsupported; use Markdown links')
            elif token.type in ('text', 'code_inline', 'code_block', 'fence'):
                for match in re.finditer(r'https?://[^\s<>"`]+', token.content):
                    url = match.group().rstrip('.,;!。。，；！')
                    # Strip unmatched prose delimiters, never arbitrary URL suffixes.
                    while url and ((url.endswith(')') and url.count(')') > url.count('(')) or
                                   (url.endswith(']') and url.count(']') > url.count('['))):
                        url = url[:-1].rstrip('.,;!。。，；！')
                    citations.append(url)
            if token.children:
                visit(token.children)
    visit(MarkdownIt('commonmark').parse(answer))
    if not citations:
        raise ValueError('final_without_opened_page_citation')
    opened = {urlsplit(base.public_url(url)) for url in pages}
    for url in citations:
        if urlsplit(base.public_url(url)) not in opened:
            raise ValueError('citation URL does not exactly match a retrieved page: '+url)
    return citations


def rescore(review, pages, answer):
    # Keep the original schema, source-membership and unsupported-claim checks.
    # Supply canonical links only after independently validating the real answer.
    citations = check_citations(answer, pages) if review.get('verdict') == 'keep' else []
    canonical = '\n'.join('<'+url+'>' for url in citations)
    return followup.semantic_review(review, pages, canonical)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('new output required')
    jobs = {j['id']: j for j in json.loads((args.source/'jobs.json').read_text())}
    rows = []
    pins = {}
    for path in sorted((args.source/'records').glob('*/outcome.json')):
        outcome = json.loads(path.read_text())
        row = dict(id=path.parent.name, before=outcome.get('verdict', 'error'),
                   after=outcome.get('verdict', 'error'), changed=False)
        pins[str(path.resolve())] = base.file_hash(path)
        review_path = path.parent/'review.json'
        if review_path.exists():
            review = json.loads(review_path.read_text())
            if 'original_review' in review and review['original_review'].get('verdict') == 'keep':
                candidate_path = path.parent/'candidate.json'
                for p in (review_path, candidate_path):
                    pins[str(p.resolve())] = base.file_hash(p)
                answer = json.loads(candidate_path.read_text())['messages'][-1]['content']
                try:
                    rescore(review['original_review'], jobs[row['id']]['pages'], answer)
                    row.update(after='keep', changed=True, prior_reason=review['reason'])
                except ValueError as error:
                    row['remaining_blocker'] = str(error)
        rows.append(row)
    for p in (args.source/'jobs.json', Path(__file__), Path(base.__file__), Path(followup.__file__)):
        pins[str(p.resolve())] = base.file_hash(p)
    report = dict(rows=rows, counts=dict(Counter(r['after'] for r in rows)),
                  restored=sum(r['changed'] for r in rows), pins=pins, paid_calls=0,
                  model_calls=0, admission_authorized=False)
    base.atomic(args.output/'receipt.json', report)
    print(json.dumps({k:v for k,v in report.items() if k not in ('rows','pins')}))


if __name__ == '__main__':
    main()
