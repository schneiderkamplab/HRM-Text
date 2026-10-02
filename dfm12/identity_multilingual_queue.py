"""CPU-only, coordination-gated identity extension ledger; no network or GPU runner."""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile

import yaml

from . import identity, identity_correction, identity_extension, export_validator
from .audit_pilot_gpu import MODEL
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import audit_payload, validate_audit
from .records import chat_fingerprint, validate_messages

VERSION = 'identity-multilingual-accepted-queue-v1'
LANGUAGES = dict(zip(
    ('da','en','nl','nb','nn','sv','is','fo','pl','de','fr','es','it','cs','pt_pt','fi','el','ro','uk','et','ca'),
    ('Danish','English','Dutch','Norwegian Bokmaal','Norwegian Nynorsk','Swedish','Icelandic','Faroese','Polish',
     'German','French','Spanish','Italian','Czech','European Portuguese (Portugal, not Brazilian Portuguese)',
     'Finnish','Greek','Romanian','Ukrainian','Estonian','Catalan')))
ORIGINAL = tuple(LANGUAGES)[:9]
CORRECTED = Path('data/dfm12/identity-corrected-da-en-20260926-v4')
HOLDOUT = Path('data/dfm12/identity-composition-holdout-20260927-v1')
STYLES = ('simple direct question, concise answer', 'false premise with explicit correction',
          'ordinary conversation followed by a relevant identity question',
          'brief compound question, answer every part without an unsolicited introduction',
          'distinguish current XL from historical v1', 'beginner explanation',
          'technical explanation with precise number formatting', 'clarify an unspecified claim')


def prompt_hash(messages):
    return digest([identity_extension.question_key(m['content']) for m in messages if m['role']=='user'])


def heldout_hash(text):
    return digest(identity_extension.question_key(text))


def request(language, slot, recipe):
    topics=recipe['topics']; topic=topics[(slot-100000)%len(topics)]
    variation=(slot-100000)//len(topics)
    turns=(1,1,2,3,4)[variation%5]
    specification=dict(language=LANGUAGES[language], language_code=language, topic=topic,
        style=STYLES[variation%len(STYLES)], user_turns=turns, variation=slot,
        grounding=recipe['grounding'], requirements=recipe['requirements'])
    record=dict(id=digest([VERSION,language,slot,recipe]), language=language, task='identity',
        profile='xl-full-bp', audit_context=recipe['grounding'],
        provenance=dict(source=VERSION,slot=slot,recipe_sha256=digest(recipe)))
    system=('Create one natural identity training conversation in the requested language, '
        'not a translation exercise. Return only JSON {"messages": [{"role":"user", "content":"..."}, ...]}. '
        'Alternate user/assistant, end with assistant, use exactly the requested user turns. '
        'No system messages, hidden reasoning, role tokens, or invented facts. Use fresh natural wording; '
        'do not copy familiar training questions or merely change punctuation. Preserve proper names. '
        'The assistant is Mimir, not the model generating this example. Follow the supplied factual '
        'authority and requested answer format, correct false premises explicitly, and answer ordinary '
        'requests without gratuitous identity claims. Native fluency and exact language variant matter.')
    return dict(record=record,request=dict(model=MODEL,temperature=.7,max_tokens=4096,
        chat_template_kwargs={'enable_thinking':False},messages=[{'role':'system','content':system},
        {'role':'user','content':json.dumps(specification,ensure_ascii=False)}]))


