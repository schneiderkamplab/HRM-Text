"""Convert downloaded expansion sources to auditable native chat or held generation inputs."""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, wait, FIRST_COMPLETED
import copy
import json
from pathlib import Path
import re
import sqlite3
import time
import jsonschema

from dfm12.io import atomic, digest, file_hash, load, lock, rows, write_json
from dfm12.prepare import Renderer
from dfm14.native_instructions import convert, count
from scripts.prepare_dfm16_dyna import publish_audit_manifest
from scripts.tokenize_chat_template import examples_from_messages, tokenize_example

ROOT = Path('data/dfm16/expansion-v1')


def target_views(candidate, renderer, per_turn=False):
    """Select whole fitting targets, never truncate a prompt or assistant answer."""
    if per_turn:
        views = [dict(candidate, messages=candidate['messages'][:i+1], target_message_index=i)
                 for i, m in enumerate(candidate['messages']) if m['role'] == 'assistant']
    else:
        views = [candidate]
    accepted, rejected = [], Counter()
    for view in views:
        thinking = any(m.get('reasoning_content') for m in view['messages'])
        total = 0
        for example in examples_from_messages(view['messages'], view.get('tools'), view.get('target_message_index')):
            encoded = tokenize_example(renderer.tokenizer, renderer.template, example, thinking)
            if encoded is None or sum(map(len, encoded)) > 4096:
                rejected['nonfitting_complete_target'] += 1
                break
            total += sum(map(len, encoded))
        else:
            if total:
                view['rendered_tokens'] = total
                accepted.append(view)
            else:
                rejected['no_training_targets'] += 1
    return accepted, rejected


def normalize_tools(tools):
    if isinstance(tools, str):
        tools = json.loads(tools)
    result = []
    for tool in tools or []:
        tool = copy.deepcopy(tool)
        if tool.get('type') not in (None, 'function'):
            raise ValueError('non_function_tool')
        function = tool.get('function', tool)
        if 'function' in function and 'name' not in function:
            function = function['function']
        if 'parameters' not in function and isinstance(function.get('arguments'), dict):
            properties = function.pop('arguments')
            function['parameters'] = dict(type='object', properties=properties,
                required=[name for name, spec in properties.items()
                          if 'optional' not in str(spec.get('type', '')) and 'default' not in spec])
        if function.get('required') is not None:
            if 'required' in function['parameters'] and function['parameters']['required'] != function['required']:
                raise ValueError('conflicting_required_fields')
            function['parameters']['required'] = function.pop('required')
        function['parameters'] = normalize_schema(function['parameters'])
        result.append(dict(type='function', function=function))
    return result


def normalize_schema(schema):
    if not isinstance(schema, dict):
        return schema
    schema = copy.deepcopy(schema)
    aliases = dict(str='string', int='integer', float='number', dict='object', list='array', bool='boolean')
    if isinstance(schema.get('type'), str):
        kind = schema['type'].removesuffix(', optional')
        schema['type'] = aliases.get(kind, kind)
    for key in ('properties', '$defs', 'definitions'):
        if key in schema:
            schema[key] = {name: normalize_schema(value) for name, value in schema[key].items()}
    for key in ('items', 'additionalProperties'):
        if isinstance(schema.get(key), dict):
            schema[key] = normalize_schema(schema[key])
    for key in ('anyOf', 'allOf', 'oneOf'):
        if key in schema:
            schema[key] = [normalize_schema(x) for x in schema[key]]
    return schema


