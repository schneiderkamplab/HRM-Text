"""Future v4 native tool conversations; legacy v2/v3 contracts are unchanged.

The teacher localizes dialogue, not executable arguments or mock receipts.
CPU-owned user data grounds every argument; audits still judge prose coherence.
"""
import copy
import json

import jsonschema

from .io import digest
from .records import MARKERS
from .multilingual_review_tools import arguments, deterministic_checks

CONTRACT = 'native-tool-dialogue-v4-localized-final-v2'
CONTROL_MARKERS = tuple(MARKERS) + ('<|', '|>', '<bos>', '<eos>', '<pad>')
SUBTYPES = ('single', 'clarify', 'multi', 'error', 'retry', 'no-call')
ERROR = {'error': 'temporary_unavailable'}
GOALS = {
    'single': 'Request only a lookup. Return the lookup result; do not perform or claim an action.',
    'clarify': 'Request only a lookup. Obtain the missing required field from a user clarification before lookup. No action.',
    'multi': 'Explicitly request lookup followed by the declared action using the successful lookup result.',
    'error': 'Request only a lookup. The sole attempt fails; report the error without retry or success.',
    'retry': 'Request only a lookup. A transient failure is followed by one retry with unchanged arguments; report the successful lookup, not an action.',
    'no-call': 'Ask a general hypothetical question about how this service works. Explain without accessing a record or claiming any execution.',
}


def encoded(value):
    return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',', ':'),allow_nan=False)


def configure(spec):
    """Scope the scenario to one path, keeping the original scenario as provenance."""
    if spec.get('contract_version') != 4 or spec['family'] != 'tool-dialogue':
        raise ValueError('Native tool dialogue requires explicit future contract_version4')
    result = copy.deepcopy(spec)
    subtype = result['subtype']
    if subtype not in SUBTYPES:
        raise ValueError('Unknown native tool subtype')
    scenario = result['scenario']
    result['tool_dialogue_source_scenario'] = copy.deepcopy(scenario)
    scenario['requirement'] = ('Fictional mock service only; no real transaction, medical advice or invented policies. '
                               + GOALS[subtype] + ' Explain the terminal result in concise natural target-language prose. '
                               'Reject any unsupported action/success claim, invented detail or contradictory explanation.')
    if subtype != 'multi':
        scenario['tools'] = [t for t in scenario['tools'] if t['function']['name']==scenario['lookup_name']]
        for key in ('action_name','action_arguments','action_result'):
            scenario.pop(key,None)
    if subtype == 'error':
        scenario['lookup_result'] = copy.deepcopy(ERROR)
    if subtype == 'no-call':
        for key in ('arguments','lookup_result','missing_field'):
            scenario.pop(key,None)
    result['tool_dialogue_contract'] = CONTRACT
    return result


def validate_spec(spec):
    if (spec.get('contract_version') != 4 or spec.get('tool_dialogue_contract') != CONTRACT
            or spec.get('subtype') not in SUBTYPES or spec.get('family') != 'tool-dialogue'):
        raise ValueError('Missing/unknown native tool contract; do not reinterpret frozen specs')
    scenario = spec['scenario']
    names = [t['function']['name'] for t in scenario['tools']]
    required = [scenario['lookup_name']]
    if spec['subtype']=='multi':
        required.append(scenario['action_name'])
    if names != required or any(t.get('type')!='function' for t in scenario['tools']):
        raise ValueError('Tool definitions do not match selected path')
    def local_references(node):
        if isinstance(node,dict):
            for key,value in node.items():
                if key in ('$ref','$dynamicRef') and (not isinstance(value,str) or not value.startswith('#')):
                    raise ValueError('External tool schema references forbidden')
                local_references(value)
        elif isinstance(node,list):
            for value in node:
                local_references(value)
    for tool in scenario['tools']:
        parameters = tool['function']['parameters']
        local_references(parameters)
        jsonschema.Draft202012Validator.check_schema(parameters)
    if spec['subtype']!='multi' and any(k in scenario for k in ('action_name','action_arguments','action_result')):
        raise ValueError('Action facts leaked into a non-action scenario')
    if spec['subtype']=='error' and scenario['lookup_result']!=ERROR:
        raise ValueError('Error-only path cannot supply success result')
    return scenario


