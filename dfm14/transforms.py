"""Native-language draft prompts and exact, Unicode-safe transformation targets.

Every output remains audit-only, including prompt/native-language calibration.
"""
import random
import regex

from dfm12.io import digest

TASKS = ("denoising", "prefix-continuation", "span-filling", "paragraph-reordering")
PROMPTS = {
    "ga": ("Ceartaigh an téacs truaillithe.", "Lean leis an téacs; tabhair an chuid atá ar iarraidh amháin.", "Líon <GAP>; tabhair an téacs atá ar iarraidh amháin.", "Cuir na hailt san ord bunaidh; tabhair an téacs iomlán gan uimhriú."),
    "mt": ("Ikkoreġi t-test imħassar.", "Kompli t-test; agħti biss il-kontinwazzjoni nieqsa.", "Imla <GAP>; agħti biss it-test nieqes.", "Poġġi l-paragrafi fl-ordni oriġinali; agħti t-test kollu mingħajr numri."),
    "mk": ("Поправи го оштетениот текст.", "Продолжи го текстот; врати го само продолжението што недостасува.", "Пополни <GAP>; врати го само текстот што недостасува.", "Подреди ги пасусите по првобитниот редослед; врати го целиот текст без нумерирање."),
    "eu": ("Zuzendu hondatutako testua.", "Jarraitu testua; eman falta den jarraipena soilik.", "Bete <GAP>; eman falta den testua soilik.", "Jarri paragrafoak jatorrizko ordenan; eman testu osoa zenbakirik gabe."),
    "gl": ("Corrixe o texto danado.", "Continúa o texto; devolve só a continuación que falta.", "Enche <GAP>; devolve só o texto que falta.", "Ordena os parágrafos na orde orixinal; devolve o texto completo sen numeración."),
    "cy": ("Cywira'r testun sydd wedi'i ddifrodi.", "Parha'r testun; dychwel y parhad coll yn unig.", "Llenwa <GAP>; dychwel y testun coll yn unig.", "Rho'r paragraffau yn eu trefn wreiddiol; dychwel y testun cyfan heb rifau."),
    "ru": ("Исправьте повреждённый текст.", "Продолжите текст; верните только недостающее продолжение.", "Заполните <GAP>; верните только пропущенный текст.", "Расположите абзацы в исходном порядке; верните полный текст без нумерации."),
    "tr": ("Bozulmuş metni düzelt.", "Metni devam ettir; yalnızca eksik devamını ver.", "<GAP> boşluğunu doldur; yalnızca eksik metni ver.", "Paragrafları özgün sırasına koy; tam metni numarasız ver."),
    "zh": ("修复损坏的文本。", "续写文本，只输出缺失的后续部分。", "填补<GAP>，只输出缺失的文本。", "将段落恢复为原始顺序，输出不带编号的完整文本。"),
    "ar": ("صحح النص التالف.", "أكمل النص وأعد الجزء الناقص فقط.", "املأ <GAP> وأعد النص الناقص فقط.", "رتب الفقرات حسب ترتيبها الأصلي وأعد النص كاملاً دون ترقيم."),
    "ja": ("破損した文章を修正してください。", "文章を続け、欠けている続きだけを出力してください。", "<GAP>を埋め、欠けている文章だけを出力してください。", "段落を元の順序に並べ、番号なしで全文を出力してください。"),
    "id": ("Perbaiki teks yang rusak.", "Lanjutkan teks; berikan hanya kelanjutan yang hilang.", "Isi <GAP>; berikan hanya teks yang hilang.", "Susun paragraf dalam urutan aslinya; berikan teks lengkap tanpa penomoran."),
    "ko": ("손상된 글을 수정하세요.", "글을 이어 쓰고 빠진 뒷부분만 출력하세요.", "<GAP>을 채우고 빠진 글만 출력하세요.", "문단을 원래 순서로 정렬하고 번호 없이 전체 글을 출력하세요."),
    "hi": ("बिगड़े हुए पाठ को ठीक करें।", "पाठ को आगे बढ़ाएँ; केवल छूटा हुआ अगला भाग दें।", "<GAP> भरें; केवल छूटा हुआ पाठ दें।", "अनुच्छेदों को मूल क्रम में रखें; बिना क्रमांक के पूरा पाठ दें।"),
    "vi": ("Sửa văn bản bị lỗi.", "Viết tiếp văn bản; chỉ trả lại phần tiếp nối còn thiếu.", "Điền <GAP>; chỉ trả lại phần văn bản còn thiếu.", "Sắp xếp các đoạn theo thứ tự ban đầu; trả lại toàn bộ văn bản không đánh số."),
    "he": ("תקן את הטקסט הפגום.", "המשך את הטקסט; החזר רק את ההמשך החסר.", "מלא את <GAP>; החזר רק את הטקסט החסר.", "סדר את הפסקאות בסדר המקורי; החזר את הטקסט המלא ללא מספור."),
}