def normalize_messages(original):
    if isinstance(original, str):
        original = json.loads(original)
    messages, reasoning = [], ''
    for i, source in enumerate(original):
        item = copy.deepcopy(source)
        kind = item.get('type')
        if kind == 'reasoning':
            reasoning += '\n'.join(x['text'] for x in item.get('summary', []) if x.get('type') == 'summary_text')
            continue
        if kind == 'function_call':
            message = dict(role='assistant', content='', tool_calls=[dict(type='function',
                id=item.get('call_id') or item.get('id') or f'call_{i}',
                function=dict(name=item['name'], arguments=item['arguments']))])
        elif kind == 'function_call_output':
            message = dict(role='tool', content=item['output'], tool_call_id=item['call_id'])
        else:
            role = item.get('role') or {'human':'user', 'gpt':'assistant', 'system':'system'}.get(item.get('from'))
            content = item.get('content', item.get('value', '')) or ''
            if isinstance(content, list):
                if any(x.get('type') not in ('text', 'input_text', 'output_text') for x in content):
                    raise ValueError('nontext_content')
                content = '\n'.join(x['text'] for x in content)
            message = dict(role=role, content=content)
            for key in ('tool_calls', 'tool_call_id', 'name', 'reasoning_content'):
                if item.get(key) is not None:
                    message[key] = item[key]
            for j, call in enumerate(message.get('tool_calls', [])):
                call.setdefault('id', f'call_{i}_{j}')
                call.setdefault('type', 'function')
        if message['role'] == 'assistant' and reasoning:
            message['reasoning_content'] = reasoning
            reasoning = ''
        messages.append(message)
    if reasoning:
        raise ValueError('dangling_reasoning')
    return messages


def swe_messages(row):
    """Translate the published SWE-smith function protocol, without inventing results."""
    messages = normalize_messages(row['messages'])
    if not messages or messages[0]['role'] != 'system':
        raise ValueError('missing_swe_tool_definitions')
    text = messages[0]['content']
    blocks = list(re.finditer(r'---- BEGIN FUNCTION #(\d+): ([\w]+) ----\n(.*?)---- END FUNCTION #\1 ----', text, re.S))
    if not blocks:
        raise ValueError('unknown_swe_system_protocol')
    tools = []
    types = dict(string='string', integer='integer', number='number', boolean='boolean', array='array', object='object')
    for block in blocks:
        name, body = block[2], block[3]
        description = body.removeprefix('Description: ').split('\nParameters:')[0].strip()
        properties, required = {}, []
        specs = list(re.finditer(r'^\s*\(\d+\) (\w+) \((\w+)(?:, (required|optional))?\): ', body, re.M))
        for i, spec in enumerate(specs):
            if spec[2] not in types:
                raise ValueError('unknown_swe_parameter_type')
            end = specs[i+1].start() if i+1 < len(specs) else len(body)
            properties[spec[1]] = dict(type=types[spec[2]], description=body[spec.end():end].strip())
            if spec[3] == 'required':
                required.append(spec[1])
        if not specs and 'No parameters are required' not in body:
            raise ValueError('unparsed_swe_parameters')
        tools.append(dict(type='function', function=dict(name=name, description=description,
            parameters=dict(type='object', properties=properties, required=required, additionalProperties=False))))
    prefix = text[:blocks[0].start()].split('You have access to the following functions:')[0].strip()
    suffix = text[blocks[-1].end():]
    if suffix.strip() and not suffix.lstrip().startswith('If you choose to call a function'):
        raise ValueError('unrecognized_swe_suffix')
    messages[0]['content'] = prefix
    schemas = {t['function']['name']:t['function']['parameters'] for t in tools}
    pending = None
    for i, message in enumerate(messages[1:], 1):
        content = message['content']
        if message['role'] == 'assistant':
            match = re.fullmatch(r'(.*?)<function=(\w+)>\s*(.*?)\s*</function>\s*', content, re.S)
            if not match or pending is not None:
                if '<function=' in content or pending is not None:
                    raise ValueError('ambiguous_swe_call')
                continue
            name, body = match[2], match[3]
            if name not in schemas:
                raise ValueError('unknown_swe_tool')
            arguments = {}
            params = list(re.finditer(r'<parameter=(\w+)>(.*?)</parameter>', body, re.S))
            if re.sub(r'<parameter=\w+>.*?</parameter>', '', body, flags=re.S).strip():
                raise ValueError('unparsed_swe_arguments')
            for param in params:
                if param[1] in arguments or param[1] not in schemas[name]['properties']:
                    raise ValueError('invalid_swe_parameter')
                value = param[2]
                if schemas[name]['properties'][param[1]]['type'] != 'string':
                    value = json.loads(value)
                arguments[param[1]] = value
            call_id = f'swe_call_{i}'
            message.update(content=match[1].strip(), tool_calls=[dict(type='function', id=call_id,
                function=dict(name=name, arguments=arguments))])
            pending = call_id, name
        elif pending is not None:
            if message['role'] != 'user' or not (content.startswith('OBSERVATION:') or
                    content == 'Your command ran successfully and did not produce any output.'):
                raise ValueError('unrecognized_swe_observation')
            message.update(role='tool', content=content.removeprefix('OBSERVATION:'),
                           tool_call_id=pending[0], name=pending[1])
            pending = None
    return messages, tools


