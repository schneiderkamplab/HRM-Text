import copy
import hashlib
import json
import sqlite3

import pytest

from dfm12 import baltic_qa31_grounded_pilot as p
from dfm12.io import digest, file_hash, write_json


def packet():
    candidate = dict(id='a', language='lt', tools=[], target_message_index=3,
                     messages=[dict(role='user', content='When?'),
                               dict(role='assistant', content='Born in 1924.'),
                               dict(role='user', content='Where?'),
                               dict(role='assistant', content='Born in Kalvarija.')])
    article = {k: 'pin' for k in p.adapter.ARTICLE_FIELDS}
    article.update(language='lt', source_document_id='lt:1',
                   text='The person was born in Kalvarija in 1924.')
    article['text_sha256'] = hashlib.sha256(article['text'].encode()).hexdigest()
    return dict(candidate=candidate, candidate_sha256=digest(candidate),
                candidate_articles=[article], exact_generation_source_verified=False)


def review(q, verdict='keep', candidate=None):
    candidate = candidate or q['candidate']
    a = q['candidate_articles'][0]
    claims = []
    for i, m in enumerate(candidate['messages']):
        if m['role'] == 'assistant':
            claims.append(dict(message_index=i, start=0, end=len(m['content']), text=m['content'],
                               relation='contradicts' if verdict == 'repair' and i == 3 else 'supports',
                               citations=[dict(article_id=a['source_document_id'], text_sha256=a['text_sha256'], quote=a['text'])]))
    return dict(reason='Matched entity and supplied biography.', verdict=verdict, history_quality='pass',
                factual_support='contradicted' if verdict == 'repair' else 'sufficient',
                **p.binding(q, candidate), entity_match=True, date_scope_resolved=True,
                safety_pass=True, claims=claims)


def test_valid_quotes_are_not_semantic_approval():
    q = packet()
    decision = p.validate(q, review(q))
    assert decision['state'] == 'needs_semantic_review'
    assert decision['assistant_text_covered']
    assert not decision['admission_authorized'] and not decision['semantic_entailment_verified']


@pytest.mark.parametrize('verdict', ['keep', 'repair'])
def test_no_article_is_hold_even_for_positive_model(verdict):
    q = packet(); r = review(q, verdict); q['candidate_articles'] = []
    assert p.request(q) is None
    assert p.validate(q, r)['state'] == 'needs_review_verification'
    with pytest.raises(ValueError): p.repair_request(q, r)


@pytest.mark.parametrize('quote', ['Born in Kalvarija.', 'When?', 'The person was born elsewhere in 1924.', '1924'])
def test_qa_only_invented_and_trivial_quotes_fail(quote):
    q = packet(); r = review(q); r['claims'][0]['citations'][0]['quote'] = quote
    with pytest.raises(ValueError, match='verbatim'): p.validate(q, r)


@pytest.mark.parametrize('field', ['article_id', 'text_sha256'])
def test_article_reference_binding(field):
    q = packet(); r = review(q); r['claims'][0]['citations'][0][field] = 'wrong'
    with pytest.raises(ValueError): p.validate(q, r)


def test_changed_candidate_invalidates_receipt():
    q = packet(); r = review(q); q['candidate']['messages'][3]['content'] += ' Changed.'
    with pytest.raises(ValueError, match='binding'): p.validate(q, r)


def test_changed_article_invalidates_receipt():
    q = packet(); r = review(q); q['candidate_articles'][0]['text'] += ' Changed.'
    with pytest.raises(ValueError, match='drift'): p.validate(q, r)


@pytest.mark.parametrize('mutation', ['omit_history', 'omit_tail', 'overlap', 'empty_citations', 'user_span'])
def test_all_assistant_text_must_be_covered(mutation):
    q = packet(); r = review(q)
    if mutation == 'omit_history': r['claims'].pop(0)
    elif mutation == 'omit_tail':
        r['claims'][0]['end'] -= 1; r['claims'][0]['text'] = r['claims'][0]['text'][:-1]
    elif mutation == 'overlap': r['claims'].append(copy.deepcopy(r['claims'][0]))
    elif mutation == 'empty_citations': r['claims'][0]['citations'] = []
    else: r['claims'][0]['message_index'] = 0
    with pytest.raises(ValueError): p.validate(q, r)


