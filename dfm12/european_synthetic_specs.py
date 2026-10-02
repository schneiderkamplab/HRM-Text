"""Isolated 12-language synthetic adapter; no admission or live-module mutation."""
from contextlib import closing
import json
import sqlite3
from types import FunctionType

from .io import digest
from . import multilingual_tasks as tasks
from . import multilingual_generation_v4 as generation
from . import multilingual_tool_dialogue as native
from . import multilingual_review_indexed as review
from .multilingual_production_specs import SourceProvider as BaseProvider, SeedUnavailable

VERSION = 'european-synthetic-specs-v1'
LANGUAGES = dict(de='German', fr='French', es='Spanish', it='Italian', cs='Czech',
                 pt_pt='European Portuguese (pt-PT)', fi='Finnish', et='Estonian',
                 ca='Catalan', el='Greek', ro='Romanian', uk='Ukrainian')
FAMILIES = tuple(tasks.QUOTAS)
PT_PT_REQUIREMENT = ('Use European Portuguese (pt-PT), not Brazilian Portuguese (pt-BR), '
    'in every natural-language user and assistant turn. Check idiom, grammar and '
    'vocabulary in context; shared Portuguese words alone do not establish the variant. '
    'Preserve quoted source text, code, tool names and identifiers unchanged.')

# Reuse the exact factory bytecode with a private globals dictionary. Unlike a
# temporary monkeypatch this cannot change another thread's seven-language run.
_factory = FunctionType(tasks.spec_for.__code__,
    dict(tasks.spec_for.__globals__, LANGUAGES=dict(LANGUAGES)),
    tasks.spec_for.__name__, tasks.spec_for.__defaults__, tasks.spec_for.__closure__)


def spec_for(language, family, slot, attempt, seeds, config):
    if language not in LANGUAGES or family not in FAMILIES:
        raise ValueError('Unsupported European language/family')
    if any(type(n) is not int or n < 0 for n in (slot, attempt)):
        raise ValueError('Slot and attempt must be nonnegative integers')
    if config.get('contract_version') != 4 or not config.get('cohort'):
        raise ValueError('Require contract version 4 and a new explicit cohort')
    spec = _factory(language, family, slot, attempt, seeds, config)
    if language == 'pt_pt':
        spec['language_variant_requirements'] = PT_PT_REQUIREMENT
    return spec


class SourceProvider(BaseProvider):
    """Single-writer durable selection from Boole's append-only seed inventory.

    Both pools use available_seeds(language,pool,seq,source_id,payload), so the
    seed owner controls eligibility. No downloading, license grant or wrapping.
    """
    def __init__(self, seeds_root, root, config):
        languages = config.get('languages', list(LANGUAGES))
        if (not languages or len(set(languages)) != len(languages)
                or any(language not in LANGUAGES for language in languages)):
            raise ValueError('Invalid European target languages')
        super().__init__(seeds_root, root, config)
        self.languages = tuple(languages)
        signature = digest(dict(version=VERSION, languages=self.languages, names=LANGUAGES))
        with self.db:
            row = self.db.execute("SELECT value FROM metadata WHERE key='european_adapter'").fetchone()
            if row is None and self.db.execute('SELECT 1 FROM selections LIMIT 1').fetchone():
                raise ValueError('Cannot reuse a legacy selection root')
            if row and row[0] != signature:
                raise ValueError('European adapter configuration drift')
            self.db.execute("INSERT OR IGNORE INTO metadata VALUES ('european_adapter',?)", (signature,))

    def next_spec(self, language, family, slot):
        if language not in self.languages:
            raise ValueError('Language not enabled in campaign')
        placeholder = dict(id='unallocated', text='unallocated', messages=[])
        seeds = {key: [placeholder] for key in (*LANGUAGES, 'openhermes')}
        spec = spec_for(language, family, slot, 0, seeds, self.config)
        key = digest([language, family, slot])
        with self.db:
            self.db.execute('BEGIN IMMEDIATE')
            found = self.db.execute('SELECT spec FROM selections WHERE id=?', (key,)).fetchone()
            if found:
                return json.loads(found[0])
            seed_hash = None
            if 'source' in spec:
                pool = 'openhermes' if family == 'openhermes' else language
                scope = f'{language}/{pool}'
                row = self.db.execute('SELECT seq FROM cursors WHERE scope=?', (scope,)).fetchone()
                cursor = row[0] if row else 0
                if not self.seeds_path.is_file():
                    raise SeedUnavailable(pool + ': seed preparation not ready')
                with closing(sqlite3.connect(self.seeds_path.resolve().as_uri()+'?mode=ro', uri=True, timeout=30)) as source:
                    while True:
                        row = source.execute('SELECT seq,source_id,payload FROM available_seeds '
                            'WHERE language=? AND pool=? AND seq>? ORDER BY seq LIMIT 1',
                            (language, pool, cursor)).fetchone()
                        if not row:
                            raise SeedUnavailable(pool + ': waiting for additional unique sources')
                        cursor, source_id, payload = row
                        if not self.db.execute('SELECT 1 FROM used_sources WHERE scope=? AND source_id=?',
                                               (scope, source_id)).fetchone():
                            break
                seed = json.loads(payload)
                if (not isinstance(source_id, str) or not source_id
                        or not isinstance(seed, dict) or seed.get('id') != source_id):
                    raise ValueError('Seed ID/payload mismatch')
                expected_language = 'en' if pool == 'openhermes' else language
                if seed.get('language', expected_language) != expected_language:
                    raise ValueError('Seed language/pool mismatch')
                if pool == 'openhermes':
                    generation._pairs(dict(spec, source=seed))
                elif not isinstance(seed.get('text'), str) or not seed['text'].strip():
                    raise ValueError('Native seed requires nonblank source text')
                spec['source'] = seed
                seed_hash = digest(seed)
                self.db.execute('INSERT INTO used_sources VALUES (?,?)', (scope, source_id))
                self.db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)', (scope, cursor))
            self.db.execute('INSERT INTO selections VALUES (?,?,?)',
                (key, json.dumps(spec, ensure_ascii=False), seed_hash))
        return spec


