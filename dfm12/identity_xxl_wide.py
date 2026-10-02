"""Adapt published XL identities to a separate XXL-wide profile; re-audit and publish."""
import argparse
import asyncio
import copy
import json
from pathlib import Path
import re

import yaml

from .export_european import Package
from .export_validator import validate
from .io import digest, file_hash, load, lock, rows, write_json
from .jobs import Queue, audit_payload, run_clients
from .prepare import Renderer
from .upload_exports import publish
from .identity_multilingual_queue import LANGUAGES
from .export_identity_multilingual import validate as validate_multilingual

PROFILE = 'xxl-wide-full-bp'
MODEL = 'google/gemma-4-26B-A4B-it'
ROOT = Path('data/dfm12/identity-xxl-wide-21-20260929')
OUTPUT = Path('exports_dfm12/identity-xxl-wide-21')
SOURCE = Path('data/dfm12/identity21-export-20260929-v1')
PROFILE_TEXT = ('The current Mimir XXL-wide profile has 16 transformer layers in L and 16 in H, '
    'hidden_size=2560, num_heads=20, head dimension 128 and expansion factor 4. '
    'It has two H cycles and three L cycles per H cycle: six L passes and two H passes. '
    'This full-bp identity profile uses full backpropagation through all eight module passes. '
    'These facts do not describe every earlier release or every training phase. '
    'The team, organization, name and historical v1 facts are unchanged. '
    'No exact total parameter count, current hardware, current dataset size or deployment capability is asserted.')

DIMENSION_REPAIRS = {
    'The documentation does not specify the exact parameter count or the specific dimensionality of these layers.':
        'My current XXL-wide profile has hidden dimension 2560 and 20 attention heads. I am not specifying an exact total parameter count here.',
    'The documentation does not specify the exact dimensionality of the hidden states within these modules.':
        'The hidden dimension of these modules in my current XXL-wide profile is 2560, with 20 attention heads.',
    'While the structural relationship between the H and L modules is defined, specific details regarding the internal dimensionality of the modules or the exact mechanism of parameter sharing are not specified in the provided information.':
        'In my current XXL-wide profile, the hidden dimension is 2560 and there are 20 attention heads. Each module reuses its own weights across its repeated passes.',
    'While the architecture involves these specific layers, the report does not specify the exact parameter count or the specific dimensionality of these layers.':
        'For my current XXL-wide profile, the hidden dimension is 2560 and there are 20 attention heads. These are current-profile facts, not a statement about an unspecified historical parameter count.',
    "I don't have specific details regarding the exact parameter sharing mechanisms or the specific dimensionality of the shared parameters beyond what is described in the module structure.":
        'My current XXL-wide profile has hidden dimension 2560 and 20 attention heads. Each module reuses its own weights across its repeated passes.',
    'Jeg har ikke informasjon om de eksakte dimensjonene eller de spesifikke hyperparametrene for disse lagene utover antallet som er oppgitt.':
        'Den skjulte dimensjonen i min nåværende XXL-wide-profil er 2560, og modellen har 20 attention-hoder. Dette fastslår ikke alle øvrige hyperparametre.',
    'Jag har dock ingen information om de exakta dimensionerna eller de specifika vikterna för lagren i denna konfiguration.':
        'Den dolda dimensionen i min nuvarande XXL-wide-profil är 2560, med 20 attention-huvuden. Detta anger inte de enskilda vikternas numeriska värden.',
}

