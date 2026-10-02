"""Sixteen purposeful searches, then bounded native candidates; no admission."""
import argparse
import asyncio
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlsplit

import jinja2
from tokenizers import Tokenizer

from scripts import dfm13_search_lastslots2 as prior
from scripts import dfm13_search_budget_policy as policy
from scripts.dfm13_search_lastslots_stdin import read_credential

base, previous, pilot, temporal = prior.base, prior.previous, prior.pilot, prior.temporal
read = prior.read
ROOT = Path('data/dfm13/search-targeted16-20261001')
LOG = Path('logs/arena_review/20261001/search-targeted16.log')
# Each tuple is query, missing evidence, allowed source domains. Date operators
# aid discovery only; they do not certify a source's historical applicability.
PLANS = {
    '34a715dc': ('QEMU 9.2 Windows aarch64 virt UEFI firmware audio network documentation',
        'Version-specific Windows host installation and x86/aarch64 EFI, sound and network requirements.', ('qemu.org', 'qemu.weilnetz.de', 'tianocore.org')),
    '3812a931': ('circolo privato associazione corrispettivi telematici somministrazione soci registratore cassa 2024',
        'Distinguish commercial activity from member-only institutional activity; no categorical tax exemption.', ('agenziaentrate.gov.it', 'fiscooggi.it')),
    '3e6744b7': ('EOIR-40 Salvadoran NACARA suspension deportation eligibility seven years extreme hardship',
        'Qualifying class and substantive eligibility, not merely jurisdiction or a filing date.', ('justice.gov', 'uscis.gov', 'govinfo.gov', 'federalregister.gov')),
    '454d90e0': ('Llama 3.1 405B DeepSeek V3 Qwen2.5 1M context total active parameters model card',
        'Dated model-card total versus active parameters and native versus extended context; no unsupported comprehensive ranking.', ('huggingface.co', 'qwenlm.github.io', 'deepseek.com', 'ai.meta.com', 'github.com')),
    'd8174c0d': ('Trump scientists layoffs NOAA NIH March 2025 planned fired March 17',
        'Reports available before March 18 distinguish scientists from total workers, plans from completed layoffs.', ('reuters.com', 'apnews.com', 'nature.com', 'science.org')),
    'deb701de': ('Google Play change country 2025 payment profile country once year existing balance',
        'Official country-change conditions and availability restrictions, not VPN anecdotes or assumed workarounds.', ('support.google.com',)),
    '9fbc4c53': ('Attari 2010 public perceptions energy consumption savings Kantenbacher Attari 2021 decision making',
        'Actual research findings and bibliographic identity underlying proposed heuristic intervention.', ('pnas.org', 'pmc.ncbi.nlm.nih.gov', 'nature.com', 'sciencedirect.com', 'iu.edu')),
    'b6dacbac': ('ультразвуковое магнитогидродинамическое перемешивание жидкости научная статья полный текст',
        'Full publicly readable Russian research with title/authors and exact links, not invented bibliography.', ('cyberleninka.ru', 'mathnet.ru', 'journals.ioffe.ru')),
    'd4fc6d00': ('Marjorie Kinnan Rawlings Cross Creek chapters chronological thematic structure memoir',
        'Evidence on the book chapter organization rather than a generic plot synopsis.', ()),
    'd64649f4': ('làng rau Ngọc Lãng Phú Yên sinh kế du lịch cộng đồng 2015 2024',
        'Dated accounts distinguish historical farming contributions and observed tourism from projected benefits.', ('baophuyen.vn', 'vietnamtourism.gov.vn', 'baovanhoa.vn', 'vietnamplus.vn')),
    '99fe14a8': ('Meizu 21 Snapdragon 8 Gen 3 Android update policy video stabilization review 2024',
        'Device-specific software support, video and emulator limitations; user price is not proof of cheapest ranking.', ('meizu.com', 'notebookcheck.net', 'gsmarena.com')),
    'f911a4e7': ('MarkText 0.17.1 Visual Studio Code 1.99 disk installed size Windows system requirements',
        'Same-platform installed footprint versus compressed download; explicitly unknown if only download sizes found.', ('github.com', 'code.visualstudio.com', 'marktext.app')),
    '4f8af9d1': ('Tarkir Dragonstorm mythic rare card image gallery 2025',
        'Set-specific official card names and rarity; exclude Commander and special printings unless requested.', ('magic.wizards.com', 'scryfall.com')),
    '63f2b7df': ('LynxJS ReactLynx camera QR code scanning native module documentation 2025',
        'Real SDK/native camera bridge requirements; do not invent unsupported React Native package compatibility.', ('lynxjs.org', 'github.com')),
    'e19e0b36': ('Bluetooth security NIST SP 800-121 revision 2 federal guidance',
        'Exact public federal guidance and jurisdiction; recommendations are not automatically binding law.', ('nist.gov', 'csrc.nist.gov', 'govinfo.gov')),
    'f9669093': ('text to speech SSML break free tier character limits registration 2025',
        'Documented pause syntax and free-tier/account restrictions; no unsupported unlimited-free claim.', ('learn.microsoft.com', 'cloud.google.com', 'docs.aws.amazon.com', 'balabolka.site')),
}