# Reuse previously reviewed native prompts without changing the old campaigns.
from dfm12.transform import PROMPTS as _PREVIOUS_PROMPTS
from dfm12.wave4_transforms import PROMPTS as _WAVE4_PROMPTS
PROMPTS.update({k: _PREVIOUS_PROMPTS[k][1:] for k in ('fo', 'pl')})
PROMPTS['fa'] = _WAVE4_PROMPTS['fa'][1:]


def window(text, tokenizer, seed, max_tokens=1500):
    """Choose a contiguous paragraph/sentence window, never decode partial tokens."""
    paragraphs = [p.strip() for p in regex.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        raise ValueError("empty_document")
    rng = random.Random(seed)
    start = rng.randrange(len(paragraphs))
    selected = []
    for paragraph in paragraphs[start:]:
        combined = "\n\n".join(selected + [paragraph])
        if len(tokenizer.encode(combined, add_special_tokens=False).ids) <= max_tokens:
            selected.append(paragraph)
        elif selected:
            break
        else:
            ends = [m.end() for m in regex.finditer(r"[.!?。！？।](?:\s*|$)", paragraph)]
            if not ends or ends[-1] != len(paragraph):
                ends.append(len(paragraph))
            start = rng.choice([0] + ends[:-1])
            last = start
            for end in ends:
                if end <= start:
                    continue
                if len(tokenizer.encode(paragraph[start:end], add_special_tokens=False).ids) > max_tokens:
                    break
                last = end
            if last > start:
                selected.append(paragraph[start:last])
            break
    text = "\n\n".join(selected)
    if len(text) < 250:
        raise ValueError("no_sufficient_complete_window")
    return text


def transform(text, language, task, provenance):
    if language not in PROMPTS:
        # Prior native prompts, not English fallbacks, for inherited-language increments.
        from dfm12.transform import PROMPTS as previous
        if language not in previous:
            raise ValueError("native_prompt_pending")
        prompts = previous[language][1:]
    else:
        prompts = PROMPTS[language]
    if "<GAP>" in text:
        raise ValueError("reserved_gap_marker")
    rng = random.Random(int(digest([text, task])[:16], 16))
    if task == "paragraph-reordering":
        parts = text.split("\n\n")
        if len(parts) < 3 or len(set(parts)) != len(parts):
            raise ValueError("no_three_distinct_source_paragraphs")
        order = list(range(len(parts)))
        rng.shuffle(order)
        if order == list(range(len(parts))):
            order = order[1:] + order[:1]
        corrupted = "\n\n".join(f"[{i+1}] {parts[j]}" for i,j in enumerate(order))
        answer = text
        details = dict(paragraph_order=order)
    elif task == "denoising":
        units = regex.findall(r"\X", text)
        possible = [i for i,u in enumerate(units) if any(c.isalpha() for c in u)]
        if len(possible) < 20:
            raise ValueError("too_few_letters")
        removed = set(rng.sample(possible, max(1, len(possible)//50)))
        corrupted = "".join(u for i,u in enumerate(units) if i not in removed)
        answer, details = text, dict(removed_grapheme_indices=sorted(removed))
    else:
        # Whitespace boundaries for spaced scripts; sentence boundaries for CJK.
        pattern = r"(?<=[。！？.!?])" if language in {"zh", "ja"} else r"\s+"
        boundaries = [m.start() for m in regex.finditer(pattern, text) if 0 < m.start() < len(text)]
        if len(boundaries) < 4:
            raise ValueError("too_few_native_boundaries")
        i = rng.randrange(max(1,len(boundaries)//4), max(2,len(boundaries)//2))
        start = boundaries[i]
        end = len(text) if task == "prefix-continuation" else boundaries[min(len(boundaries)-1, i+max(1,len(boundaries)//10))]
        corrupted = text[:start] if task == "prefix-continuation" else text[:start] + "<GAP>" + text[end:]
        answer = text[start:end]
        details = dict(start=start, end=end)
        assert text[:start] + answer + text[end:] == text
    return dict(id=digest([language,task,text]), language=language, task=task,
        messages=[dict(role="user",content=prompts[TASKS.index(task)]+"\n\n"+corrupted),
                  dict(role="assistant",content=answer)], provenance=provenance,
        audit_context=dict(original=text, transformation=details),
        admission_authorized=False, training_ready=False)