def response_schema(spec):
    validate_spec(spec)
    fields = ['user']
    if spec['subtype']=='clarify':
        fields += ['clarification','clarification_reply']
    elif spec['subtype']=='no-call':
        fields += ['explanation']
    if spec['subtype']!='no-call':
        fields += ['final']
    string = {'type':'string','minLength':1,'maxLength':1200}
    return {'type':'object','properties':{key:copy.deepcopy(string) for key in fields},
            'required':fields,'additionalProperties':False}


def request(spec):
    from .multilingual_tasks import MODEL
    scenario = validate_spec(spec)
    view = {k:spec[k] for k in ('language','language_code','subtype','audience','tone')}
    view.update(contract=CONTRACT,scenario=scenario)
    if spec['subtype']!='no-call':
        view['terminal_evidence'] = terminal_evidence(spec)
    instruction = '''Write only the requested localized dialogue fields, in the requested
language/variant, as JSON. All data are a fictional mock service. Follow ONLY the
selected subtype; do not add fields for other paths. No raw chat delimiters,
hidden reasoning, tool-call text, fabricated identifiers, policies or outcomes.
The CPU inserts canonical JSON request data into the user's turn and assembles
native tool calls/results. You may naturalize service names and dates in prose;
never change their meaning or contradict the canonical data. You need not copy
the data block or repeat every identifier. Request the selected operation clearly.
For lookup-only paths do not ask to book, reserve or redirect anything. For multi,
explicitly request the action. Do not put lookup/action results in user text.
For clarify, user lacks the specified missing_field: do not mention its value
until clarification_reply. Ask for that field, not an unrelated detail. CPU adds
the exact missing value to the reply; no invented substitute value is allowed.
For no-call, provide a general hypothetical explanation only, with no claimed
execution, record-specific availability, invented requirements or guarantees.
For tool paths, final MUST be a concise natural-language explanation of the exact
terminal_evidence in the requested language, not JSON-only or copied tool syntax.
Lookup/clarify/retry paths only found information: they did NOT book, reserve,
redirect or otherwise act. Error-only paths failed: explain the failure without
inventing a result or promising that a retry happened. The retry path succeeded
only on the second lookup; no action happened. Multi may confirm only the action
supported by its successful action receipt. Keep quantities, identifiers, dates,
availability and error state consistent. Do not invent policy or real-world
execution. Do not add standalone retry narration between native tool messages.
Return exactly the schema fields. Maintain Bokmal/Nynorsk and Faroese/Icelandic
distinctions; concise native wording, not literal word substitutions.
'''
    return dict(model=MODEL,temperature=0.75,max_tokens=2048,
        chat_template_kwargs={'enable_thinking':False},
        response_format={'type':'json_schema','json_schema':{
            'name':'tool_'+spec['subtype'].replace('-','_')+'_v4','strict':True,
            'schema':response_schema(spec)}},
        messages=[{'role':'system','content':instruction},
                  {'role':'user','content':encoded(view)}])


def terminal_evidence(spec):
    scenario = validate_spec(spec)
    subtype = spec['subtype']
    if subtype=='no-call':
        raise ValueError('No-call has no terminal tool evidence')
    action = subtype=='multi'
    return dict(tool=scenario['action_name'] if action else scenario['lookup_name'],
        result=copy.deepcopy(scenario['action_result'] if action else scenario['lookup_result']),
        action_executed=action,lookup_attempts=2 if subtype=='retry' else 1,
        successful=subtype!='error',scope='fictional_mock_only',
        required_review=['target_language','result_grounding','no_unsupported_action_claim','no_invented_details'])


