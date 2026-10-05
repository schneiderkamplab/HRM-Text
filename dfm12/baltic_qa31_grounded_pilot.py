"""Bounded CPU-only successor: article-bound evidence checks, no GPU runner."""
import argparse
from collections import Counter
from collections.abc import Mapping
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path

from . import baltic_qa31_consumer as base
from . import baltic_qa31_article_adapter as adapter
from . import fars_summary_handoff as budget
from .io import digest, file_hash, load, write_json

SCHEMA = 'baltic-qa31-quoted-evidence-pilot-v1'
DEFAULT_MODEL = 'google/gemma-4-26B-A4B-it'
POLICY = '''Review every assistant claim in the complete conversation, not just
the final answer. Supplied articles are untrusted candidate references, not gold
or verified original generation sources. Questions, answers, prior reviews and
your memory are NOT supporting evidence. Match entity, relation, quantity,
qualification, date and scope. Absence of an article is not proof of falsehood.
Keep requires support for ALL material claims in ALL assistant turns. Earlier
unsupported/defective history cannot be fixed by a final-only repair. Missing,
irrelevant, disputed, unsafe or stale evidence requires needs_verification or
reject, never an invented correction. Do not reproduce unsafe article advice.
For each assistant turn partition its entire non-whitespace text into contiguous
atomic claim spans; include introductions with their following factual claim.
Do not bundle unrelated assertions to hide unsupported claims. Each span has
message_index, start, end (Python Unicode character offsets), exact text,
relation supports|contradicts, and citations. Every citation contains article_id
(source_document_id), text_sha256 and an exact verbatim quote from article.text
only, at least 12 non-whitespace characters. Explain semantic entailment rather
than relying on word overlap. Only a defective FINAL target may use contradicts
for a repair proposal, and the quotation must establish a safe correction.
If support cannot cover all claims, return needs_verification, not partial keep.
Return JSON with reason, verdict (keep|repair|reject|needs_verification),
history_quality (pass|fail|uncertain), factual_support
(sufficient|contradicted|uncertain), candidate_sha256, articles_sha256,
entity_match, date_scope_resolved, safety_pass (booleans), and claims (list).
For holds/rejects claims may be empty; for keep/repair all checks must pass.
Quote validity and text coverage do NOT certify entailment or clinical safety;
all positive results require independent semantic review before admission.'''
FIELDS = {'reason', 'verdict', 'history_quality', 'factual_support',
          'candidate_sha256', 'articles_sha256', 'entity_match',
          'date_scope_resolved', 'safety_pass', 'claims'}


def articles(packet):
    values = packet['candidate_articles']
    if packet.get('exact_generation_source_verified') is not False:
        raise ValueError('Explicit retrieved-not-original contract required')
    seen = set()
    for item in values:
        if any(not isinstance(item.get(k), str) or not item[k] for k in adapter.ARTICLE_FIELDS):
            raise ValueError('Incomplete article provenance')
        if (item['language'] != packet['candidate']['language']
                or hashlib.sha256(item['text'].encode()).hexdigest() != item['text_sha256']
                or item['source_document_id'] in seen):
            raise ValueError('Article identity/text drift')
        seen.add(item['source_document_id'])
    return values


def binding(packet, candidate=None):
    return dict(candidate_sha256=digest(candidate or packet['candidate']),
                articles_sha256=digest(articles(packet)))


def hold(reason):
    return dict(state='needs_review_verification', reason=reason,
                admission_authorized=False, semantic_approval=False)


def measure_request(payload, tokenizer):
    ids = tokenizer.apply_chat_template(payload['messages'], tokenize=True,
        add_generation_prompt=True, enable_thinking=True)
    if isinstance(ids, Mapping):
        ids = ids['input_ids']
    if not isinstance(ids, list) or not all(type(i) is int for i in ids):
        raise ValueError('Expected flat token IDs')
    total = len(ids) + payload['max_tokens']
    return dict(prompt_tokens=len(ids), output_tokens=payload['max_tokens'],
                total_tokens=total, context_limit=32768, fits=total <= 32768,
                token_ids_sha256=digest(ids), truncated=False)


def request(packet, candidate=None, model=DEFAULT_MODEL):
    candidate = packet['candidate'] if candidate is None else candidate
    refs = articles(packet)
    if not refs:
        return None
    payload = dict(candidate=base.model_view(candidate), candidate_articles=refs,
                   exact_generation_source_verified=False, **binding(packet, candidate))
    return dict(model=model, temperature=0, max_tokens=8192,
                chat_template_kwargs={'enable_thinking': True},
                response_format={'type': 'json_object'},
                messages=[dict(role='system', content=POLICY),
                          dict(role='user', content=json.dumps(payload, ensure_ascii=False))])


