"""Production copy of controlled stages; automatic source review is explicit.

Derived from the frozen experimental adapter without modifying its historical file.
Only source-review provenance acceptance and the policy ID differ.
"""
import hashlib
import json
import math
import re
import time
from pathlib import Path

import httpx
from audit_pipeline.dfm14 import Audit
from scripts.dfm16_story_calibration import immutable, sha
from dfm12.io import file_hash, load, rows

LANGUAGES = ('da', 'en', 'hi', 'ja')
TASKS = ('creative', 'summary', 'qa', 'rewrite', 'revision')
POLICY = 'simplestories-production-staged-v1'

# Three provisional assistant-manual native request variants per task family.
TEMPLATES = {
'en': {
 'creative': ['Write a story about {topic}.', 'Create a fictional story about {topic}.', 'Tell a story about {topic}.'],
 'summary': ['Summarize the following story without adding facts.', 'Write a concise summary of this story. Preserve the main events.', 'Summarize the main events in the following text.'],
 'qa': ['Answer this question using only the story: {question}', 'Using the following story, answer: {question}', 'Read the story and answer the question: {question}'],
 'rewrite': ['Rewrite the narration in {operation}. Preserve all events.', 'Change the narration to {operation}, keeping the facts unchanged.', 'Retell this story in {operation}. Do not change the events.'],
 'revision': ['Write a story about {topic} in exactly three paragraphs.', 'Create a three-paragraph story about {topic}.', 'Tell a story about {topic}. Use exactly three paragraphs.'],
 'limit': 'Length: {lo}–{hi} words, counted by whitespace.',
 'edit': 'Change only paragraph {paragraph}: {change}. Return only that paragraph, with no heading. The edited paragraph must contain {lo}–{hi} words, counted by whitespace. The complete story must remain {total_lo}–{total_hi} words.',
 'undo': 'Restore the original first paragraph exactly. Retain the edited final paragraph and the unchanged middle paragraph. Return the complete story. Length: {lo}–{hi} words, counted by whitespace.',
 'operation': 'the present tense',
},
'da': {
 'creative': ['Skriv en historie om {topic}.', 'Find på en fortælling om {topic}.', 'Fortæl en historie om {topic}.'],
 'summary': ['Sammenfat følgende historie uden at tilføje nye oplysninger.', 'Skriv et kort resumé af historien. Bevar de vigtigste begivenheder.', 'Gengiv hovedbegivenhederne i følgende tekst i et kort resumé.'],
 'qa': ['Besvar spørgsmålet ud fra historien: {question}', 'Brug kun historien til at besvare dette spørgsmål: {question}', 'Læs historien, og besvar spørgsmålet: {question}'],
 'rewrite': ['Omskriv fortællingen til {operation}. Bevar alle begivenheder.', 'Skriv fortællingen i {operation} uden at ændre oplysningerne.', 'Gengiv historien i {operation}. Begivenhederne skal være de samme.'],
 'revision': ['Skriv en historie om {topic} i præcis tre afsnit.', 'Find på en fortælling om {topic}. Brug præcis tre afsnit.', 'Fortæl en historie om {topic}, fordelt på præcis tre afsnit.'],
 'limit': 'Længde: {lo}–{hi} ord, talt efter mellemrum.',
 'edit': 'Ret kun afsnit {paragraph}: {change}. Svar kun med dette afsnit uden overskrift. Afsnittet skal være på {lo}–{hi} ord, talt efter mellemrum. Hele historien skal fortsat være på {total_lo}–{total_hi} ord.',
 'undo': 'Gendan det oprindelige første afsnit ordret. Bevar det redigerede sidste afsnit og det uændrede midterafsnit. Gengiv hele historien. Længde: {lo}–{hi} ord, talt efter mellemrum.',
 'operation': 'nutid',
},
'hi': {
 'creative': ['विषय: {topic}\nइस विषय पर एक कहानी लिखें।', 'विषय: {topic}\nदिए गए विषय पर आधारित एक काल्पनिक कहानी लिखें।', 'विषय: {topic}\nइस विषय को लेकर एक कहानी सुनाएँ।'],
 'summary': ['नीचे दी गई कहानी का सारांश लिखें। कोई नया तथ्य न जोड़ें।', 'मुख्य घटनाओं को बनाए रखते हुए इस कहानी का संक्षिप्त सारांश लिखें।', 'नीचे दिए गए पाठ की मुख्य घटनाओं को संक्षेप में लिखें।'],
 'qa': ['केवल कहानी के आधार पर इस प्रश्न का उत्तर दें: {question}', 'नीचे दी गई कहानी पढ़कर उत्तर दें: {question}', 'इस प्रश्न का उत्तर कहानी से प्राप्त जानकारी के आधार पर दें: {question}'],
 'rewrite': ['कहानी के वर्णन को {operation} में लिखें। सभी घटनाएँ वही रखें।', 'तथ्यों को बदले बिना कहानी का वर्णन {operation} में बदलें।', 'इस कहानी को {operation} में दोबारा लिखें। घटनाएँ न बदलें।'],
 'revision': ['विषय: {topic}\nइस विषय पर ठीक तीन अनुच्छेदों में कहानी लिखें।', 'विषय: {topic}\nइस विषय पर आधारित कहानी लिखें। ठीक तीन अनुच्छेदों का प्रयोग करें।', 'विषय: {topic}\nइस विषय को लेकर तीन अनुच्छेदों की कहानी लिखें।'],
 'limit': 'लंबाई: {lo}–{hi} शब्द। शब्दों की गिनती रिक्त स्थानों के आधार पर करें।',
 'edit': 'केवल अनुच्छेद {paragraph} बदलें: {change}। उत्तर में केवल वही अनुच्छेद दें, कोई शीर्षक नहीं। बदले गए अनुच्छेद की लंबाई {lo}–{hi} शब्द होनी चाहिए। पूरी कहानी की लंबाई {total_lo}–{total_hi} शब्द बनी रहनी चाहिए। शब्दों को रिक्त स्थानों के आधार पर गिनें।',
 'undo': 'पहला अनुच्छेद मूल रूप में अक्षरशः वापस रखें। बदला हुआ अंतिम अनुच्छेद और अपरिवर्तित बीच का अनुच्छेद बनाए रखें। पूरी कहानी दें। लंबाई: {lo}–{hi} शब्द, रिक्त स्थानों के आधार पर गिने हुए।',
 'operation': 'वर्तमान काल',
},
'ja': {
 'creative': ['{topic}について物語を書いてください。', '{topic}を題材にした架空の物語を作ってください。', '{topic}をテーマに物語を書いてください。'],
 'summary': ['次の物語を、新しい事実を加えずに要約してください。', '主な出来事を保ちながら、この物語を短く要約してください。', '次の文章の主な出来事を簡潔にまとめてください。'],
 'qa': ['物語だけを根拠に、次の質問に答えてください。{question}', '次の物語を読んで質問に答えてください。{question}', '物語に書かれた情報を使って答えてください。{question}'],
 'rewrite': ['地の文を{operation}に書き換えてください。出来事は変えないでください。', '事実を変えずに、物語の地の文を{operation}にしてください。', 'この物語の地の文を{operation}で書き直してください。すべての出来事を保ってください。'],
 'revision': ['{topic}について、ちょうど三つの段落で物語を書いてください。', '{topic}を題材にした物語を三段落で作ってください。', '{topic}をテーマに物語を書いてください。段落数は必ず三つにしてください。'],
 'limit': '長さは{lo}～{hi}文字です。空白と改行を除き、句読点も一文字として数えてください。',
 'edit': '第{paragraph}段落だけを変更してください：{change}。見出しを付けず、その段落だけを返してください。この段落は{lo}～{hi}文字、物語全体は{total_lo}～{total_hi}文字にしてください。空白と改行を除き、句読点も数えてください。',
 'undo': '最初の段落を元の文章に一字一句戻してください。変更済みの最後の段落と、変更していない中段落はそのまま保ってください。物語全体を返してください。長さは{lo}～{hi}文字です。空白と改行を除き、句読点も数えてください。',
 'operation': '現在形',
}}


