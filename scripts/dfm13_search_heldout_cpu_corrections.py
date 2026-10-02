"""Agent-authored heldout corrections with exact cache windows; no model calls."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sqlite3

import jinja2
from tokenizers import Tokenizer
from scripts import dfm13_search_calibration as base
from scripts import dfm13_search_manual_packet as packets
from scripts import dfm13_search_training_contract as contract
from scripts import dfm13_search_cached_repairs as repairs

ROOT = Path('data/dfm13/search-heldout-cpu-corrections-20261001-v2')


def paragraph(body, anchor, chars=1400):
    pos = body.index(anchor)
    start = body.rfind('\n', 0, pos) + 1
    end = body.find('\n\n', pos)
    if end == -1:
        end = len(body)
    end = min(end, start + chars)
    return dict(start=start, end=end, text=body[start:end])


def source_plan(prefix, pages):
    if prefix == 'bcb18033':
        url = next(u for u in pages if '/2.16/' in u)
        return url, ['The number of seconds newsboat shall wait', 'How many times newsboat shall try',
                     'If set, then user errors', 'parallel reload threads']
    if prefix == '918bee08':
        url = next(u for u in pages if 'linguistics.stackexchange.com' in u)
        return url, ["We don't know why Latin", 'not particularly well-supported', 'As Atamiri pointed out']
    if prefix == '118fd78c':
        url = next(u for u in pages if 'outmarketing.com.br' in u)
        return url, ['### **3. Mais conteúdo humanizado**', 'Vídeos curtos e longos']
    url = next(u for u in pages if 'TEMARIO-PRL-FOL.pdf' in u)
    return url, ['ASPECTOS BÁSICOS DEL REGLAMENTO DE PREVENCIÓN', 'Paralización de actividades', 'Disposiciones generales']


def answer(prefix, url):
    if prefix == 'bcb18033':
        return (
            'Separate two goals: diagnosing a long wait, and giving a genuinely slow feed more time. '
            'Newsboat documents `download-timeout` as the seconds to wait before giving up, and '
            '`download-retries` as the number of download attempts. Raising either can make a failing feed take longer, '
            'so do not raise them merely to investigate apparent blocking.\n\n'
            'For diagnosis, set `error-log "~/.newsboat/error.log"` to record feed errors, and identify which feed fails. '
            'Check your existing timeout/retry settings before increasing them. If the issue is genuinely a slow connection, '
            'a longer timeout may instead be an appropriate trade-off. `reload-threads` controls parallel reload threads '
            'when reloading all feeds; the log and your configuration can help distinguish waiting from a global failure. '
            'These are documented controls, not a diagnosis of the particular cause. '
            '[Newsboat manual](' + url + ').')
    if prefix == '918bee08':
        return (
            'The premise is not universal: a modern language can have elaborate inflection too. Losing noun or verb endings '
            'in a particular language history does not show that all languages become simpler as they age.\n\n'
            'The retrieved linguistic discussion does not establish a single causal explanation. It explicitly cautions '
            'that overall language complexity is difficult to compare. In particular, the claim that less morphology is '
            'necessarily compensated by more complex syntax is questioned there, not established as a rule. '
            'Forum suggestions about contact, sound change or population size should therefore be presented as proposals '
            'requiring language-specific evidence, not a demonstrated universal explanation.\n\n'
            'A better comparison would specify an ancient language and its later descendants and ask which inflections '
            'changed and why. The useful distinction is between changes in a particular grammatical system and a supposed '
            'general decline in complexity. [Discussion and its explicit cautions](' + url + ').')
    if prefix == '118fd78c':
        return (
            'Aqui estão cinco ideias de conteúdos sobre marketing digital para redes sociais, como propostas criativas, '
            'não como previsões ou tendências de um ano específico:\n\n'
            '1. **Carrossel: da atenção à ação.** Mostre um exemplo de publicação, uma chamada para ação e a página de destino.\n'
            '2. **Vídeo tutorial.** Demonstre como transformar uma dúvida frequente de clientes numa publicação útil.\n'
            '3. **Bastidores de uma campanha.** Apresente o objetivo, o rascunho e as decisões criativas, sem inventar resultados.\n'
            '4. **Perguntas da comunidade.** Convide seguidores a enviar dúvidas e transforme uma delas numa resposta explicativa.\n'
            '5. **Checklist antes de publicar.** Revise clareza, legibilidade, legenda e a ação que você pretende sugerir.\n\n'
            'Os formatos de vídeo e conteúdo humanizado aparecem no material consultado; os exemplos acima são sugestões '
            'criadas para o seu pedido, sem afirmar que eram tendências em março de 2025. '
            '[Material de referência](' + url + ').')
    return (
        'Te propongo diez términos para un crucigrama inspirado en ese tema; son conceptos plausibles, '
        'no una transcripción de tu libro. Para la cuadrícula puedes omitir las tildes.\n\n'
        '| Palabra | Pista |\n|---|---|\n'
        '| INTEGRACIÓN | Incorporación de la prevención a las actividades y decisiones de la empresa. |\n'
        '| COORDINACIÓN | Organización conjunta de actuaciones para que sean compatibles entre sí. |\n'
        '| PARTICIPACIÓN | Intervención de las personas trabajadoras en cuestiones preventivas. |\n'
        '| JERARQUÍA | Orden de niveles de responsabilidad dentro de una organización. |\n'
        '| EVALUACIÓN | Análisis que permite valorar los riesgos antes de planificar medidas. |\n'
        '| PLANIFICACIÓN | Organización anticipada de las actuaciones preventivas necesarias. |\n'
        '| PARALIZACIÓN | Detención de una actividad ante una situación de riesgo grave. |\n'
        '| SUBSANACIÓN | Corrección de una deficiencia o situación problemática detectada. |\n'
        '| INFRACCIÓN | Incumplimiento de una obligación o norma aplicable. |\n'
        '| CONTINGENCIA | Suceso posible para el que conviene prever una respuesta. |\n\n'
        'Las pistas son formulaciones didácticas, no definiciones legales exhaustivas. '
        'El material consultado trata la integración, evaluación, planificación y paralización de actividades. '
        '[Temario de PRL y FOL](' + url + ').')


def main():
    if ROOT.exists():
        raise ValueError('new root required')
    holds = contract.manual_holds()
    manifest = repairs.read(packets.ROOT / 'queue.json')
    info = repairs.read(contract.METADATA)['tokenizer_info']
    tokenizer = Tokenizer.from_file(info['tokenizer_path'])
    template = jinja2.Environment().from_string(Path(info['chat_template_path']).read_text())
    db = sqlite3.connect('file:' + str(base.CAMPAIGN / 'cache.sqlite') + '?mode=ro', uri=True)
    records = []; pins = {str(Path(__file__).resolve()): base.file_hash(Path(__file__)),
                          str(contract.MANUAL_RECEIPT.resolve()): base.file_hash(contract.MANUAL_RECEIPT)}
    for entry in manifest['cases']:
        prefix = entry['id'][:8]
        if prefix not in ('118fd78c', '81484873', 'bcb18033', '918bee08'):
            continue
        path = Path(entry['packet']); packet = repairs.read(path)
        pins[str(path.resolve())] = base.file_hash(path)
        url, anchors = source_plan(prefix, packet['pages'])
        available = db.execute('SELECT query,raw FROM searches WHERE owner=? AND status=?', (entry['id'], 'done')).fetchall()
        matched = None
        for query, raw in available:
            try:
                repairs.native_search(packet['candidate'], query)
                source_page = next(p for p in json.loads(raw)['data'] if p.get('url') == url)
                matched = query, raw, source_page
                break
            except (ValueError, StopIteration):
                pass
        if matched is None:
            raise ValueError('no native-query matched cached source')
        query, raw, page = matched
        excerpts = []
        for anchor in anchors:
            segment = paragraph(page['content'], anchor)
            if segment not in excerpts:
                excerpts.append(segment)
        pages = {url: dict(url=url, title=page.get('title', ''), excerpts=excerpts,
            body='\n\n'.join(p['text'] for p in excerpts),
            full_content_sha256=hashlib.sha256(page['content'].encode()).hexdigest())}
        job = dict(candidate=packet['candidate'], query=query, pages=pages,
                   cache_sha256=hashlib.sha256(raw).hexdigest(), hint='Agent-authored response to independent heldout finding.')
        candidate = repairs.repaired_candidate(job, answer(prefix, url))
        candidate['correction_provenance'].update(author_type='coding_agent_manual_draft', teacher_generated=False,
            source_candidate_content_sha256=base.digest(packet['candidate']),
            assessment_sha256=base.file_hash(contract.MANUAL_RECEIPT), original_hold_not_cleared=True)
        checked, _ = contract.strict_row(candidate, packet['sample']['prompt'])
        rendered = contract.rendered_targets(checked, tokenizer, template, info, 4096)
        folder = ROOT / entry['id']
        base.atomic(folder / 'candidate.json', candidate)
        base.atomic(folder / 'support.json', dict(pages=pages, raw_cache_sha256=job['cache_sha256'],
            source_packet_sha256=base.file_hash(path), original_hash_hold=next(h for h in holds if h['id'] == entry['id'])))
        base.atomic(folder / 'render.json', rendered)
        records.append(dict(id=entry['id'], candidate=str(folder / 'candidate.json'),
            candidate_sha256=base.file_hash(folder / 'candidate.json'), target_tokens=rendered[0]['target_tokens'],
            total_tokens=rendered[0]['total_tokens'], fits_student_context=rendered[0]['fits_student_context'],
            purpose='creative_task_with_retrieval_context' if prefix in ('118fd78c', '81484873') else 'source_grounded_answer',
            new_candidate_review='pending', admission_authorized=False))
    db.close()
    base.atomic(ROOT / 'queue.json', dict(cases=records, pins=pins, paid_calls=0, model_calls=0,
        original_holds_unchanged=True, admission_authorized=False))
    print(json.dumps(records))


if __name__ == '__main__':
    main()
