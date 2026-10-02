"""Future-only Jina controls. No network calls or historical cache migration."""
from dataclasses import asdict, dataclass
import hashlib
import json
import re
import sqlite3
from urllib.parse import parse_qs, urlsplit


def historical_key(query):
    value = {'provider': 'jina', 'endpoint': 'https://s.jina.ai/',
             'query': query, 'accept': 'application/json'}
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def historical_restricted_hit(db, query, owner, settings):
    """Read-only exact-owner/query compatibility lookup; never reserves or fetches.

    A present but corrupt/mismatched record raises rather than inviting a paid
    fallback. Historical provider budgets cannot be applied retroactively.
    """
    key = historical_key(query)
    row = db.execute('SELECT owner,query,status,raw,provenance FROM searches WHERE key=?', (key,)).fetchone()
    if row is None:
        return None
    cached_owner, cached_query, status, raw, provenance_text = row
    if cached_owner != owner or cached_query != query:
        raise ValueError('historical owner/query provenance mismatch')
    if status != 'done':
        raise ValueError('historical request unresolved; no automatic paid retry')
    raw = raw.encode() if isinstance(raw, str) else raw
    provenance = json.loads(provenance_text)
    raw_hash = hashlib.sha256(raw).hexdigest()
    if provenance.get('response_sha256') != raw_hash or not provenance.get('retrieved_at'):
        raise ValueError('historical response hash/time mismatch')
    for field in ('requested_url', 'url'):
        url = urlsplit(provenance.get(field, ''))
        if (url.scheme != 'https' or url.netloc != 's.jina.ai' or url.path != '/'
                or url.fragment or parse_qs(url.query) != {'q': [query]}):
            raise ValueError('historical source endpoint/query mismatch')
    payload = json.loads(raw)
    if not isinstance(payload, dict) or not isinstance(payload.get('data'), list):
        raise ValueError('invalid historical response schema')
    results = []
    for page in payload['data'][:settings.num]:
        if not isinstance(page, dict) or not isinstance(page.get('url'), str):
            raise ValueError('invalid historical result schema')
        item = {k: page[k] for k in ('title', 'url', 'date') if k in page}
        description = page.get('description')
        content = page.get('content')
        text = description if isinstance(description, str) and description else content
        text = text if isinstance(text, str) else ''
        item.update(description=text[:1000], snippet_truncated=len(text) > 1000,
                    snippet_origin='description' if text is description else 'extractive_content_prefix')
        results.append(item)
    return {'data': results, 'provenance': {
        'cache_hit': True, 'derived_locally': True, 'derivation_version': 1,
        'query': query, 'owner': owner, 'historical_cache_key': key,
        'derived_cache_key': settings.cache_key(query), 'requested_settings': asdict(settings),
        'original_retrieved_at': provenance['retrieved_at'],
        'original_response_sha256': raw_hash, 'original_provenance': provenance,
        'historical_usage': usage_receipt(payload, received_bytes=len(raw)),
        'provider_requests_this_lookup': 0, 'provider_token_budget_applied': False,
        'snippet_character_limit': 1000,
        'note': 'Local projection of previously billed content, not a new provider response or retroactively budget-limited retrieval.'}}


def restricted_search_plan(db, query, owner, settings=None):
    """Resolve historical data before offering request settings for a true miss.

    A miss is not authorization to dispatch: caller must still reserve under
    the shared campaign ceiling and dispatch guard. This function has no I/O
    beyond SQLite SELECT and never calls the provider.
    """
    settings = settings or SearchSettings()
    hit = historical_restricted_hit(db, query, owner, settings)
    if hit is not None:
        return {'status': 'cache_hit', 'response': hit, 'request': None}
    return {'status': 'cache_miss', 'response': None, 'request': settings.request(query),
            'cache_key': settings.cache_key(query), 'dispatch_authorized': False}


@dataclass(frozen=True)
class SearchSettings:
    num: int = 5
    token_budget: int = 25000
    respond_with: str = 'no-content'

    def __post_init__(self):
        if type(self.num) is not int or not 1 <= self.num <= 5:
            raise ValueError('num must be an integer in 1..5')
        if type(self.token_budget) is not int or not 1 <= self.token_budget <= 25000:
            raise ValueError('token budget must be an integer in 1..25000')
        if self.respond_with != 'no-content':
            raise ValueError('discovery must not fetch full result contents')

    def request(self, query):
        return {'params': {'q': query, 'num': self.num}, 'headers': {
            'Accept': 'application/json', 'X-Respond-With': self.respond_with,
            'X-Token-Budget': str(self.token_budget)}}

    def cache_key(self, query):
        value = {'version': 2, 'endpoint': 'https://s.jina.ai/',
                 'query': query, 'settings': asdict(self)}
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def usage_receipt(payload, *, received_bytes, oversized=False):
    """Keep alternative usage fields separate; unknown is never zero billing."""
    payload = payload if isinstance(payload, dict) else {}
    meta = payload.get('meta')
    pages = payload.get('data')
    return {'meta_usage': meta.get('usage') if isinstance(meta, dict) else None,
            'top_usage': payload.get('usage'),
            'item_usage': [{'url': p.get('url'), 'usage': p.get('usage')}
                           for p in (pages if isinstance(pages, list) else [])
                           if isinstance(p, dict)],
            'received_bytes': received_bytes, 'oversized': oversized,
            'billing_complete': False,
            'note': 'Response usage is not an invoice; local size rejection does not establish zero charge.'}


def sanitized_body(body, secrets=()):
    text = body.decode('utf-8', errors='replace') if isinstance(body, bytes) else str(body)
    for secret in secrets:
        if secret:
            text = text.replace(secret, '[REDACTED]')
    text = re.sub(r'jina_[A-Za-z0-9_-]+', '[REDACTED]', text)
    text = re.sub(r'(?i)bearer\s+[^\s"<>]+', 'Bearer [REDACTED]', text)
    text = re.sub(r'(?i)(["\x27]?(?:authorization|api[_-]?key|token)["\x27]?\s*[:=]\s*)["\x27]?[^\s,"\x27}]+', r'\1[REDACTED]', text)
    return text[:2048]


class DispatchGuard:
    """Use the SAME SQLite connection/transaction as reservation insertion.

    Cache hits precede this gate. Call check_in_transaction immediately before
    reserving any new request. In-flight calls cannot be recalled; semaphore
    acquisition must precede reservation. This class never refunds or retries.
    """
    def __init__(self, db: sqlite3.Connection):
        self.db = db
        db.execute('CREATE TABLE IF NOT EXISTS jina_dispatch_halt (id INTEGER PRIMARY KEY CHECK(id=1), receipt TEXT NOT NULL)')

    def check_in_transaction(self):
        if not self.db.in_transaction:
            raise RuntimeError('reservation transaction required')
        if self.db.execute('SELECT 1 FROM jina_dispatch_halt WHERE id=1').fetchone():
            raise RuntimeError('Jina dispatch halted; cached work only')

    def record_failure(self, status, body, *, secrets=()):
        receipt = {'status': status, 'body': sanitized_body(body, secrets),
                   'systemic_halt': status in (401, 402, 403), 'retry': False}
        if receipt['systemic_halt']:
            with self.db:
                self.db.execute('INSERT OR IGNORE INTO jina_dispatch_halt VALUES (1,?)',
                                (json.dumps(receipt),))
        return receipt