def count(text, language):
    """Explicit whitespace-word / non-whitespace Unicode code-point contract."""
    return len(''.join(text.split())) if language == 'ja' else len(text.split())


def band(source, language):
    n = count(source, language)
    return max(1, math.ceil(n * .8)), max(1, math.floor(n * 1.2))


def validate_source(row):
    if row['language'] not in LANGUAGES or row['task'] not in TASKS:
        raise ValueError('unsupported language/task')
    source = row['source']
    if source['language'] != row['language'] or not source['text'].strip():
        raise ValueError('authoritative source must be in target language')
    if source['review'] != 'clear' or source['reviewer'] not in ('assistant-manual', 'odin-source-and-request-audit') or not source['facts']:
        raise ValueError('reviewed intelligible source and facts required')
    if source['sha256'] != sha(source['text']):
        raise ValueError('changed authoritative source')
    if row['language'] == 'da' and not source.get('translation_of'):
        raise ValueError('Danish translation lineage required')
    if row['task'] == 'qa' and not (row.get('question') and row.get('reference_answer') and row.get('answer_support') in source['text']):
        raise ValueError('reviewed source-supported question required')
    if row['task'] == 'rewrite' and source.get('narration') != 'past':
        raise ValueError('present-tense rewrite requires past-tense source')
    if row.get('slots_reviewed') is not True:
        raise ValueError('native slots and compatible preconditions must be reviewed')
    if row['task'] in ('creative', 'revision') and not row.get('topic'):
        raise ValueError('native topic required')
    if row['task'] == 'revision' and len(row.get('changes', [])) != 2:
        raise ValueError('two compatible reviewed paragraph changes required')