def recipe():
    facts=yaml.safe_load(identity.FACTS.read_text())
    correction=yaml.safe_load(Path('dfm12/identity_correction.yaml').read_text())
    repair=yaml.safe_load(Path('dfm12/identity_repair_expansion.yaml').read_text())
    expansion=yaml.safe_load(Path('dfm12/identity_expansion.yaml').read_text())
    # Only topic/fact identifiers are reused; heldout wording and answers never enter requests.
    topics=[dict(recipe=label,key=k,topic=v['topic'],facts=v['facts'])
            for label,source in [('expansion-v2',expansion),('repair-v3',repair)]
            for k,v in source['requests'].items()]
    return dict(topics=topics,grounding=dict(facts=facts['facts'],sources=facts['sources'],
        profile=facts['profiles']['xl-full-bp'],current_runtime=correction['runtime_binding'],
        checkpoint_continuation=repair['authorized_context']['checkpoint_continuation']),requirements=[
        'DFM organizational leaders are Kristoffer Nielbo and Peter Schneider-Kamp; the training-team leader is Peter Schneider-Kamp. Do not invent roster members or infer noninvolvement.',
        'Current XL: 16 layers in L and 16 in H; two H cycles with three L cycles each, six L passes and two H passes. Layers and passes differ. No unsupported historical depth comparison.',
        'Original scratch training used random weights, not inherited Gemma weights. Checkpoint continuation retains learned weights; generated training text does not copy teacher weights.',
        'Mimir v1 used Gemma 4 tokenization. The separate 65536-token BPE belongs to the original HRM-Text report. Current runtime is Gemma-derived with adapted template, not byte-identical.',
        'Historical 161 datasets and 70479308606 tokens per epoch are v1 quantities, not counts for every later release. Format numbers naturally for the requested language.',
        'Brief compound answers must address every part; neutral questions do not need an invented No. No claims of tool access, memory, hardware, native ability or affiliations without authority.',
        'NB and NN are distinct written standards. Use European Portuguese for pt_pt, never silently substitute pt-BR.'])


def source_inventory(exports, corrected, holdout):
    retained={lang:[] for lang in LANGUAGES}; originals={}; pins={}; forbidden_chats=set(); forbidden_prompts=set(); heldouts=set()
    def pin(path):
        pins[str(Path(path).resolve())]=file_hash(path)
    for lang in ORIGINAL:
        package=Path(exports)/f'dfm12-identity-xl-full-bp-{lang}'
        export_validator.validate(package)
        manifest=load(package/'metadata/manifest.json');pin(package/'metadata/manifest.json')
        if manifest['source']['profile']!='xl-full-bp' or manifest['source']['facts_sha256']!=file_hash(identity.FACTS):
            raise ValueError('Original identity authority mismatch')
        records=[]
        for item in manifest['data_files']:
            path=package/item['file'];pin(path);records.extend(rows(path))
        for item in manifest['metadata_files']:pin(package/item['file'])
        if len(records)!=manifest['counts']['accepted'] or len({chat_fingerprint(r['messages']) for r in records})!=len(records):
            raise ValueError('Original accepted count or uniqueness mismatch')
        for row in records:
            if row['language']!=lang:raise ValueError('Original language mismatch')
            forbidden_chats.add(chat_fingerprint(row['messages']));forbidden_prompts.add((lang,prompt_hash(row['messages'])))
        originals[lang]=len(records)
        if lang not in ('da','en'):retained[lang]=records
    identity_correction.verify(corrected)
    manifest=load(corrected/'manifest.json');pin(corrected/'manifest.json');pin(corrected/'seal.json')
    for item in manifest['files']:pin(corrected/item['path'])
    for lang in ('da','en'):
        retained[lang]=list(rows(corrected/manifest['languages'][lang]['input']))
        if len(retained[lang])!=manifest['languages'][lang]['counts']['merged']['conversations']:
            raise ValueError('Corrected retained count mismatch')
        for split,name in [('heldout','test'),('development','previous-heldout')]:
            for row in rows(corrected/split/lang/(name+'.jsonl.gz')):
                forbidden_chats.add(chat_fingerprint(row['messages']))
                heldouts.update(heldout_hash(m['content']) for m in row['messages'] if m['role']=='user')
    heldout_manifest=load(holdout/'manifest.json');pin(holdout/'manifest.json')
    if heldout_manifest.get('training_allowed') is not False:raise ValueError('Heldout boundary missing')
    for name,sha in heldout_manifest['files'].items():
        if file_hash(holdout/name)!=sha:raise ValueError('Heldout drift')
        pin(holdout/name)
    for case in load(holdout/'cases.json'):
        heldouts.update(heldout_hash(text) for text in case['users'])
    for lang,records in retained.items():
        for row in records:
            forbidden_chats.add(chat_fingerprint(row['messages']));forbidden_prompts.add((lang,prompt_hash(row['messages'])))
    return retained,originals,pins,forbidden_chats,forbidden_prompts,heldouts