def _check_spec(spec):
    code = spec.get('language_code')
    if (code not in LANGUAGES or spec.get('language') != LANGUAGES[code]
            or spec.get('contract_version') != 4 or spec.get('family') not in FAMILIES):
        raise ValueError('Not a European v4 specification')


def request(spec, *, endpoint_models=None):
    _check_spec(spec)
    if spec['family'] == 'tool-dialogue':
        payload = native.request(spec)
    else:
        payload = generation.request(spec, endpoint_models=endpoint_models)
    if spec['language_code'] == 'pt_pt':
        payload['messages'][0]['content'] += '\n' + PT_PT_REQUIREMENT
    generation.measure_prompt(payload, generation.context_limit(endpoint_models))
    return payload


def decode(spec, content, finish_reason):
    _check_spec(spec)
    if spec['family'] != 'tool-dialogue':
        return generation.decode(spec, content, finish_reason)
    import jsonschema
    if finish_reason != 'stop':
        raise ValueError('Incomplete tool generation')
    output = generation._parse(content)
    jsonschema.validate(output, native.request(spec)['response_format']['json_schema']['schema'])
    return output


def assemble(spec, output):
    _check_spec(spec)
    candidate = (native if spec['family'] == 'tool-dialogue' else generation).assemble(spec, output)
    candidate['admission_authorized'] = False
    return candidate


def audit_record(candidate):
    spec = candidate['provenance']
    _check_spec(spec)
    if candidate['language'] != spec['language_code'] or candidate['family'] != spec['family']:
        raise ValueError('Candidate/specification identity mismatch')
    record = {key: candidate[key] for key in ('language', 'family', 'messages', 'tools')}
    record.update(language_name=LANGUAGES[candidate['language']], requested_subtype=spec['subtype'])
    if candidate['language'] == 'pt_pt':
        record['language_variant_requirements'] = PT_PT_REQUIREMENT
    for key in ('reference', 'scenario', 'terminal_evidence', 'tool_dialogue_grounding'):
        if key in spec or key in candidate:
            record[key] = spec[key] if key in spec else candidate[key]
    if 'source' in spec:
        record['source'] = spec['source']
        if candidate['family'] == 'openhermes':
            record['source_messages'] = spec['source']['messages']
    return record


def review_request(candidate):
    payload = review.request(audit_record(candidate))
    if candidate['language'] == 'pt_pt':
        payload['messages'][0]['content'] += '\nReject a wrong language variant. ' + PT_PT_REQUIREMENT
    return payload