def initial_request(row):
    validate_source(row)
    lang, task = row['language'], row['task']
    t = TEMPLATES[lang]
    request = t[task][row['variant'] % 3].format(topic=row.get('topic'), question=row.get('question'), operation=t['operation'])
    if task in ('creative', 'rewrite', 'revision'):
        lo, hi = band(row['source']['text'], lang)
        request += '\n' + t['limit'].format(lo=lo, hi=hi)
    if task in ('summary', 'qa', 'rewrite'):
        request += '\n\n' + row['source']['text']
    return request


def payload(model, messages):
    result = dict(model=model, temperature=.3, max_tokens=6144,
        chat_template_kwargs={'enable_thinking': False}, messages=[
        dict(role='system', content='Follow the current user request. Return only the requested plain text, without JSON, commentary, headings or code fences. Separate story paragraphs with one blank line.'), *messages])
    if model == 'odin-2-large':
        result.pop('max_tokens'); result.pop('chat_template_kwargs')
        result.update(max_completion_tokens=6144, reasoning_effort='none', include_reasoning=False)
    return result


def decode(body):
    choice = body['choices'][0]
    usage=body.get('usage',{})
    # Provider reasoning-token accounting is not an output validity criterion.
    # The user explicitly authorized ignoring it after the v2 development run.
    if usage.get('completion_tokens',0)>6144:
        raise ValueError('completion_budget_exceeded')
    m = choice['message']
    if choice['finish_reason'] != 'stop' or m.get('reasoning') or m.get('reasoning_content'):
        raise ValueError('incomplete_or_thinking_response')
    text = m['content']
    if not isinstance(text, str) or not text.strip():
        raise ValueError('malformed_response')
    return text.strip()


def findings(text, language, limits=None, paragraphs=None):
    issues = []
    try:
        json_envelope = isinstance(json.loads(text), (dict, list))
    except (ValueError, TypeError):
        json_envelope = False
    if text.lstrip().startswith('```') or json_envelope:
        issues.append('Return plain prose without a code fence or JSON envelope.')
    if limits and not limits[0] <= count(text, language) <= limits[1]:
        issues.append(f'Length is {count(text, language)}; required interval is {limits[0]}–{limits[1]}.')
    if paragraphs and len(re.split(r'\n\s*\n', text)) != paragraphs:
        issues.append(f'Return exactly {paragraphs} paragraph(s) separated by blank lines.')
    return issues


def edit_request(row, parts, index, original=None):
    lo, hi = band(row['source']['text'], row['language'])
    unchanged = sum(count(p, row['language']) for i, p in enumerate(parts) if i != index)
    remaining = (max(1, lo - unchanged), hi - unchanged)
    if index == 2 and original is not None:
        undo_unchanged = count(original[0], row['language']) + count(parts[1], row['language'])
        remaining = (max(remaining[0], lo-undo_unchanged), min(remaining[1], hi-undo_unchanged))
    if remaining[1] < remaining[0]:
        raise ValueError('incompatible paragraph allowance')
    return TEMPLATES[row['language']]['edit'].format(paragraph=index+1,
        change=row['changes'][0 if index == 0 else 1], lo=remaining[0], hi=remaining[1], total_lo=lo, total_hi=hi), remaining