def initialize(db, retained, target, recipe_value, chats=(), prompts=(), heldouts=()):
    db.executescript('''
      CREATE TABLE metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE targets(language TEXT PRIMARY KEY,target INTEGER,retained INTEGER,accepted_new INTEGER DEFAULT 0,
        active INTEGER DEFAULT 0,attempts INTEGER DEFAULT 0,next_slot INTEGER,max_attempts INTEGER,
        CHECK(retained+accepted_new+active<=target),CHECK(active>=0));
      CREATE TABLE jobs(id TEXT PRIMARY KEY,language TEXT,slot INTEGER,state TEXT,payload TEXT,owner TEXT,
        candidate TEXT,audit_payload TEXT,generation_result TEXT,audit_result TEXT,error TEXT,
        UNIQUE(language,slot));
      CREATE INDEX pending ON jobs(state,language,slot);
      CREATE TABLE seen(fingerprint TEXT PRIMARY KEY,owner TEXT);
      CREATE TABLE prompts(language TEXT,fingerprint TEXT,owner TEXT,PRIMARY KEY(language,fingerprint));
      CREATE TABLE heldouts(fingerprint TEXT PRIMARY KEY);
    ''')
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('INSERT INTO metadata VALUES (?,?)',('activated','false'))
        db.executemany('INSERT INTO seen VALUES (?,?)',((h,'prior') for h in chats))
        db.executemany('INSERT INTO prompts VALUES (?,?,?)',((lang,h,'prior') for lang,h in prompts))
        db.executemany('INSERT INTO heldouts VALUES (?)',((h,) for h in heldouts))
        for lang in LANGUAGES:
            count=len(retained.get(lang,[]));gap=target-count
            if gap<0:raise ValueError('Target below existing retained count')
            db.execute('INSERT INTO targets(language,target,retained,next_slot,max_attempts) VALUES(?,?,?,?,?)',
                       (lang,target,count,100000+gap,6*gap))
            for slot in range(100000,100000+gap):
                payload=request(lang,slot,recipe_value)
                db.execute('INSERT INTO jobs(id,language,slot,state,payload) VALUES(?,?,?,?,?)',
                           (payload['record']['id'],lang,slot,'queued',json.dumps(payload,ensure_ascii=False)))
        db.execute('COMMIT')
    except BaseException:
        db.execute('ROLLBACK');raise