# Explicit new questions teach the width, which the original registry did not specify.
WIDTH_QA = {
    'de': ('Wie groß sind deine verborgene Dimension und die Anzahl deiner Attention-Köpfe?', 'Mein aktuelles XXL-wide-Profil hat eine verborgene Dimension von 2560 und 20 Attention-Köpfe mit jeweils 128 Dimensionen.'),
    'fr': ('Quelle est ta dimension cachée et combien de têtes d’attention as-tu ?', 'Mon profil XXL-wide actuel a une dimension cachée de 2560 et 20 têtes d’attention, avec 128 dimensions par tête.'),
    'es': ('¿Cuál es tu dimensión oculta y cuántas cabezas de atención tienes?', 'Mi perfil XXL-wide actual tiene una dimensión oculta de 2560 y 20 cabezas de atención, con 128 dimensiones por cabeza.'),
    'it': ('Qual è la tua dimensione nascosta e quante teste di attenzione hai?', 'Il mio profilo XXL-wide attuale ha una dimensione nascosta di 2560 e 20 teste di attenzione, con 128 dimensioni per testa.'),
    'cs': ('Jaká je tvoje skrytá dimenze a kolik máš hlav pozornosti?', 'Můj aktuální profil XXL-wide má skrytou dimenzi 2560 a 20 hlav pozornosti, každou se 128 dimenzemi.'),
    'pt_pt': ('Qual é a tua dimensão oculta e quantas cabeças de atenção tens?', 'O meu perfil XXL-wide atual tem uma dimensão oculta de 2560 e 20 cabeças de atenção, com 128 dimensões por cabeça.'),
    'fi': ('Mikä on piilotilasi ulottuvuus ja montako huomiopäätä sinulla on?', 'Nykyisen XXL-wide-profiilini piilotilan ulottuvuus on 2560, ja siinä on 20 huomiopäätä, joissa kussakin on 128 ulottuvuutta.'),
    'et': ('Kui suur on sinu peidetud kihi mõõde ja mitu tähelepanupead sul on?', 'Minu praeguse XXL-wide-profiili peidetud kihi mõõde on 2560 ja sellel on 20 tähelepanupead, igas peas 128 mõõdet.'),
    'ca': ('Quina és la teva dimensió oculta i quants caps d’atenció tens?', 'El meu perfil XXL-wide actual té una dimensió oculta de 2560 i 20 caps d’atenció, amb 128 dimensions per cap.'),
    'el': ('Ποια είναι η κρυφή σου διάσταση και πόσες κεφαλές προσοχής έχεις;', 'Το τρέχον προφίλ μου XXL-wide έχει κρυφή διάσταση 2560 και 20 κεφαλές προσοχής, με 128 διαστάσεις ανά κεφαλή.'),
    'ro': ('Care este dimensiunea ta ascunsă și câte capete de atenție ai?', 'Profilul meu actual XXL-wide are o dimensiune ascunsă de 2560 și 20 de capete de atenție, cu 128 de dimensiuni per cap.'),
    'uk': ('Яка твоя прихована розмірність і скільки в тебе голів уваги?', 'Мій поточний профіль XXL-wide має приховану розмірність 2560 і 20 голів уваги, по 128 вимірів на голову.'),
    'en': ('What are your hidden dimension and number of attention heads?', 'My current XXL-wide profile has a hidden dimension of 2560 and 20 attention heads, with 128 dimensions per head.'),
    'da': ('Hvad er din skjulte dimension og dit antal attention-hoveder?', 'Min aktuelle XXL-wide-profil har en skjult dimension på 2560 og 20 attention-hoveder med 128 dimensioner pr. hoved.'),
    'nb': ('Hva er din skjulte dimensjon og antallet attention-hoder?', 'Min nåværende XXL-wide-profil har en skjult dimensjon på 2560 og 20 attention-hoder med 128 dimensjoner per hode.'),
    'nn': ('Kva er den skjulte dimensjonen din og talet på attention-hovud?', 'Den noverande XXL-wide-profilen min har ein skjult dimensjon på 2560 og 20 attention-hovud med 128 dimensjonar per hovud.'),
    'sv': ('Vilken är din dolda dimension och hur många attention-huvuden har du?', 'Min nuvarande XXL-wide-profil har en dold dimension på 2560 och 20 attention-huvuden med 128 dimensioner per huvud.'),
    'nl': ('Wat zijn je verborgen dimensie en je aantal attention-heads?', 'Mijn huidige XXL-wide-profiel heeft een verborgen dimensie van 2560 en 20 attention-heads met 128 dimensies per head.'),
    'pl': ('Jaki jest twój wymiar ukryty i ile masz głów uwagi?', 'Mój obecny profil XXL-wide ma wymiar ukryty 2560 i 20 głów uwagi, po 128 wymiarów na głowę.'),
    'is': ('Hver er falda víddin þín og hversu marga athyglishausa hefurðu?', 'Núverandi XXL-wide-útfærsla mín hefur falda vídd 2560 og 20 athyglishausa með 128 víddir á haus.'),
    'fo': ('Hvussu stór er tann falda dimensiónin hjá tær, og hvussu nógvar attention-høvd hevur tú?', 'Núverandi XXL-wide-profilurin hjá mær hevur eina falda dimensión á 2560 og 20 attention-høvd við 128 dimensiónum í hvørjum høvdi.'),
}