@pytest.mark.parametrize('field', ['entity_match', 'date_scope_resolved', 'safety_pass'])
def test_unresolved_checks_hold(field):
    q = packet(); r = review(q); r[field] = False
    assert p.validate(q, r)['state'] == 'needs_review_verification'


def test_bad_protected_history_cannot_be_repaired():
    q = packet(); r = review(q, 'repair'); r['claims'][0]['relation'] = 'contradicts'
    assert p.validate(q, r)['state'] == 'needs_review_verification'


def test_repair_requires_new_evidence_and_keeps_history():
    q = packet(); r = review(q, 'repair')
    q_before = copy.deepcopy(q)
    candidate = copy.deepcopy(q['candidate']); candidate['messages'][3]['content'] = 'In Kalvarija.'
    evidence = review(q, candidate=candidate)
    for field in ('candidate_sha256', 'articles_sha256'): evidence.pop(field)
    result = dict(reason='Correction from biography.', target='In Kalvarija.', evidence_review=evidence)
    decision, corrected = p.validate_repair(q, r, result)
    assert corrected['messages'][:-1] == q['candidate']['messages'][:-1]
    assert q == q_before and not decision['admission_authorized']
    result['target'] += ' Unsupported extra fact.'
    with pytest.raises(ValueError, match='coverage'): p.validate_repair(q, r, result)


def test_quote_overlap_is_not_entailment_certification():
    q = packet(); q['candidate']['messages'][3]['content'] = 'Born on Mars.'
    # Even apparently valid text citations must still undergo semantic review.
    decision = p.validate(q, review(q))
    assert decision['state'] == 'needs_semantic_review' and not decision['semantic_approval']


def test_requests_exclude_prior_qa_gold_and_preserve_full_articles():
    q = packet(); q['upstream_record'] = {'secret_prior_judgment': 'keep'}
    payload = p.request(q)
    content = json.loads(payload['messages'][1]['content'])
    assert content['candidate_articles'] == q['candidate_articles']
    assert 'upstream_record' not in content and 'secret_prior_judgment' not in json.dumps(content)
    assert payload['model'] == p.DEFAULT_MODEL
    assert p.request(q, model=p.base.MODEL)['model'] == p.base.MODEL


def test_prepare_preserves20_and_nohit_rows_without_dispatch(tmp_path):
    source = tmp_path/'old'; source.mkdir()
    db = sqlite3.connect(source/'catalog.sqlite')
    db.execute('CREATE TABLE catalog(id TEXT,packet TEXT,prior_evidence TEXT,origin TEXT)')
    for i in range(20):
        q = packet()
        if i < 5: q['candidate_articles'] = []
        db.execute('INSERT INTO catalog VALUES(?,?,?,?)', (str(i), json.dumps(q), '{}', 'old'))
    db.commit(); db.close()
    manifest = dict(diagnostic_only=True, count=20, calibration_diagnostic_ids=[str(i) for i in range(20)],
                    snapshot='test', revision='test', pins={str((source/'catalog.sqlite').resolve()): file_hash(source/'catalog.sqlite')})
    write_json(source/'manifest.json', manifest)
    write_json(source/'seal.json', dict(manifest_sha256=file_hash(source/'manifest.json')))
    old_sha = file_hash(source/'catalog.sqlite')
    class Tokenizer:
        def apply_chat_template(self, messages, **kwargs): return [1]*100
    result = p.prepare(tmp_path/'new', source, Tokenizer())
    assert result['states'] == {'needs_review_verification': 5, 'pending_quoted_review': 15}
    assert result['gpu_requests'] == 0 and not result['launch_supported']
    assert file_hash(source/'catalog.sqlite') == old_sha
    assert len((tmp_path/'new/packets.jsonl').read_text().splitlines()) == 20
    with pytest.raises(FileExistsError): p.prepare(tmp_path/'new', source, Tokenizer())
