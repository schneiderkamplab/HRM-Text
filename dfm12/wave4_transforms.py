"""Native four-task transformations from pinned wave-four documents."""
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import heapq
import json
from pathlib import Path
from types import FunctionType

from . import transform as shared
from .baltic_sources_cpu import renderer
from .io import atomic, digest, file_hash, load, lock, rows, write_json
from .wave4_cpu import LANGUAGES, enqueue

ROOT = Path('data/dfm13/wave4')
PROMPTS = {
    'sq': ('shqip', 'Korrigjo gabimet në tekst.', 'Vazhdo tekstin; jep vetëm vazhdimin që mungon.', 'Plotëso <GAP>; jep vetëm tekstin që mungon.', 'Rivendos rendin origjinal të paragrafëve; jep tekstin e plotë pa numërim.'),
    'be': ('беларуская мова', 'Выпраў памылкі ў тэксце.', 'Працягні тэкст; падай толькі адсутны працяг.', 'Запоўні <GAP>; падай толькі адсутны тэкст.', 'Аднаві першапачатковы парадак абзацаў; падай поўны тэкст без нумарацыі.'),
    'bs': ('bosanski', 'Ispravi greške u tekstu.', 'Nastavi tekst; navedi samo nastavak koji nedostaje.', 'Popuni <GAP>; navedi samo tekst koji nedostaje.', 'Vrati izvorni redoslijed odlomaka; navedi cijeli tekst bez numeracije.'),
    'bg': ('български', 'Поправи грешките в текста.', 'Продължи текста; дай само липсващото продължение.', 'Попълни <GAP>; дай само липсващия текст.', 'Възстанови първоначалния ред на абзаците; дай целия текст без номериране.'),
    'hr': ('hrvatski', 'Ispravi pogreške u tekstu.', 'Nastavi tekst; navedi samo nastavak koji nedostaje.', 'Popuni <GAP>; navedi samo tekst koji nedostaje.', 'Vrati izvorni redoslijed odlomaka; navedi cijeli tekst bez numeriranja.'),
    'hu': ('magyar', 'Javítsd ki a szöveg hibáit.', 'Folytasd a szöveget; csak a hiányzó folytatást add meg.', 'Töltsd ki a <GAP> helyét; csak a hiányzó szöveget add meg.', 'Állítsd vissza a bekezdések eredeti sorrendjét; add meg a teljes szöveget számozás nélkül.'),
    'lb': ('Lëtzebuergesch', 'Verbesser d’Feeler am Text.', 'Setz den Text weider; gëff nëmmen déi feelend Fortsetzung un.', 'Fëll <GAP> aus; gëff nëmmen de feelenden Text un.', 'Stell déi ursprénglech Reiefolleg vun den Abschnitter erëm hier; gëff de ganzen Text ouni Nummeréierung un.'),
    'sr': ('српски', 'Исправи грешке у тексту.', 'Настави текст; наведи само наставак који недостаје.', 'Попуни <GAP>; наведи само текст који недостаје.', 'Врати изворни редослед пасуса; наведи цео текст без нумерације.'),
    'sk': ('slovenčina', 'Oprav chyby v texte.', 'Pokračuj v texte; uveď iba chýbajúce pokračovanie.', 'Doplň <GAP>; uveď iba chýbajúci text.', 'Obnov pôvodné poradie odsekov; uveď celý text bez číslovania.'),
    'sl': ('slovenščina', 'Popravi napake v besedilu.', 'Nadaljuj besedilo; navedi samo manjkajoče nadaljevanje.', 'Zapolni <GAP>; navedi samo manjkajoče besedilo.', 'Obnovi prvotni vrstni red odstavkov; navedi celotno besedilo brez oštevilčenja.'),
    'fa': ('فارسی', 'خطاهای متن را اصلاح کن.', 'متن را ادامه بده؛ فقط ادامهٔ حذف‌شده را بنویس.', 'جای <GAP> را پر کن؛ فقط متن حذف‌شده را بنویس.', 'ترتیب اصلی بندها را بازسازی کن؛ متن کامل را بدون شماره‌گذاری بنویس.'),
}
transform = FunctionType(shared.transform.__code__, dict(shared.transform.__globals__, PROMPTS=PROMPTS),
                         shared.transform.__name__, shared.transform.__defaults__)