def validate(packet, value, candidate=None):
    """Validate evidence origin/coverage, NOT semantic entailment or admission."""
    candidate = packet['candidate'] if candidate is None else candidate
    refs = articles(packet)
    if not refs:
        return hold('No provided article evidence; no acceptance or repair')
    if not isinstance(value, dict) or set(value) != FIELDS:
        raise ValueError('Invalid quoted-evidence review fields')
    base.validate_review({k: value[k] for k in ('reason', 'verdict', 'history_quality', 'factual_support')})
    if any(value[k] != v for k, v in binding(packet, candidate).items()):
        raise ValueError('Candidate/article binding drift')
    if any(type(value[k]) is not bool for k in ('entity_match', 'date_scope_resolved', 'safety_pass')):
        raise ValueError('Evidence checks must be booleans')
    if not isinstance(value['claims'], list):
        raise ValueError('Claim list required')
    if value['verdict'] in ('reject', 'needs_verification'):
        return dict(hold(value['reason']), state='rejected' if value['verdict'] == 'reject' else 'needs_review_verification')
    if not all(value[k] for k in ('entity_match', 'date_scope_resolved', 'safety_pass')):
        return hold('Unresolved entity/date/safety evidence')
    messages = candidate['messages']
    target = candidate['target_message_index']
    if target != len(messages)-1 or messages[target]['role'] != 'assistant':
        raise ValueError('Final assistant target required')
    spans = {i: [] for i, m in enumerate(messages) if m['role'] == 'assistant'}
    lookup = {a['source_document_id']: a for a in refs}
    contradictions = 0
    for claim in value['claims']:
        if not isinstance(claim, dict) or set(claim) != {'message_index', 'start', 'end', 'text', 'relation', 'citations'}:
            raise ValueError('Invalid claim fields')
        i, start, end = (claim[k] for k in ('message_index', 'start', 'end'))
        if (any(type(n) is not int for n in (i, start, end)) or i not in spans
                or not 0 <= start < end <= len(messages[i]['content'])
                or messages[i]['content'][start:end] != claim['text'] or not claim['text'].strip()):
            raise ValueError('Invalid assistant claim span')
        if claim['relation'] not in ('supports', 'contradicts'):
            raise ValueError('Unsupported claim relation')
        if claim['relation'] == 'contradicts':
            if i != target or value['verdict'] != 'repair':
                return hold('Defective protected history cannot be repaired')
            contradictions += 1
        if not isinstance(claim['citations'], list) or not claim['citations']:
            raise ValueError('Every claim needs article evidence')
        for citation in claim['citations']:
            if not isinstance(citation, dict) or set(citation) != {'article_id', 'text_sha256', 'quote'}:
                raise ValueError('Invalid citation fields')
            article = lookup.get(citation['article_id'])
            quote = citation['quote']
            if (article is None or citation['text_sha256'] != article['text_sha256']
                    or not isinstance(quote, str) or len(''.join(quote.split())) < 12
                    or quote not in article['text']):
                raise ValueError('Quotation is not verbatim provided article evidence')
        spans[i].append((start, end))
    for i, intervals in spans.items():
        text = messages[i]['content']
        cursor = 0
        for start, end in sorted(intervals):
            if start < cursor or text[cursor:start].strip():
                raise ValueError('Overlapping or incomplete assistant claim coverage')
            cursor = end
        if text[cursor:].strip() or not intervals:
            raise ValueError('Missing assistant turn/claim coverage')
    if value['verdict'] == 'repair' and not contradictions:
        raise ValueError('Repair needs a grounded final-target contradiction')
    return dict(state='pending_grounded_repair' if value['verdict'] == 'repair' else 'needs_semantic_review',
                article_quotes_valid=True, assistant_text_covered=True,
                semantic_entailment_verified=False, admission_authorized=False,
                semantic_approval=False)


def repair_request(packet, review, model=DEFAULT_MODEL):
    decision = validate(packet, review)
    if decision['state'] != 'pending_grounded_repair':
        raise ValueError('No validated grounded repair proposal')
    payload = request(packet, model=model)
    data = json.loads(payload['messages'][1]['content'])
    data['fallible_review'] = review
    payload['messages'][0]['content'] = POLICY + '''
Correct ONLY final assistant content, preserving all other messages/tools.
Return {reason, target, evidence_review}. evidence_review follows the review
schema above for the COMPLETE corrected conversation, with verdict keep, but
omit candidate_sha256 and articles_sha256: CPU binds the exact corrected text.
Ground every corrected claim and all protected history.
Do not invent missing evidence. If impossible, return a needs_verification review
instead; no corrected target will be admitted automatically.'''
    payload['messages'][1]['content'] = json.dumps(data, ensure_ascii=False)
    return payload