def prepare(root,exports=Path('exports_dfm12'),corrected=CORRECTED,holdout=HOLDOUT,target=2000):
    root=Path(root).resolve();corrected=Path(corrected);holdout=Path(holdout)
    if root.exists():raise FileExistsError(root)
    if type(target) is not int or target<1:raise ValueError('Positive integer target required')
    inventory=source_inventory(exports,corrected,holdout)
    retained,originals,pins,chats,prompts,heldouts=inventory
    root.parent.mkdir(parents=True,exist_ok=True)
    temp=Path(tempfile.mkdtemp(prefix='.identity-queue-',dir=root.parent))
    try:
        value=recipe();write_json(temp/'recipe.json',value)
        for path in (identity.FACTS,Path('dfm12/identity_correction.yaml'),Path('dfm12/identity_expansion.yaml'),
                     Path('dfm12/identity_repair_expansion.yaml'),Path('data/sampled_dfm11/metadata.json')):
            pins[str(path.resolve())]=file_hash(path)
        info=load('data/sampled_dfm11/metadata.json')['tokenizer_info']
        if info.get('enable_thinking') is not False:raise ValueError('Training template must be non-thinking')
        for key in ('tokenizer_path','chat_template_path'):pins[str(Path(info[key]).resolve())]=file_hash(info[key])
        files={'recipe.json':file_hash(temp/'recipe.json')};counts={}
        for lang,records in retained.items():
            path=temp/'retained'/f'{lang}.jsonl.gz'
            identity_extension.write_rows(path,records);files[str(path.relative_to(temp))]=file_hash(path)
            counts[lang]=dict(target=target,retained=len(records),accepted_originals=originals.get(lang,0),
                new_accepts_needed=target-len(records),baseline_kind='corrected_v4_local_curated' if lang in ('da','en') else 'audited_export' if records else 'none')
        db=sqlite3.connect(temp/'queue.sqlite',isolation_level=None)
        try:initialize(db,retained,target,value,chats,prompts,heldouts)
        finally:db.close()
        modules=[Path(__file__),Path(identity_extension.__file__),Path(identity_correction.__file__),
                 Path(identity.__file__),Path(export_validator.__file__),Path(__file__).with_name('jobs.py'),
                 Path(__file__).with_name('records.py')]
        manifest=dict(version=VERSION,policy='coordination_required_no_network_runner',languages=counts,
            target_accepted_or_retained=target*len(LANGUAGES),physical_repeat=1,source_pins=pins,
            implementation_pins={str(p.resolve()):file_hash(p) for p in modules},files=files,
            preserved_corrected_da_en_not_new_teacher_certification=True,heldout_prompt_hashes=len(heldouts),
            max_candidates_per_deficit=6,failed_rows_replayed=False,quality_audit_required=True,
            original_databases_unchanged=True,student_tokenizer=info,
            preparation_requests=sum(v['new_accepts_needed'] for v in counts.values()))
        write_json(temp/'manifest.json',manifest)
        write_json(temp/'seal.json',{'manifest_sha256':file_hash(temp/'manifest.json')})
        with sqlite3.connect(temp/'queue.sqlite') as db:
            db.execute('INSERT INTO metadata VALUES (?,?)',('manifest_sha256',file_hash(temp/'manifest.json')))
        temp.rename(root)
    except BaseException:
        shutil.rmtree(temp);raise
    return manifest


