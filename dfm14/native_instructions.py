"""Convert structured instruction traces without fabricating tool definitions."""
import ast
import copy
import json
import re
import jsonschema


def validate(messages, tools):
    schemas = {}
    for tool in tools:
        if tool.get('type') != 'function':
            raise ValueError('unsupported_tool_type')
        f = tool['function']
        if f['name'] in schemas:
            raise ValueError('duplicate_tool_schema')
        jsonschema.Draft202012Validator.check_schema(f['parameters'])
        schemas[f['name']] = f['parameters']
    pending, ids = {}, set()
    if not messages or messages[-1]['role'] != 'assistant':
        raise ValueError('missing_assistant_target')
    for i, message in enumerate(messages):
        role = message['role']
        if role not in {'system', 'user', 'assistant', 'tool'}:
            raise ValueError('unsupported_role')
        if not isinstance(message.get('content'), str):
            raise ValueError('nontext_content')
        if role == 'system' and i != 0:
            raise ValueError('late_system')
        if pending and role != 'tool':
            raise ValueError('missing_tool_result')
        if role == 'tool':
            call_id = message.get('tool_call_id')
            if call_id not in pending or message.get('name') != pending[call_id]:
                raise ValueError('unlinked_tool_result')
            del pending[call_id]
        calls = message.get('tool_calls') or []
        if calls and role != 'assistant':
            raise ValueError('nonassistant_tool_call')
        for call in calls:
            function = call['function']
            name = function['name']
            if name not in schemas:
                raise ValueError('undeclared_tool:' + name)
            if call['id'] in ids:
                raise ValueError('duplicate_tool_call_id')
            jsonschema.validate(function['arguments'], schemas[name])
            ids.add(call['id']); pending[call['id']] = name
        for key in ('content', 'reasoning_content'):
            if re.search(r'</?(?:think|tool_call)>|<\|(?:tool|turn|channel)', message.get(key) or ''):
                raise ValueError('unconverted_control_markup')
    if pending:
        raise ValueError('unresolved_terminal_tool_call')


def convert(row):
    kwargs = row.get('chat_template_kwargs') or {}
    if any(k not in {'custom_instructions','enable_thinking','python_tools','xml_tools'} and v
           for k,v in kwargs.items()) or kwargs.get('python_tools'):
        raise ValueError('unsupported_template_metadata')
    tools = copy.deepcopy(row.get('tools') or [])
    for block in kwargs.get('xml_tools') or []:
        if not isinstance(block, str):
            raise ValueError('invalid_xml_tool_definitions')
        for line in block.splitlines():
            if line.strip():
                tools.append(json.loads(line))
    messages, pending = [], []
    custom = kwargs.get('custom_instructions')
    if custom:
        messages.append(dict(role='system', content=custom))
    for original in row['messages']:
        m = copy.deepcopy(original)
        if m.get('reasoning_content') is None:
            m.pop('reasoning_content', None)
        content = m.get('content') or ''
        if not isinstance(content, str):
            raise ValueError('nontext_content')
        reasoning = re.match(r'^\s*<think>(.*?)</think>\s*', content, re.S)
        if reasoning:
            if m['role'] != 'assistant' or m.get('reasoning_content'):
                raise ValueError('ambiguous_reasoning')
            m['reasoning_content'] = reasoning[1].strip()
            content = content[reasoning.end():]
        calls = list(re.finditer(r'<tool_call>(.*?)</tool_call>', content, re.S))
        if calls:
            if m['role'] != 'assistant' or m.get('tool_calls'):
                raise ValueError('ambiguous_tool_calls')
            m['tool_calls'] = []
            for match in calls:
                try:
                    call = json.loads(match[1])
                except json.JSONDecodeError:
                    call = ast.literal_eval(match[1])
                if not isinstance(call, dict) or set(call) != {'name','arguments'}:
                    raise ValueError('invalid_tool_call_object')
                call_id = f'call_{len(messages)}_{len(m["tool_calls"])}'
                m['tool_calls'].append(dict(type='function', id=call_id, function=call))
            content = re.sub(r'<tool_call>.*?</tool_call>', '', content, flags=re.S).strip()
        for call in m.get('tool_calls') or []:
            args = call['function'].get('arguments')
            if isinstance(args, str):
                call['function']['arguments'] = json.loads(args)
            pending.append((call['id'], call['function']['name']))
        if m['role'] == 'tool':
            if len(pending) != 1 and not m.get('tool_call_id'):
                raise ValueError('ambiguous_tool_result_link')
            if m.get('tool_call_id'):
                matches = [x for x in pending if x[0] == m['tool_call_id']]
                if len(matches) != 1:
                    raise ValueError('unlinked_tool_result')
                call_id, name = matches[0]
            else:
                call_id, name = pending[0]
            pending.remove((call_id,name)); m.update(tool_call_id=call_id, name=name)
        m['content'] = content
        messages.append(m)
    # smolagents uses a terminal final_answer pseudo-tool, not an external action.
    last = messages[-1] if messages else {}
    calls = last.get('tool_calls') or []
    if len(calls) == 1 and calls[0]['function']['name'] == 'final_answer':
        call = calls[0]
        definitions = [t for t in tools if t['function']['name'] == 'final_answer']
        if len(definitions) != 1 or set(call['function']['arguments']) != {'answer'} or last['content'].strip():
            raise ValueError('ambiguous_final_answer')
        jsonschema.validate(call['function']['arguments'], definitions[0]['function']['parameters'])
        last['content'] = call['function']['arguments']['answer']
        last.pop('tool_calls')
        tools = [t for t in tools if t['function']['name'] != 'final_answer']
    validate(messages, tools)
    return dict(language='en', task='instruction', messages=messages, tools=tools,
                format_contract='gemma4-native-structured-tools-v1')


def count(record, renderer, limit):
    from scripts.tokenize_chat_template import examples_from_messages, tokenize_example
    total = 0
    for example in examples_from_messages(record['messages'], record.get('tools', [])):
        encoded = tokenize_example(renderer.tokenizer, renderer.template, example, False)
        if encoded is None or sum(map(len,encoded)) > limit:
            raise ValueError('full_target_context_exceeds_limit')
        total += sum(map(len,encoded))
    if not total:
        raise ValueError('no_training_targets')
    return total