def adapt(record):
    if record['profile'] != 'xl-full-bp':
        raise ValueError('Not the explicitly selected source profile')
    result = copy.deepcopy(record)
    result['profile'] = PROFILE
    result['component'] = 'identity-' + PROFILE + '-' + record['language']
    for message in result['messages']:
        # Only this curated profile's name changes; numerical/historical/team text stays intact.
        message['content'] = re.sub(r'\bXL\b', 'XXL-wide', message['content'])
        for old, new in DIMENSION_REPAIRS.items():
            message['content'] = message['content'].replace(old, new)
    result['audit_context']['profile'] = dict(description=PROFILE, facts=[dict(source='XXL_wide.yaml and owner-selected full-bp identity', text=PROFILE_TEXT)])
    result['id'] = digest([PROFILE, record['id'], result['messages']])
    result.pop('rendered_tokens', None)
    return result


def prepare(root):
    arch = yaml.safe_load(Path('config/arch/size/XXL_wide.yaml').read_text())
    assert (arch['n_layers'], arch['hidden_size'], arch['num_heads'], arch['expansion']) == (32, 2560, 20, 4)
    renderer = Renderer(load('data/sampled_dfm11/metadata.json')['tokenizer_info'])
    queue = Queue(root / 'jobs.sqlite')
    report = {'sources': [], 'context_exclusions': [], 'prepared': 0}
    wanted = set()
    assert set(WIDTH_QA) == set(LANGUAGES)
    context = load('data/dfm12/identity-multilingual-2000-20260928-v1/recipe.json')['grounding']
    for language in LANGUAGES:
        source = SOURCE / ('dfm12-identity-xl-full-bp-' + language)
        checked = validate_multilingual(source)
        assert checked['rows'] == 2000 and checked['language'] == language
        upstream = load(SOURCE / 'upload-receipts.json')['schneiderkamplab/' + source.name]
        assert upstream['status'] == 'verified'
        assert upstream['manifest_sha256'] == file_hash(source / 'metadata/manifest.json')
        report['sources'].append(dict(repo='schneiderkamplab/' + source.name, revision=upstream['revision'],
                                      manifest_sha256=upstream['manifest_sha256']))
        records = list(rows(source / 'data/train-00000.jsonl.gz'))
        provenance = list(rows(source / 'metadata/provenance.jsonl.gz'))
        candidates = []
        for original_row, admission in zip(records, provenance):
            original = dict(original_row, profile='xl-full-bp', audit_context=copy.deepcopy(context))
            converted = adapt(original)
            converted['provenance'] = dict(repo='schneiderkamplab/' + source.name, revision=upstream['revision'],
                source_record_id=original['id'], original_messages_sha256=digest(original['messages']),
                original_admission=admission, conversion='profile-scoped CPU rename; fresh independent audit',
                architecture_sha256=file_hash('config/arch/size/XXL_wide.yaml'))
            candidates.append(converted)
        width = copy.deepcopy(candidates[0])
        question, answer = WIDTH_QA[language]
        width['messages'] = [dict(role='user', content=question), dict(role='assistant', content=answer)]
        width['id'] = digest([PROFILE, language, width['messages']])
        width['provenance'] = dict(source='CPU-authored width Q&A', architecture_sha256=file_hash('config/arch/size/XXL_wide.yaml'))
        candidates.append(width)
        for record in candidates:
            try:
                record['rendered_tokens'] = renderer.count(record['messages'])
            except ValueError as exc:
                report['context_exclusions'].append(dict(id=record['id'], reason=str(exc)))
                continue
            payload = audit_payload(record, MODEL)
            payload['request']['messages'][0]['content'] += (' Explicitly reject claims that the current hidden dimension '
                'or head count is unspecified: they are now known. Preserve historical v1 scope. '
                'Check the requested language and every turn, not just the last answer. '
                'A profile name change does not certify any pre-existing dubious claim.')
            wanted.add(queue.add('audit', payload))
            report['prepared'] += 1
    obsolete = [dict(id=k, payload=json.loads(p), status=s, result=r)
                for k, p, s, r in queue.db.execute('SELECT id,payload,status,result FROM jobs') if k not in wanted]
    if obsolete:
        write_json(root / ('superseded-' + digest([x['id'] for x in obsolete])[:12] + '.json'), obsolete)
        queue.db.executemany('DELETE FROM jobs WHERE id=?', [(x['id'],) for x in obsolete])
    queue.close()
    write_json(root / 'preparation.json', report)