def convert_row(repo, row):
    if repo == 'SWE-bench/SWE-smith-trajectories' and row.get('resolved') is not True:
        raise ValueError('unsuccessful_trajectory')
    params = row.get('responses_create_params')
    if repo == 'SWE-bench/SWE-smith-trajectories':
        messages, tools = swe_messages(row)
    elif params:
        messages = normalize_messages(params['input'])
        tools = normalize_tools(params.get('tools'))
        target = row.get('expected_action')
        if target:
            if target['type'] == 'message':
                messages.append(dict(role='assistant', content=target['content']))
            elif target['type'] == 'function_call':
                messages.append(dict(role='assistant', content='', tool_calls=[dict(type='function',
                    id='target_'+digest(target)[:20], function=dict(name=target['name'], arguments=target['arguments']))]))
            else:
                raise ValueError('unsupported_reference_action')
        elif repo.endswith('workplace_assistant') and row.get('ground_truth'):
            messages.append(dict(role='assistant', content='', tool_calls=[dict(type='function',
                id=f'target_{i}', function=dict(name=t['name'], arguments=t['arguments']))
                for i, t in enumerate(row['ground_truth'])]))
        else:
            return None
    else:
        original = row.get('messages') or row.get('conversations')
        if not original:
            return None
        messages = normalize_messages(original)
        tools = normalize_tools(row.get('tools'))
    # Never carry an incompatible text tool protocol into native chat supervision.
    if any(re.search(r'<function=|<parameter=|BEGIN FUNCTION|<tool_response>', m['content']) for m in messages):
        raise ValueError('requires_source_specific_tool_protocol_adapter')
    candidate = convert(dict(messages=messages, tools=tools), allow_terminal_tool_calls=True)
    if messages and messages[-1]['role'] != 'assistant':
        raise ValueError('missing_reference_answer')
    return candidate


def selected_files(directory, repo):
    snapshot = directory/'snapshot'
    pin = load(directory/'source.json')
    files = []
    for entry in pin['files']:
        name = entry['path']
        if not name.endswith(('.jsonl', '.jsonl.gz', '.parquet', '.json')) or name.startswith('.'):
            continue
        if re.search(r'(^|[/_.-])(test|validation|valid|val|dev)([/_.-]|$)', name, re.I):
            continue
        # XML view carries the actual tool definitions; the tool view omits them.
        # Choose one representation per trajectory, then convert to native calls.
        if repo == 'SWE-bench/SWE-smith-trajectories' and not name.startswith('data/xml-'):
            continue
        path = snapshot/name
        if path.exists():
            files.append(path)
    return sorted(files)