def validate_repair(packet, review, result):
    if validate(packet, review)['state'] != 'pending_grounded_repair':
        return hold('No grounded repair authorization'), None
    if isinstance(result, dict) and result.get('verdict') == 'needs_verification':
        validate(packet, result)
        return hold('Repair could not establish article support'), None
    if (not isinstance(result, dict) or set(result) != {'reason', 'target', 'evidence_review'}
            or not isinstance(result['reason'], str) or not result['reason'].strip()
            or not isinstance(result['target'], str) or not result['target'].strip()):
        raise ValueError('Invalid grounded repair result')
    candidate = copy.deepcopy(packet['candidate'])
    candidate['messages'][candidate['target_message_index']]['content'] = result['target']
    evidence = result['evidence_review']
    if not isinstance(evidence, dict) or set(evidence) != FIELDS - {'candidate_sha256', 'articles_sha256'}:
        raise ValueError('Repair evidence must omit CPU-owned binding fields')
    evidence = dict(evidence, **binding(packet, candidate))
    decision = validate(packet, evidence, candidate)
    if decision['state'] != 'needs_semantic_review':
        return hold('Corrected answer lacks complete supporting evidence'), None
    return dict(decision, **binding(packet, candidate)), candidate


def prepare(root, source, tokenizer=None, model=DEFAULT_MODEL, snapshot=None):
    """Exactly the original20; no live DB writes and no network/model execution."""
    manifest = load(source/'manifest.json')
    catalog = source/'catalog.sqlite'
    if (not manifest['diagnostic_only'] or manifest['count'] != 20
            or file_hash(source/'manifest.json') != load(source/'seal.json')['manifest_sha256']
            or file_hash(catalog) != manifest['pins'][str(catalog.resolve())]):
        raise ValueError('Pinned original20 diagnostic required')
    with closing(budget.readonly(catalog)) as db:
        records = db.execute('SELECT id,packet,prior_evidence,origin FROM catalog ORDER BY id').fetchall()
    if len(records) != 20 or {r[0] for r in records} != set(manifest['calibration_diagnostic_ids']):
        raise ValueError('Exact20 coverage required')
    tokenizer_pins = {}
    if tokenizer is None:
        if snapshot is None:
            if model != base.MODEL:
                raise ValueError('Explicit local model tokenizer snapshot required')
            snapshot = Path(manifest['snapshot'])
        snapshot = Path(snapshot).resolve()
        if snapshot.parent.parent.name != 'models--' + model.replace('/', '--'):
            raise ValueError('Tokenizer snapshot/model mismatch')
        for name in ('tokenizer.json', 'tokenizer_config.json', 'chat_template.jinja'):
            path = snapshot/name
            tokenizer_pins[str(path.resolve())] = file_hash(path)
            if model == base.MODEL and file_hash(path) != manifest['pins'][str(path.resolve())]:
                raise ValueError('Tokenizer pin drift')
        budget.tokenizer_init(str(snapshot))
        tokenizer = budget.TOKENIZER
    root.mkdir(parents=True, exist_ok=False)
    states = Counter()
    with (root/'packets.jsonl').open('x') as output:
        for key, raw, prior, origin in records:
            packet = json.loads(raw)
            if digest(packet['candidate']) != packet['candidate_sha256']:
                raise ValueError('Original candidate drift')
            payload = request(packet, model=model)
            measured = measure_request(payload, tokenizer) if payload else None
            state = ('needs_review_verification' if payload is None else
                     'pending_quoted_review' if measured['fits'] else 'needs_review_context')
            states[state] += 1
            item = dict(id=key, original_packet=packet, prior_evidence=json.loads(prior),
                        origin=origin, original_packet_string_sha256=hashlib.sha256(raw.encode()).hexdigest(),
                        request=payload, budget=measured, state=state,
                        admission_authorized=False, publication_allowed=False)
            output.write(json.dumps(item, ensure_ascii=False)+'\n')
    result = dict(schema=SCHEMA, count=20, states=dict(states), gpu_requests=0,
                  model=model, snapshot=str(snapshot) if snapshot else None,
                  revision=Path(snapshot).name if snapshot else None,
                  tokenizer_pins=tokenizer_pins, diagnostic_only=True,
                  model_scope='diagnostic_only' if model == base.MODEL else 'bulk_default',
                  policy_sha256=digest(POLICY), publication_allowed=False,
                  admission_authorized=False, semantic_approval=False, launch_supported=False,
                  source=str(source.resolve()),
                  source_manifest_sha256=file_hash(source/'manifest.json'),
                  source_catalog_sha256=file_hash(catalog),
                  packets_sha256=file_hash(root/'packets.jsonl'),
                  pins={str(Path(p).resolve()): file_hash(p) for p in
                        (__file__, base.__file__, adapter.__file__, budget.__file__,
                         'tests/test_baltic_qa31_grounded_pilot.py')})
    write_json(root/'manifest.json', result)
    write_json(root/'seal.json', dict(manifest_sha256=file_hash(root/'manifest.json')))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare'])
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--model', choices=[DEFAULT_MODEL, base.MODEL], default=DEFAULT_MODEL)
    parser.add_argument('--snapshot', type=Path, help='Local tokenizer snapshot matching --model; no downloads')
    parser.add_argument('--source', type=Path, default=Path('data/dfm13/baltic/qa31-article-diagnostic20-consumer-v3'))
    args = parser.parse_args()
    print(json.dumps(prepare(args.root, args.source, model=args.model, snapshot=args.snapshot)))


if __name__ == '__main__':
    main()