class Budget(base.SearchBudget):
    def __init__(self, root, allowed):
        if len(allowed) != 16 or len(set(allowed.values())) != 16:
            raise ValueError('exact sixteen unique scoped queries required')
        super().__init__(root)
        self.allowed = dict(allowed)
        self.authorization = base.digest(allowed)
        self.db.execute('CREATE TABLE IF NOT EXISTS targeted_reservations (key TEXT PRIMARY KEY, owner TEXT, authorization TEXT)')
        self.db.commit()

    def reserve(self, query, owner):
        if self.allowed.get(owner) != query:
            raise ValueError('query outside explicit scope')
        key = base.digest(dict(provider='jina', endpoint='https://s.jina.ai/', query=query, accept='application/json'))
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row = self.db.execute('SELECT status,raw,provenance FROM searches WHERE key=?', (key,)).fetchone()
            if row:
                if row[0] != 'done':
                    raise ValueError('prior reservation unresolved; no paid retry')
                self.db.commit()
                return key, (row[1], json.loads(row[2]))
            if policy.ceiling(self.db) != 200:
                raise ValueError('explicit 200-cap policy required')
            if self.db.execute('SELECT count(*) FROM searches').fetchone()[0] >= 200:
                raise ValueError('campaign ceiling exhausted')
            if self.db.execute('SELECT count(*) FROM targeted_reservations WHERE authorization=?', (self.authorization,)).fetchone()[0] >= 16:
                raise ValueError('sixteen-query batch exhausted')
            self.db.execute('INSERT INTO searches(key,owner,query,status) VALUES(?,?,?,?)', (key, owner, query, 'reserved'))
            self.db.execute('INSERT INTO targeted_reservations VALUES(?,?,?)', (key, owner, self.authorization))
            self.db.commit()
            return key, None
        except BaseException:
            self.db.rollback()
            raise


def prepare():
    if ROOT.exists():
        raise ValueError('new root required')
    source = previous.ROOT / 'jobs.json'
    items = []
    for job in read(source):
        plan = PLANS.get(job['id'][:8])
        if not plan:
            continue
        query, reason, domains = plan
        asof = job['sample']['original_timestamp'][:10]
        items.append(dict(job=job, query=query + ' before:' + asof,
            reason=reason, source_asof=asof, allowed_domains=domains,
            date_policy='Search date operator is not proof. Future facts forbidden; undated current claims need applicable dated evidence or an explicit limitation.'))
    if len(items) != 16:
        raise ValueError('missing source tasks')
    base.atomic(ROOT / 'planned-queries.json', items)
    info = read(pilot.contract.METADATA)['tokenizer_info']
    dependencies = (Path(__file__), Path(policy.__file__), Path(base.__file__), Path(prior.__file__),
        Path(previous.__file__), Path(pilot.__file__), Path(temporal.__file__),
        Path(pilot.contract.__file__), Path(pilot.reviewer.__file__), Path(pilot.mode.__file__),
        Path(pilot.bounded.__file__), Path('scripts/dfm13_search_lastslots_stdin.py'),
        source, ROOT / 'planned-queries.json', pilot.contract.METADATA,
        Path(info['tokenizer_path']), Path(info['chat_template_path']),
        base.CAMPAIGN / 'cap-200-authorization.json')
    base.atomic(ROOT / 'authorization.json', dict(pins={str(p.resolve()):base.file_hash(p) for p in dependencies},
        allowed={x['job']['id']:x['query'] for x in items}, campaign=str(base.CAMPAIGN),
        maximum_new_queries=16, campaign_ceiling=200, no_paid_retries=True,
        concurrency_per_endpoint=8, admission_authorized=False,
        authorization='Explicit user instruction: targeted supplement batch 16-24; this branch selects sixteen.'))
    base.atomic(ROOT / 'runtime.json', dict(status='prepared_awaiting_secure_stdin', pid=None,
        paid_calls_started=False, credential_waiter=False, planned_queries=16))
    print(json.dumps(dict(root=str(ROOT), queries=16, handoff='python -m scripts.dfm13_search_targeted16 run-stdin')))