def prepare_source(source, root=ROOT):
    repo = source['repo_id']
    directory = root/'downloads'/repo.replace('/', '__')
    out = root/'converted'/repo.replace('/', '__')
    with lock(out/'.prepare.lock'):
        if (out/'conversion.json').exists():
            return load(out/'conversion.json')
        status = load(directory/'status.json')
        if status['phase'] != 'downloaded':
            return dict(repo_id=repo, phase=status['phase'], error=status.get('error'))
        files = selected_files(directory, repo)
        if not files:
            result = dict(repo_id=repo, phase='blocked_external_recipe', training_ready=False)
            write_json(out/'status.json', result)
            return result
        meta = load('data/dfm15/native-reasoning-v2/sampled_dfm15/metadata.json')['tokenizer_info']
        renderer = Renderer(meta, max_length=4097)
        pin = load(directory/'source.json')
        counts, chunks, pending = Counter(), [], []
        db = sqlite3.connect(out/'seen.sqlite')
        db.execute('DROP TABLE IF EXISTS seen')
        db.execute('CREATE TABLE seen (hash TEXT PRIMARY KEY)')
        def flush():
            if not pending:
                return
            name = f'chunks/{len(chunks):06}.jsonl'
            with atomic(out/name) as stream:
                for value in pending:
                    stream.write(json.dumps(value, ensure_ascii=False)+'\n')
            chunks.append(dict(job_id=f'input-{len(chunks):06}', input=name, rows=len(pending),
                               task='instruction', sha256=file_hash(out/name)))
            pending.clear()
        try:
            with atomic(out/'generation-pending.jsonl') as generation, atomic(out/'held.jsonl') as held:
                for path in files:
                    for index, row in enumerate(rows(path)):
                        counts['input'] += 1
                        provenance = dict(repo_id=repo, revision=pin['revision'],
                            file=str(path.relative_to(directory/'snapshot')), row=index,
                            source_id=row.get('id', row.get('trajectory_id', row.get('traj_id'))))
                        try:
                            candidate = convert_row(repo, row)
                            if candidate is None:
                                generation.write(json.dumps(dict(provenance=provenance, source=row), ensure_ascii=False)+'\n')
                                counts['pending_generation'] += 1
                                continue
                            if repo == 'openbmb/UltraData-SFT-2605' and 'Chinese' in str(path):
                                candidate['language'] = 'zh'
                            views, rejected = target_views(candidate, renderer,
                                per_turn=repo == 'SWE-bench/SWE-smith-trajectories')
                            counts.update(rejected)
                            for view in views:
                                key = digest([view['messages'], view.get('tools'), view.get('target_message_index')])
                                if not db.execute('INSERT OR IGNORE INTO seen VALUES (?)', (key,)).rowcount:
                                    counts['duplicate'] += 1
                                    continue
                                view.update(id=key, audit_id=key, provenance=provenance,
                                    training_ready=False, admission_authorized=False)
                                pending.append(view)
                                counts['audit_candidates'] += 1
                                if len(pending) == 128:
                                    flush()
                        except (ValueError, KeyError, TypeError, IndexError, SyntaxError, jsonschema.ValidationError, jsonschema.SchemaError) as exc:
                            reason = type(exc).__name__+':'+str(exc).split('\n', 1)[0][:150]
                            counts['held:'+reason] += 1
                            held.write(json.dumps(dict(provenance=provenance, reason=reason), ensure_ascii=False)+'\n')
                        if counts['input'] % 1000 == 0:
                            write_json(out/'status.json', dict(phase='converting', counts=dict(counts), time=time.time()))
                flush()
            db.commit()
        finally:
            db.close()
        publish_audit_manifest(out, chunks)
        result = dict(repo_id=repo, phase='converted_pending_audit_and_generation', counts=dict(counts),
                      training_ready=False, chunks=len(chunks), revision=pin['revision'])
        write_json(out/'conversion.json', result)
        write_json(out/'status.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--wait', action='store_true')
    parser.add_argument('--workers', type=int, default=4)
    args = parser.parse_args()
    sources = load('config/dfm16_expansion.json')['sources']
    with lock(args.root/'.conversion-controller.lock'):
        pending, active, failures = list(sources), {}, []
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            while pending or active:
                for source in pending[:]:
                    if len(active) >= args.workers:
                        break
                    path = args.root/'downloads'/source['repo_id'].replace('/', '__')/'status.json'
                    if not path.exists() or load(path)['phase'] == 'downloading':
                        continue
                    active[pool.submit(prepare_source, source, args.root)] = source
                    pending.remove(source)
                if active:
                    done, _ = wait(active, timeout=30, return_when=FIRST_COMPLETED)
                    for future in done:
                        source = active.pop(future)
                        try:
                            print(future.result(), flush=True)
                        except Exception as exc:
                            failure = dict(repo_id=source['repo_id'], error=repr(exc))
                            failures.append(failure)
                            print(failure, flush=True)
                elif not args.wait:
                    break
                else:
                    time.sleep(30)
                write_json(args.root/'conversion-controller.json', dict(pending=pending,
                    active=list(active.values()), failures=failures, sampling=False))
        if failures:
            raise RuntimeError('Source conversion failures: inspect conversion-controller.json')


if __name__ == '__main__':
    main()