def prepare(language):
    source = ROOT/'downloads'/('wikipedia-'+language)
    pin = load(source/'wave4-download.json')
    if pin['status'] != 'downloaded':
        raise ValueError('Wikipedia download not ready: '+language)
    files = sorted(source.glob(pin['config']+'/*.parquet'))
    dest = ROOT/'transforms'/('wikipedia-'+language)
    with lock(dest/'.lock'):
        receipt = dest/'receipt.json'
        if receipt.exists():
            result = load(receipt)
            if file_hash(dest/'candidates.jsonl') != result['sha256']:
                raise ValueError('Sealed transformation changed')
            return language, result
        targets = {task: int(value['target_per_language']*1.5)
                   for task, value in load('data/dfm12/baselines.json')['tasks'].items()}
        # A bounded hash sample across every file avoids first-file/topic bias.
        limit = max(targets.values())*3
        heap = []
        counts = Counter()
        for path in files:
            for ordinal, row in enumerate(rows(path)):
                counts['documents_scanned'] += 1
                text = row.get('text', '')
                if not 500 <= len(text) <= 2000000:
                    continue
                rank = int(digest([language, row['id'], 20261003])[:16], 16)
                if len(heap) >= limit and rank >= -heap[0][0]:
                    continue
                selected = shared.window(text, rank, max_chars=4500)
                if len(selected) < 500 or '\ufffd' in selected or sum(c.isalpha() for c in selected)/len(selected)<.6:
                    continue
                origin = dict(repo=pin['repo'], revision=pin['revision'],
                    config=pin['config'], file=str(path.relative_to(source)), row=ordinal,
                    id=row['id'], url=row.get('url'), title=row.get('title'),
                    paragraph_structure='original', window_seed=rank)
                entry = (-rank, str(row['id']), selected, origin)
                if len(heap) < limit:
                    heapq.heappush(heap, entry)
                else:
                    heapq.heapreplace(heap, entry)
        render = renderer()
        seen = set()
        with atomic(dest/'candidates.jsonl') as out, atomic(dest/'seeds.jsonl') as seeds:
            for _, _, text, origin in sorted(heap, reverse=True):
                key = digest(text)
                if key in seen:
                    continue
                seen.add(key)
                seeds.write(json.dumps(dict(id=key, text=text, language=language,
                    provenance=origin), ensure_ascii=False)+'\n')
                for task, target in targets.items():
                    if counts[task] >= target:
                        continue
                    try:
                        record = transform(text, language, task, origin, 20261003)
                        record['rendered_tokens'] = render.count(record['messages'])
                    except ValueError as exc:
                        counts['rejected:'+str(exc)] += 1
                        continue
                    record.update(admission_authorized=False, audit_status='pending')
                    out.write(json.dumps(record, ensure_ascii=False)+'\n')
                    counts[task] += 1
        result = dict(language=language, targets=targets, counts=counts,
            inputs={str(p):file_hash(p) for p in files}, sha256=file_hash(dest/'candidates.jsonl'),
            shortfalls={task:max(0,target-counts[task]) for task,target in targets.items()})
        write_json(receipt,result)
        print('TRANSFORMS', language, dict(counts), flush=True)
        return language, result


if __name__ == '__main__':
    import time
    # Wait only for the known download producer; missing/failed sources stay explicit.
    pending = set(LANGUAGES)
    while pending:
        ready = [lang for lang in sorted(pending)
                 if (ROOT/'downloads'/('wikipedia-'+lang)/'wave4-download.json').exists()
                 and load(ROOT/'downloads'/('wikipedia-'+lang)/'wave4-download.json')['status']=='downloaded']
        if not ready:
            raise RuntimeError('No ready documents for remaining languages: '+str(sorted(pending)))
        with ProcessPoolExecutor(max_workers=8) as pool:
            for language, _ in pool.map(prepare,ready):
                enqueue(ROOT, 'wikipedia-'+language, ROOT/'transforms'/('wikipedia-'+language)/'candidates.jsonl')
                pending.remove(language)
