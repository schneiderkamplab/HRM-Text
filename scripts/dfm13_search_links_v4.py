"""Parse evidence links without treating display labels or code examples as citations."""
import re
from urllib.parse import quote, urlsplit, urlunsplit
from markdown_it import MarkdownIt
from scripts import dfm13_search_calibration as base


def equivalent(url):
    p=urlsplit(base.public_url(url))
    def norm(text):
        text=quote(text,safe="/%:@!$&'()*+,;=-._~[]?")
        return re.sub(r'%([0-9a-fA-F]{2})',lambda m: chr(int(m[1],16))
            if chr(int(m[1],16)) in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'
            else '%'+m[1].upper(),text)
    host=p.netloc.lower()
    if (p.scheme=='https' and host.endswith(':443')) or (p.scheme=='http' and host.endswith(':80')):
        host=host.rsplit(':',1)[0]
    return urlunsplit((p.scheme,host,norm(p.path or '/'),norm(p.query),''))


def extract(answer):
    links=[]; illustrative=[]
    def scan(text):
        for match in re.finditer(r'https?://[^\s<>"`]+',text):
            url=match.group().rstrip('.,;!。。，；！')
            while ((url.endswith(']') and url.count(']')>url.count('[')) or
                   (url.endswith(')') and url.count(')')>url.count('('))):
                url=url[:-1].rstrip('.,;!。。，；！')
            yield url
    def visit(tokens):
        depth=0
        for token in tokens:
            if token.type=='link_open':
                links.append(token.attrGet('href'));depth+=1
            elif token.type=='link_close':
                depth-=1
            elif token.type=='image':
                links.append(token.attrGet('src'))
            elif token.type in ('html_inline','html_block'):
                raise ValueError('HTML links unsupported')
            elif token.type in ('fence','code_block'):
                illustrative.extend(scan(token.content))
            elif token.type in ('text','code_inline') and not depth:
                links.extend(scan(token.content))
            if token.children and token.type!='image':
                visit(token.children)
    visit(MarkdownIt('commonmark').parse(answer))
    return dict(links=links,illustrative_code_urls=illustrative)


def check(answer,pages,supporting_urls):
    result=extract(answer)
    known={equivalent(u):u for u in pages}
    supporting={equivalent(u) for u in supporting_urls}
    if not supporting or not supporting.issubset(known):
        raise ValueError('review cites unobserved source or lacks support')
    links={equivalent(u) for u in result['links']}
    unknown=links-set(known)
    if unknown:
        raise ValueError('unclassified unobserved hyperlink: '+sorted(unknown)[0])
    if not links.intersection(supporting):
        raise ValueError('no answer citation to supporting observed page')
    return result


def main():
    import argparse
    import json
    from pathlib import Path
    from collections import Counter
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,default=Path('data/dfm13/search-reviewer-v3-20261001'))
    parser.add_argument('--output',type=Path,default=Path('data/dfm13/search-links-v4-20261001'))
    args=parser.parse_args()
    if args.output.exists(): raise ValueError('new output required')
    rows=[]
    jobs=json.loads((args.source/'jobs.json').read_text())
    for job in jobs:
        folder=args.source/'records'/job['id']; path=folder/'review.json'
        if not path.exists():
            rows.append(dict(id=job['id'],status='review_error'));continue
        review=json.loads(path.read_text()); raw=review.get('original_review',review)
        if raw.get('findings') or raw.get('unsupported_claims'):
            rows.append(dict(id=job['id'],status='semantic_findings_remain'));continue
        try:
            parsed=check(job['answer'],job['pages'],raw['supporting_urls'])
            rows.append(dict(id=job['id'],status='mechanically_clear_not_certified',previous=review['verdict'],parsed=parsed))
        except ValueError as error:
            rows.append(dict(id=job['id'],status='held',reason=str(error)))
    result=dict(rows=rows,counts=dict(Counter(r['status'] for r in rows)),
        newly_mechanically_clear=[r['id'] for r in rows if r['status']=='mechanically_clear_not_certified' and r['previous']!='keep'],
        admission_authorized=False,model_calls=0,paid_calls=0,
        pins={str(p.resolve()):base.file_hash(p) for p in [Path(__file__),args.source/'jobs.json',*sorted((args.source/'records').glob('*/review.json'))]})
    base.atomic(args.output/'receipt.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ('rows','pins')}))


if __name__=='__main__':main()
