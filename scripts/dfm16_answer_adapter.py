"""Generate targets with source-specific checks and concise semantic review."""
import json
import asyncio
import subprocess
import httpx
import jsonschema
from referencing import Registry
from referencing.exceptions import Unresolvable

from audit_pipeline.dfm14 import Audit
from audit_pipeline import review
from dfm12.io import load
from dfm12.prepare import Renderer
from dfm14.native_instructions import count, convert
from scripts.dfm16_verification import check


class Answers(Audit):
    def initialize_cpu(self):
        self.renderer = Renderer(load(self.root/'tokenizer.json'), max_length=4097)
        self.verification_slots = asyncio.Semaphore(8)
        if (self.root/'preparation.json').exists():
            from scripts.dfm16_verification import VERIFIERS
            for repo, revision in load(self.root/'preparation.json').get('verifier_pins', {}).items():
                actual = subprocess.check_output(['git', '-C', str(VERIFIERS/repo), 'rev-parse', 'HEAD'], text=True).strip()
                if actual != revision or subprocess.call(['git', '-C', str(VERIFIERS/repo), 'diff', '--quiet', 'HEAD']):
                    raise ValueError('Changed verifier checkout: '+repo)

    def request(self, row):
        payload = dict(model=self.model, messages=row['messages'], temperature=.2,
                       max_tokens=row.get('max_tokens', 4096),
                       chat_template_kwargs=dict(enable_thinking=False))
        if row.get('tools'):
            payload.update(tools=row['tools'], tool_choice='auto')
        return payload

    def candidate(self, body, row):
        choice = body['choices'][0]
        if choice['finish_reason'] not in ('stop', 'tool_calls'):
            raise ValueError('incomplete_answer')
        message = choice['message']
        text = message.get('content') or ''
        if message.get('reasoning_content') or message.get('reasoning'):
            raise ValueError('unexpected_thinking')
        if 'schema' in row:
            validator = jsonschema.validators.validator_for(row['schema'])
            validator(row['schema'], registry=Registry()).validate(json.loads(text))
        target = dict(role='assistant', content=text)
        if message.get('tool_calls'):
            target['tool_calls'] = message['tool_calls']
        candidate = convert(dict(messages=row['messages']+[target], tools=row.get('tools', [])),
                            allow_terminal_tool_calls=True)
        candidate.update(id=row['id'], provenance=row['provenance'])
        candidate['rendered_tokens'] = count(candidate, self.renderer, 4096)
        candidate['target_message_index'] = len(candidate['messages'])-1
        return candidate

    async def process(self, item, http, cpu, disk):
        row = item[1]
        result = dict(audit_id=row['audit_id'], input_id=row['id'], policy=review.VERSION)
        for attempt in (1, 2):
            try:
                body = await http.post(await cpu.call(self.request, row))
                candidate = await cpu.call(self.candidate, body, row)
                verification = row.get('verification')
                if verification:
                    async with self.verification_slots:
                        passed = await asyncio.to_thread(check, candidate['messages'][-1]['content'], verification)
                    result['verification'] = dict(kind=verification['kind'], passed=passed,
                        executable=verification['kind'] not in ('reference_review', 'tool_review', 'commonsense_review'))
                    if not passed:
                        result.update(status='reviewed', review=dict(decision='reject'), attempt=attempt,
                                      generation=body, rejection='deterministic_verifier')
                        break
                payload = await cpu.call(review.payload, dict(conversation=candidate['messages'],
                    tools=candidate.get('tools', []),
                    task=('Check correctness, instruction compliance and coherence. Reference evidence is private verification context, '
                          'not permission to invent tool results. Check event names and permanent constraints for calendar tasks. '
                          'Code must solve the intended task, not special-case tests. Commonsense conclusions must remain plausible, not certain.'
                          if verification else 'Faithful structured extraction: values must be supported by the supplied document, not merely valid JSON.'),
                    evidence=verification or row['schema']), self.model)
                verdict = await cpu.call(review.verdict, await http.post(payload))
                result.update(status='reviewed', review=verdict, attempt=attempt,
                              candidate=candidate, generation=body)
                break
            except (httpx.HTTPError, ValueError, KeyError, TypeError, IndexError,
                    jsonschema.ValidationError, jsonschema.SchemaError, Unresolvable, subprocess.TimeoutExpired) as exc:
                result.update(status='infrastructure_or_invalid_review', attempt=attempt,
                              error=dict(type=type(exc).__name__, message=str(exc)[:500]))
        await disk.call(self.commit, item, result)