def selected_payload(payload, item):
    pages, exclusions = [], []
    for page in payload.get('data', []):
        url = page.get('url', '')
        host = (urlsplit(url).hostname or '').lower()
        domains = item['allowed_domains']
        dates = re.findall(r'(?<!\d)(20\d{2})[-/](\d{2})[-/](\d{2})(?!\d)', url)
        reason = None
        if domains and not any(host == d or host.endswith('.' + d) for d in domains):
            reason = 'outside scoped source domains'
        elif any('-'.join(date) > item['source_asof'] for date in dates):
            reason = 'explicit URL publication date after original question'
        if reason:
            exclusions.append(dict(url=url, reason=reason))
        else:
            pages.append(page)
    return dict(data=pages), exclusions


async def run():
    auth = read(ROOT / 'authorization.json')
    for name, sha in auth['pins'].items():
        if base.file_hash(Path(name)) != sha:
            raise ValueError('pinned input changed')
    generation = ROOT / 'generation'
    if not (generation / 'manifest.json').exists():
        secret = os.environ.get('JINA_API_KEY')
        if not secret:
            raise ValueError('secure stdin credential required; no waiting process')
        info = read(pilot.contract.METADATA)['tokenizer_info']
        student = Tokenizer.from_file(info['tokenizer_path'])
        template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
        def count(messages):
            return len(student.encode(pilot.contract.training.render(template, messages, base.TOOLS, True, False), add_special_tokens=False).ids)
        jobs, excluded, pins = [], [], dict(auth['pins'])
        async with base.Web('jina', ROOT / 'provider-snapshots') as web:
            web.budget = Budget(base.CAMPAIGN, auth['allowed'])
            for item in read(ROOT / 'planned-queries.json'):
                original = item['job']; key = original['id']
                folder = ROOT / 'retrieval' / key
                try:
                    if (folder / 'error.json').exists():
                        raise ValueError('previous bounded retrieval/preparation failure; retained without automatic retry')
                    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), status='retrieving',
                        completed=len(jobs)+len(excluded), total=16, current_id=key))
                    result = await web.search(item['query'], owner=key)
                    base.atomic(folder / 'result.json', result)
                    raw, provenance = web.budget.db.execute('SELECT raw,provenance FROM searches WHERE query=? AND status="done"', (item['query'],)).fetchone()
                    payload = base.strict_json(raw)
                    filtered, source_exclusions = selected_payload(payload, item)
                    index = next(i for i,m in enumerate(original['messages']) if m.get('tool_calls'))
                    history, removed = temporal.replace_controller_date(original['messages'][:index], original['sample']['original_timestamp'])
                    history.append(dict(role='assistant', content='', tool_calls=[dict(id='targeted16-'+key[:16], type='function',
                        function=dict(name='search', arguments=dict(query=item['query'])))]))
                    chunks = pilot.select_evidence(previous.eligible_paragraphs(filtered), item['query']+'\n'+original['sample']['prompt'], history, count, reserve=previous.RESERVE+300)
                    messages = pilot.history_with_observation(history, chunks, item['query'])
                    observation = base.strict_json(messages[-1]['content'])
                    observation.update(answer_asof=item['source_asof'], evidence_scope=item['reason'],
                        date_policy=item['date_policy'], publication_dates_not_verified=True)
                    messages[-1]['content'] = json.dumps(observation, ensure_ascii=False)
                    if count(messages)+previous.RESERVE > 4096:
                        raise ValueError('student budget exceeded; no silent truncation')
                    cache = folder / 'full-cache.json'; evidence = folder / 'evidence.json'
                    base.atomic(cache, payload)
                    base.atomic(evidence, dict(chunks=chunks, source_exclusions=source_exclusions,
                        raw_response_sha256=hashlib.sha256(raw).hexdigest(), full_response_snapshot=str(cache),
                        provider_provenance=json.loads(provenance), query=item['query'], reason=item['reason'],
                        source_asof=item['source_asof'], original_user_unchanged=True,
                        removed_controller_date_sentence=removed, original_job_sha256=base.digest(original),
                        query_author='controller', native_call_is_model_generated=False,
                        target_policy='final answer only; controller search and observations masked',
                        student_prompt_tokens=count(messages), answer_reserve_tokens=previous.RESERVE))
                    jobs.append(dict(id=key, sample=original['sample'], messages=messages, tools=base.TOOLS,
                        pages={p['url']:p for p in observation['results']}, evidence=str(evidence)))
                    for p in (cache, evidence, folder / 'result.json'):
                        pins[str(p.resolve())] = base.file_hash(p)
                except Exception as error:
                    entry = dict(id=key, reason=str(error).replace(secret, '[REDACTED]'), admission_authorized=False)
                    if not (folder / 'error.json').exists():
                        base.atomic(folder / 'error.json', entry)
                    excluded.append(entry)
            total = web.budget.db.execute('SELECT count(*) FROM searches').fetchone()[0]
        os.environ.pop('JINA_API_KEY', None)
        del secret
        pins[str((ROOT / 'authorization.json').resolve())] = base.file_hash(ROOT / 'authorization.json')
        previous.seal(generation, jobs, excluded, pins, info, read(previous.ROOT / 'manifest.json'))
        base.atomic(ROOT / 'retrieval-finished.json', dict(ready=len(jobs), excluded=excluded,
            paid_reservations=total, campaign_ceiling=200, no_admission=True))
    manifest = pilot.previous.verify(generation)
    pilot.GenerationSession = previous.GenerationSession
    pilot.reviewer.messages = temporal.review_messages
    original_atomic = base.atomic
    def atomic(path, value):
        if Path(path) == generation / 'progress.json':
            value = dict(value, total=manifest['total'])
        original_atomic(path, value)
    base.atomic = atomic
    base.atomic(ROOT / 'runtime.json', dict(pid=os.getpid(), status='generation_and_review', queued=manifest['total'],
        concurrency_per_endpoint=8, paid_calls_allowed=0))
    await pilot.run(argparse.Namespace(root=generation, concurrency_per_server=8, timeout=600))
    base.atomic(ROOT / 'runtime.json', dict(pid=None, status='terminal', previous_pid=os.getpid(),
        progress=read(generation / 'progress.json') if (generation / 'progress.json').exists() else {}, admission_authorized=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'run-stdin', 'resume-cached', '_child'])
    args = parser.parse_args()
    if args.command == 'prepare':
        prepare(); return
    if args.command == 'run-stdin':
        credential = read_credential(sys.stdin)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open('ab') as output:
            env = dict(os.environ); env.pop('JINA_API_KEY', None)
            child = subprocess.Popen([sys.executable, '-u', '-m', __spec__.name, '_child'],
                stdin=subprocess.PIPE, stdout=output, stderr=subprocess.STDOUT, env=env, start_new_session=True)
            child.stdin.write((credential+'\n').encode()); child.stdin.close()
        print(f'PID {child.pid}; log {LOG}')
        return
    if args.command == '_child':
        os.environ['JINA_API_KEY'] = read_credential(sys.stdin)
    elif not (ROOT / 'generation/manifest.json').exists():
        raise ValueError('cached generation manifest required')
    try:
        with (ROOT / 'run.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            asyncio.run(run())
    finally:
        os.environ.pop('JINA_API_KEY', None)


if __name__ == '__main__':
    main()