def action_sources(scenario):
    """Separate lookup-returned values from values the user must supply."""
    returned = {
        'library': {'copy_id':'copy_id'},
        'appointment': {'slot_id':'slot_id'},
        'parcel': {'parcel_id':'parcel_id','locker_id':'available_locker_id'},
        'event': {'ticket_type_id':'ticket_type_id'},
        'stock': {'stock_id':'stock_id'},
    }[scenario['domain']]
    if not set(returned) <= set(scenario['action_arguments']):
        raise ValueError('Missing lookup-derived action identifier')
    result = {}
    for field,value in scenario['action_arguments'].items():
        if field in returned:
            key = returned[field]
            item = scenario['lookup_result'].get(key)
            if type(item) is not type(value) or item != value:
                raise ValueError('Action identifier does not match successful lookup')
            result[field] = {'kind':'lookup_result','field':key}
        else:
            result[field] = {'kind':'user'}
    return result


def assemble(spec, generated):
    scenario = validate_spec(spec)
    subtype = spec['subtype']
    schema = response_schema(spec)
    jsonschema.Draft202012Validator(schema).validate(generated)
    for value in generated.values():
        if not value.strip() or any(marker in value for marker in CONTROL_MARKERS):
            raise ValueError('Empty dialogue or raw chat/control delimiter')
    messages = [{'role':'user','content':generated['user']}]
    bindings = []
    def supply(index, data, group):
        # Explicit visible user data, not a hidden inference from a translated
        # substring. Semantic audit must still reject conflicting generated prose.
        block = encoded(data)
        messages[index]['content'] += '\n\n```json\n'+block+'\n```'
        for field,value in data.items():
            bindings.append(dict(group=group,field=field,value=value,source='user_data',
                message_index=index,canonical_json=block,verification='cpu_inserted_exact_value'))
    if subtype=='no-call':
        messages.append({'role':'assistant','content':generated['explanation']})
    else:
        lookup_args = arguments(copy.deepcopy(scenario['arguments']))
        def agrees(values, receipt):
            return all(key in receipt and type(receipt[key]) is type(value) and receipt[key]==value
                       for key,value in values.items())
        if subtype!='error' and not agrees(lookup_args,scenario['lookup_result']):
            raise ValueError('Lookup receipt contradicts supplied arguments')
        missing = scenario['missing_field']
        if missing not in lookup_args:
            raise ValueError('Missing field not in lookup arguments')
        supplied = dict(lookup_args)
        if subtype=='clarify':
            value = supplied.pop(missing)
            if str(value) in generated['user']:
                raise ValueError('Missing argument already present before clarification')
        supply(0,supplied,'lookup')
        if subtype=='multi':
            sources = action_sources(scenario)
            if not agrees(scenario['action_arguments'],scenario['action_result']):
                raise ValueError('Action receipt contradicts action arguments')
            if scenario['domain'] in ('stock','event'):
                quantity = scenario['action_arguments']['quantity']
                available = scenario['lookup_result']['available']
                if type(quantity) is not int or type(available) is not int or not 0 < quantity <= available:
                    raise ValueError('Requested quantity exceeds available result or has invalid type')
            user_args = {k:v for k,v in scenario['action_arguments'].items() if sources[k]['kind']=='user'}
            if user_args:
                supply(0,user_args,'action')
        if subtype=='clarify':
            messages += [{'role':'assistant','content':generated['clarification']},
                         {'role':'user','content':generated['clarification_reply']}]
            supply(2,{missing:lookup_args[missing]},'lookup')
        def call(name,args,response):
            index = len(messages)
            identifier = 'call_'+str(index)
            messages.extend([{'role':'assistant','content':'','tool_calls':[
                {'id':identifier,'type':'function','function':{'name':name,'arguments':copy.deepcopy(args)}}]},
                {'role':'tool','name':name,'tool_call_id':identifier,'content':encoded(response)}])
            return index+1
        if subtype=='retry':
            call(scenario['lookup_name'],lookup_args,ERROR)
        lookup_index = call(scenario['lookup_name'],lookup_args,scenario['lookup_result'])
        terminal_index = lookup_index
        if subtype=='multi':
            if 'error' in scenario['lookup_result']:
                raise ValueError('Action cannot follow a failed lookup')
            for field,source in sources.items():
                if source['kind']=='lookup_result':
                    bindings.append(dict(group='action',field=field,value=scenario['action_arguments'][field],
                        source='tool_result',message_index=lookup_index,result_field=source['field']))
            terminal_index = call(scenario['action_name'],arguments(copy.deepcopy(scenario['action_arguments'])),scenario['action_result'])
        # Structural validity is not semantic approval of this localized prose.
        messages.append({'role':'assistant','content':generated['final']})
    tools = copy.deepcopy(scenario['tools'])
    row = dict(messages=messages,tools=tools)
    from scripts.prepare_dfm11_tool_replacements import validate_trajectory
    error = validate_trajectory(row,allow_terminal_calls=False)
    if error:
        raise ValueError(error)
    if any(not check['passed'] for check in deterministic_checks(row)):
        raise ValueError('Invalid native call schema/identifier/result binding')
    # Check all content, including CPU-inserted scenario values, for raw markers.
    if any(marker in encoded(row) for marker in CONTROL_MARKERS):
        raise ValueError('Raw chat/control delimiter in scenario')
    provenance = copy.deepcopy(spec)
    provenance['tool_dialogue_grounding'] = dict(contract=CONTRACT,argument_sources=bindings,
        final_policy='audited_localized_terminal_explanation' if subtype!='no-call' else 'audited_hypothetical_explanation',
        semantic_review_required=True,
        limitation='Canonical values are grounded; naturalized prose/intent consistency still requires semantic audit.')
    if subtype!='no-call':
        provenance['tool_dialogue_grounding']['final_evidence'] = dict(
            terminal_evidence(spec),result_message_index=terminal_index,
            final_message_index=len(messages)-1,semantic_status='pending_review')
    identity = [CONTRACT,4,spec['language_code'],'tool-dialogue',spec['slot'],spec['variant'],spec.get('cohort')]
    return dict(id=digest(identity),language=spec['language_code'],family='tool-dialogue',
        messages=messages,tools=tools,provenance=provenance,native_speaker_review='pending',pilot_only=True)