def verify(root):
    root=Path(root);manifest=load(root/'manifest.json')
    if manifest['version']!=VERSION or file_hash(root/'manifest.json')!=load(root/'seal.json')['manifest_sha256']:
        raise ValueError('Queue manifest drift')
    for name,sha in manifest['files'].items():
        if file_hash(root/name)!=sha:raise ValueError('Queue artifact drift: '+name)
    for path,sha in {**manifest['source_pins'],**manifest['implementation_pins']}.items():
        if file_hash(path)!=sha:raise ValueError('Queue pin drift: '+path)
    with sqlite3.connect((root/'queue.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
        if db.execute("SELECT value FROM metadata WHERE key='manifest_sha256'").fetchone()[0]!=file_hash(root/'manifest.json'):
            raise ValueError('Ledger manifest mismatch')
    return manifest


class Queue:
    """One durable broker, or multiple SQLite-serialized brokers; no HTTP side effects."""
    def __init__(self,root):
        self.root=Path(root);self.recipe=load(self.root/'recipe.json')
        self.db=sqlite3.connect(self.root/'queue.sqlite',isolation_level=None)
        self.db.row_factory=sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL');self.db.execute('PRAGMA synchronous=FULL')

    def close(self):self.db.close()

    @contextmanager
    def transaction(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:yield;self.db.execute('COMMIT')
        except BaseException:self.db.execute('ROLLBACK');raise

    def activate(self,authorization):
        verify(self.root)
        expected=file_hash(self.root/'manifest.json')
        if (authorization.get('manifest_sha256')!=expected or authorization.get('scope')!='identity_extension_generation_and_audit'
                or authorization.get('coordination_complete') is not True or not authorization.get('authorized_by')
                or not authorization.get('endpoints') or not 1<=authorization.get('concurrency_per_endpoint',0)<=32):
            raise ValueError('Explicit pinned coordination receipt required')
        with self.transaction():
            previous=self.db.execute("SELECT value FROM metadata WHERE key='authorization'").fetchone()
            if previous and json.loads(previous[0])!=authorization:raise ValueError('Authorization drift')
            self.db.execute('INSERT OR IGNORE INTO metadata VALUES (?,?)',('authorization',json.dumps(authorization)))
            self.db.execute("UPDATE metadata SET value='true' WHERE key='activated'")

    def claim(self,owner):
        if not owner:raise ValueError('Owner required')
        with self.transaction():
            if self.db.execute("SELECT value FROM metadata WHERE key='activated'").fetchone()[0]!='true':return None
            job=self.db.execute("SELECT * FROM jobs WHERE state='audit_pending' ORDER BY rowid LIMIT 1").fetchone()
            stage='audit'
            if job is None:
                stage='generate'
                job=self.db.execute("SELECT j.* FROM jobs j JOIN targets t ON j.language=t.language WHERE j.state='queued' AND t.retained+t.accepted_new+t.active<t.target AND t.attempts<t.max_attempts ORDER BY j.slot,j.language LIMIT 1").fetchone()
            if job is None:return None
            expected=request(job['language'],job['slot'],self.recipe)
            if job['id']!=expected['record']['id'] or json.loads(job['payload'])!=expected:
                raise ValueError('Generation request drift')
            if stage=='audit' and json.loads(job['audit_payload'])!=audit_payload(json.loads(job['candidate']),MODEL):
                raise ValueError('Audit request drift')
            self.db.execute('UPDATE jobs SET state=?,owner=? WHERE id=?',('auditing' if stage=='audit' else 'generating',owner,job['id']))
            if stage=='generate':self.db.execute('UPDATE targets SET active=active+1,attempts=attempts+1 WHERE language=?',(job['language'],))
            return dict(id=job['id'],stage=stage,payload=json.loads(job['audit_payload'] if stage=='audit' else job['payload']))

    def _terminal(self,job,state,error=None):
        self.db.execute('UPDATE jobs SET state=?,error=? WHERE id=?',(state,error,job['id']))
        self.db.execute('UPDATE targets SET active=active-1,accepted_new=accepted_new+? WHERE language=?',
                        (int(state=='accepted'),job['language']))
        group=self.db.execute('SELECT * FROM targets WHERE language=?',(job['language'],)).fetchone()
        queued=self.db.execute("SELECT count(*) FROM jobs WHERE language=? AND state='queued'",(job['language'],)).fetchone()[0]
        if group['retained']+group['accepted_new']+group['active']+queued<group['target'] and group['attempts']+queued<group['max_attempts']:
            payload=request(job['language'],group['next_slot'],self.recipe)
            self.db.execute('INSERT INTO jobs(id,language,slot,state,payload) VALUES(?,?,?,?,?)',
                (payload['record']['id'],job['language'],group['next_slot'],'queued',json.dumps(payload,ensure_ascii=False)))
            self.db.execute('UPDATE targets SET next_slot=next_slot+1 WHERE language=?',(job['language'],))

    def submit(self,key,owner,stage,result,renderer):
        """Worker supplies parsed complete response; failed HTTP calls use fail(), never this API."""
        if stage not in ('generate','audit'):raise ValueError('Unknown stage')
        column='generation_result' if stage=='generate' else 'audit_result'
        with self.transaction():
            job=self.db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
            if not job or job['owner']!=owner:raise ValueError('Job ownership mismatch')
            if job[column] is not None:
                if json.loads(job[column])!=result:raise ValueError('Completed response overwrite')
                return job['state']
            if job['state']!=('generating' if stage=='generate' else 'auditing'):raise ValueError('Stage not running')
            self.db.execute(f'UPDATE jobs SET {column}=? WHERE id=?',(json.dumps(result,ensure_ascii=False),key))
            if stage=='audit':
                try:validate_audit(result)
                except (ValueError,TypeError,AttributeError) as exc:
                    self._terminal(job,'invalid',repr(exc));return 'invalid'
                state='accepted' if result['keep'] else 'rejected';self._terminal(job,state);return state
            try:
                messages=result['messages'];validate_messages(messages)
                payload=json.loads(job['payload']);spec=json.loads(payload['request']['messages'][1]['content'])
                if any(m['role'] not in ('user','assistant') for m in messages) or sum(m['role']=='user' for m in messages)!=spec['user_turns']:
                    raise ValueError('Generation role/turn mismatch')
                if any(self.db.execute('SELECT 1 FROM heldouts WHERE fingerprint=?',(heldout_hash(m['content']),)).fetchone() for m in messages if m['role']=='user'):
                    raise ValueError('Heldout/development prompt overlap')
                fp=chat_fingerprint(messages);ph=prompt_hash(messages)
                if self.db.execute('SELECT 1 FROM seen WHERE fingerprint=?',(fp,)).fetchone() or self.db.execute('SELECT 1 FROM prompts WHERE language=? AND fingerprint=?',(job['language'],ph)).fetchone():
                    self._terminal(job,'duplicate');return 'duplicate'
                measurement=renderer(messages)
                candidate=dict(payload['record'],messages=messages,component='identity-xl-full-bp',rendered_tokens=measurement['rendered_tokens'])
                audit=audit_payload(candidate,MODEL)
                self.db.execute('INSERT INTO seen VALUES (?,?)',(fp,key));self.db.execute('INSERT INTO prompts VALUES (?,?,?)',(job['language'],ph,key))
                self.db.execute("UPDATE jobs SET state='audit_pending',candidate=?,audit_payload=?,owner=NULL WHERE id=?",(json.dumps(candidate,ensure_ascii=False),json.dumps(audit,ensure_ascii=False),key))
                return 'audit_pending'
            except (KeyError,ValueError,TypeError) as exc:
                self._terminal(job,'invalid',repr(exc));return 'invalid'

    def fail(self,key,owner,error):
        with self.transaction():
            job=self.db.execute('SELECT * FROM jobs WHERE id=?',(key,)).fetchone()
            if not job or job['owner']!=owner or job['state'] not in ('generating','auditing'):raise ValueError('Not owned running work')
            self._terminal(job,'failed',str(error))

    def status(self):
        return dict(activated=self.db.execute("SELECT value FROM metadata WHERE key='activated'").fetchone()[0]=='true',
            languages=[dict(r) for r in self.db.execute('SELECT * FROM targets ORDER BY language')],
            jobs=dict(self.db.execute('SELECT state,count(*) FROM jobs GROUP BY state')))


def main():
    parser=argparse.ArgumentParser(__doc__)
    parser.add_argument('action',choices=['prepare','verify','status','activate'])
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--exports',type=Path,default=Path('exports_dfm12'))
    parser.add_argument('--corrected',type=Path,default=CORRECTED)
    parser.add_argument('--holdout',type=Path,default=HOLDOUT)
    parser.add_argument('--authorization',type=Path)
    args=parser.parse_args()
    if args.action=='prepare':
        m=prepare(args.root,args.exports,args.corrected,args.holdout);print(json.dumps(m['languages'],indent=2));return
    if args.action=='verify':verify(args.root);print('verified');return
    with lock(args.root/'queue.lock'):
        queue=Queue(args.root)
        try:
            if args.action=='activate':
                if args.authorization is None:parser.error('activation requires --authorization')
                queue.activate(load(args.authorization))
            print(json.dumps(queue.status(),indent=2))
        finally:queue.close()


if __name__=='__main__':main()