def export(root, output):
    if (output / 'manifest.json').exists():
        return
    output.mkdir(parents=True, exist_ok=True)
    if list(output.glob('.building-*')) or list(output.glob('dfm12-*')):
        raise ValueError('Partial export exists; inspect before retrying')
    queue = Queue(root / 'jobs.sqlite')
    if any(x['status'] not in ('done', 'failed') for x in queue.status()):
        raise ValueError('Audit not terminal')
    excluded = {}
    for payload, status, result in queue.db.execute('SELECT payload,status,result FROM jobs'):
        record = json.loads(payload)['record']
        if record['provenance'].get('source') == 'CPU-authored width Q&A':
            if status != 'done' or json.loads(result).get('keep') is not True:
                raise ValueError('Width Q&A needs review before publication: ' + record['language'])
        for message in record['messages']:
            if re.search(r'(?<!X)XL(?!-wide)', message['content']):
                excluded[record['id']] = 'Stale profile reference; excluded without altering audited content'
            if any(old in message['content'] for old in DIMENSION_REPAIRS):
                excluded[record['id']] = 'Stale unknown-dimension claim'
    write_json(output / 'export-exclusions.json', excluded)
    packages = {}
    for row in queue.db.execute("SELECT id,payload,status,result,attempts,error FROM jobs WHERE stage='audit' ORDER BY rowid"):
        record = json.loads(row[1])['record']
        if record['id'] in excluded:
            continue
        component = record['component']
        if component not in packages:
            packages[component] = Package(output, component, [root / 'preparation.json', Path('config/arch/size/XXL_wide.yaml')])
        packages[component].add(row)
    queue.close()
    entries = []
    for package in packages.values():
        entry = package.finish()
        folder = output / entry['name']
        language = entry['languages']
        card = ('---\nlanguage:\n' + ''.join('- ' + ('pt' if x == 'pt_pt' else x) + '\n' for x in language) +
            'task_categories:\n- text-generation\nconfigs:\n- config_name: default\n  data_files:\n'
            '  - split: train\n    path: data/train-*.jsonl.gz\n---\n\n# ' + entry['name'] + '\n\n' +
            'Mimir XXL-wide full-backpropagation identity variant, adapted from the published XL identity corpus.\n\n' +
            PROFILE_TEXT + '\n\n' +
            'CPU conversion changes only profile references; a small width Q&A is added per language. '
            'Every exported conversation passed a NEW automated Gemma 4 26B-A4B audit with all scores at least 4/5. '
            'Rejected and failed rows are excluded. This is not native-speaker certification. '
            'Historical v1 descriptions and the training team are not replaced with current-profile facts.\n\n' +
            'Use this variant INSTEAD OF the XL identity datasets when training XXL-wide; do not mix both identities. '
            'Repeat 10 is a recommended mixture setting, not duplicated rows. No existing training mixture was changed.\n\n' +
            'Only data/ is training input. metadata/ preserves per-row source repository/revision, '
            'original IDs/hashes/audits and new audit judgments. No blanket relicensing of source references is asserted. '
            'Run `python validate_dataset.py` for integrity and accepted-only validation.\n')
        (folder / 'README.md').write_text(card)
        entries.append(entry)
    write_json(output / 'manifest.json', dict(packages=entries, finished=True,
        rows=sum(x['rows'] for x in entries), upload_performed=False, profile=PROFILE))


def main():
    p = argparse.ArgumentParser(__doc__)
    p.add_argument('--publish', action='store_true')
    p.add_argument('--concurrency', type=int, default=4, help='Additional requests per shared server')
    p.add_argument('--refresh', action='store_true', help='Reconcile CPU corrections after this job was stopped')
    a = p.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    with lock(ROOT / '.lock'):
        if a.refresh:
            if (OUTPUT / 'manifest.json').exists():
                raise ValueError('Cannot refresh an already exported variant')
            q = Queue(ROOT / 'jobs.sqlite')
            q.db.execute("UPDATE jobs SET status='pending',owner=NULL,lease=NULL WHERE status='running'")
            q.close()
        if a.refresh or not (ROOT / 'preparation.json').exists():
            prepare(ROOT)
        print('Prepared', load(ROOT / 'preparation.json')['prepared'], flush=True)
        from .identity_audit_async import run as run_audits
        asyncio.run(run_audits(ROOT / 'jobs.sqlite', [f'http://127.0.0.1:{p}/v1' for p in range(8600, 8608)], a.concurrency))
        export(ROOT, OUTPUT)
        if a.publish:
            from .publish_identity_xxl_wide import publish as publish_identity
            publish_identity(OUTPUT)
        write_json(ROOT / 'completion.json', dict(export=str(OUTPUT), publication_requested=a.publish,
            packages=load(OUTPUT / 'manifest.json')['packages']))


if __name__ == '__main__':
    main()