def prepare(root, language):
    """Freeze thirty CPU-prepared requests; no generation, calibration or admission."""
    from pathlib import Path
    from .io import file_hash, write_json
    from .multilingual_tasks import spec_for
    from .multilingual_prepare_calibrated import IMPLEMENTATIONS
    from .multilingual_diagnose import PromptBudget
    from .identity_gpu import training_renderer
    root = Path(root)
    root.mkdir(parents=True,exist_ok=False)
    training_renderer(root)
    budget = PromptBudget()
    records = []
    for slot in range(30):
        spec = spec_for(language,'tool-dialogue',slot,0,{},
                        {'contract_version':4,'cohort':root.name})
        payload = request(spec)
        records.append(dict(spec=spec,request=payload,prompt_tokens=budget.measure(payload)))
    write_json(root/'requests.json',records)
    write_json(root/'manifest.json',dict(contract=CONTRACT,contract_version=4,
        requests=len(records),language=language,cpu_only=True,model_outputs=0,
        generation_authorized=False,calibration_passed=False,admission_authorized=False,
        semantic_review_required=True,
        implementation_pins={name:file_hash(Path(__file__).with_name(name)) for name in IMPLEMENTATIONS},
        input_pins={p.name:file_hash(p) for p in root.iterdir() if p.is_file()}))
    return len(records)


if __name__=='__main__':
    import argparse
    from pathlib import Path
    from .multilingual_seeds import LANGUAGES
    parser = argparse.ArgumentParser(description='CPU-only native tool v4 request preparation; no model calls')
    parser.add_argument('--prepare-root',type=Path,required=True)
    parser.add_argument('--language',choices=tuple(LANGUAGES),default='sv')
    args = parser.parse_args()
    print('Prepared CPU requests:',prepare(args.prepare_root,args.language))