ASSEMBLY = {
 'en': ('Return only that paragraph, with no heading.', 'Return the complete story, copying the other paragraphs exactly.'),
 'da': ('Svar kun med dette afsnit uden overskrift.', 'Gengiv hele historien, og kopiér de øvrige afsnit ordret.'),
 'hi': ('उत्तर में केवल वही अनुच्छेद दें, कोई शीर्षक नहीं।', 'उत्तर में पूरी कहानी दें। बाकी अनुच्छेद अक्षरशः वही रखें।'),
 'ja': ('見出しを付けず、その段落だけを返してください。', '他の段落を一字一句変えずに、物語全体を返してください。'),
}


def assembly_request(request, language):
    before, after = ASSEMBLY[language]
    if request.count(before) != 1: raise ValueError('unknown edit template')
    return request.replace(before, after)


def replace(parts, index, text):
    if len(parts) != 3 or len(re.split(r'\n\s*\n', text)) != 1:
        raise ValueError('edit boundary')
    return [text if i == index else p for i, p in enumerate(parts)]


class StagedGenerate(Audit):
    """One queue item per conversation; every stage durable before dependencies.

    Write-ahead dispatch receipts prevent regeneration after an ambiguous crash.
    Such a request remains unresolved rather than silently spending another attempt.
    """
    context_length = 0

    def receipt(self, state):
        value = super().receipt(state)
        artifacts = {}
        for row in rows(self.root/state['job']['input']):
            for directory in ('stages', 'versions'):
                for path in (self.output/directory/sha(row['id'])).glob('*.json'):
                    artifacts[str(path.relative_to(self.output))] = file_hash(path)
        value.update(policy=POLICY, stage_artifacts=artifacts)
        return value

    def verify_receipt(self, job, folder):
        super().verify_receipt(job, folder)
        receipt = load(folder/'receipt.json')
        if receipt.get('policy') != POLICY: raise ValueError('changed staged policy')
        for relative, digest in receipt['stage_artifacts'].items():
            if file_hash(self.output/relative) != digest:
                raise ValueError('changed completed stage artifact')

    def stage_path(self, row, stage, attempt):
        return self.output/'stages'/sha(row['id'])/f'{stage}-{attempt}.json'

    def begin(self, row, stage, attempt, request):
        path = self.stage_path(row, stage, attempt)
        pin = sha(dict(row=row, model=self.model, request=request))
        if path.exists():
            record = json.loads(path.read_text())
            if record['pin'] != pin:
                raise ValueError('changed stage inputs')
            return {k:v for k,v in record.items() if k != 'pin'}
        intent = path.with_suffix('.intent.json')
        if intent.exists():
            if json.loads(intent.read_text())['pin'] != pin:
                raise ValueError('changed stage intent')
            return dict(pin=pin, error='interrupted_dispatch_unresolved')
        immutable(intent, dict(pin=pin))
        return None

    def finish_stage(self, row, stage, attempt, request, record):
        immutable(self.stage_path(row, stage, attempt), dict(record,
            pin=sha(dict(row=row, model=self.model, request=request))))

    async def generate_stage(self, row, stage, messages, limits, paragraphs, http, cpu, disk, allow_correction=True, unchanged_text=None):
        attempts = []
        current = messages
        # One objective correction, transport retries separately bounded to one.
        for correction in range(2 if allow_correction else 1):
            request = await cpu.call(payload, self.model, current)
            body = None
            for transport_attempt in range(2):
                number = correction*2 + transport_attempt
                record = await disk.call(self.begin, row, stage, number, request)
                if record is None:
                    try:
                        started=time.monotonic()
                        body = await http.post(request)
                        record = dict(response=body,seconds=time.monotonic()-started)
                    except httpx.HTTPError as exc:
                        status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                        record = dict(error=type(exc).__name__, retryable=status in (408,429,500,502,503,504) or status is None)
                    await disk.call(self.finish_stage, row, stage, number, request, record)
                attempts.append(record)
                if 'response' in record:
                    body = record['response']; break
                if not record.get('retryable'):
                    return dict(status='unresolved', attempts=attempts)
            if body is None:
                return dict(status='unresolved', attempts=attempts)
            try:
                text = await cpu.call(decode, body)
            except (ValueError, KeyError, TypeError, IndexError):
                return dict(status='unresolved', attempts=attempts)
            issues = await cpu.call(findings, text, row['language'], limits, paragraphs)
            if unchanged_text is not None and text == unchanged_text:
                issues.append('The requested paragraph edit must change the paragraph; the response is identical.')
            attempts[-1] = dict(attempts[-1], findings=issues, text=text, correction=correction)
            # Findings also have an immutable receipt before the next request.
            await disk.call(immutable, self.stage_path(row, stage, number).with_suffix('.check.json'), attempts[-1])
            if not issues:
                return dict(status='complete', text=text, corrected=bool(correction), attempts=attempts)
            current = [*messages, dict(role='assistant', content=text), dict(role='user', content='Correct only these objective failures; preserve meaning and all other requirements:\n'+'\n'.join(issues))]
        return dict(status='deterministic_failure', attempts=attempts)

    async def process(self, item, http, cpu, disk):
        row = item[1]
        stages, messages = {}, []
        result = dict(audit_id=row['audit_id'], input_id=row['id'], policy=POLICY, status='unresolved', stages=stages)
        request = await cpu.call(initial_request, row)
        messages.append(dict(role='user', content=request))
        limits = await cpu.call(band, row['source']['text'], row['language']) if row['task'] in ('creative','rewrite','revision') else None
        first = await self.generate_stage(row, 'initial', messages, limits, 3 if row['task']=='revision' else None, http, cpu, disk)
        stages['initial'] = first
        if first['status'] == 'complete':
            messages.append(dict(role='assistant', content=first['text']))
            if row['task'] == 'revision':
                original = re.split(r'\n\s*\n', first['text'])
                parts = original[:]
                await disk.call(immutable,self.output/'versions'/sha(row['id'])/'initial.json',
                    dict(opening=original[0],middle=original[1],ending=original[2]))
                for name, index in [('opening',0), ('ending',2)]:
                    request, allowance = await cpu.call(edit_request, row, parts, index, original)
                    # Model returns one paragraph; student sees a complete story assembled in code.
                    request_messages = [*messages, dict(role='user',content=request)]
                    stage = await self.generate_stage(row,name,request_messages,allowance,1,http,cpu,disk,
                        allow_correction=not any(s.get('corrected') for s in stages.values()),unchanged_text=parts[index])
                    stages[name] = stage
                    if stage['status'] != 'complete': break
                    parts = await cpu.call(replace,parts,index,stage['text'])
                    # Student request asks for the assembled complete story, while the
                    # generator sees the narrower paragraph-only request.
                    full_request = assembly_request(request, row['language'])
                    messages.extend([dict(role='user',content=full_request),dict(role='assistant',content='\n\n'.join(parts))])
                    # Full versions are explicit context for the next operation.
                    # Stored independently; never silently change the requested response shape.
                    await disk.call(immutable,self.output/'versions'/sha(row['id'])/(name+'.json'),dict(parts=parts))
                else:
                    undone = [original[0], parts[1], parts[2]]
                    undo = TEMPLATES[row['language']]['undo'].format(lo=limits[0],hi=limits[1])
                    text = '\n\n'.join(undone)
                    issues = await cpu.call(findings,text,row['language'],limits,3)
                    stages['undo'] = dict(status='deterministic_failure' if issues else 'complete',text=text,findings=issues,generated=False)
                    messages.extend([dict(role='user',content=undo),dict(role='assistant',content=text)])
            if all(s['status']=='complete' for s in stages.values()):
                result.update(status='generated',candidate=dict(messages=messages),
                    first_attempt_contract_clear=not any(s.get('corrected') for s in stages.values()))
        if result['status'] != 'generated':
            result['status'] = next((s['status'] for s in stages.values() if s['status']!='complete'),'unresolved')
        result['messages'] = messages
        result['seconds'] = sum(a.get('seconds',0) for s in stages.values() for a in s.get('attempts',[]))
        await disk.call(self.commit,item,result)
