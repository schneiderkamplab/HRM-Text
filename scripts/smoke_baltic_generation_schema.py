"""Read-only, bounded schema replay of Baltic malformed generations."""
import argparse
import asyncio
from copy import deepcopy
import json
from pathlib import Path
import sqlite3

import aiohttp
from jsonschema import Draft202012Validator

from dfm12 import baltic_compact_successor as campaign
from dfm12.io import write_json
from dfm12.multilingual_calibration_v6 import RawResponseWriter, raw_query, strict_json
from dfm12.wave_synthetic_runtime import decoder_schema


async def run(root, output, selection=None, disable_reasoning_output=False):
    output.mkdir(parents=True, exist_ok=False)
    controller = campaign.controller()
    selected = []
    with sqlite3.connect((root / 'jobs.sqlite').resolve().as_uri() + '?mode=ro', uri=True) as db:
        if selection:
            for entry in json.loads(selection.read_text()):
                row = db.execute('SELECT id,spec_json,workdir,outcome_json FROM jobs WHERE id=?',
                                 (entry['id'],)).fetchone()
                if row is None:
                    raise ValueError('Selected source job missing')
                selected.append(row)
        for language in (() if selection else ('lt', 'lv')):
            for family in ('grounded-instruct', 'summary-rewrite', 'multiturn',
                           'openhermes', 'math-code', 'tool-dialogue'):
                row = db.execute(
                    "SELECT id,spec_json,workdir,outcome_json FROM jobs WHERE language=? "
                    "AND family=? AND status='invalid_output' "
                    "AND json_extract(outcome_json,'$.completed')>=1791078108 "
                    "ORDER BY id LIMIT 1", (language, family)).fetchone()
                if row:
                    selected.append(row)
    write_json(output / 'selection.json', [dict(id=r[0], spec=json.loads(r[1]),
               original_outcome=json.loads(r[3])) for r in selected])
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=600)) as session:
        async def replay(index, row):
            key, spec, directory, _ = row
            spec = json.loads(spec)
            original = json.loads((Path(directory) / 'requests' / f'{key}-generate.json').read_text())
            payload = deepcopy(original['request'])
            payload['response_format'] = dict(type='json_schema', json_schema=dict(
                name='conversation', strict=True, schema=decoder_schema(original['schema'])))
            if disable_reasoning_output:
                payload['include_reasoning'] = False
            write_json(output / f'{key}.request.json', payload)
            result = dict(id=key, language=spec['language_code'], family=spec['family'],
                          production_changed=False, quality_accepted=False)
            try:
                raw = await raw_query(session, f'http://127.0.0.1:{8800 + index % 8}/v1',
                                      payload, RawResponseWriter(output / 'raw'), dict(id=key),
                                      offload_writer=True)
                result['raw'] = raw
                if raw['finish_reason'] != 'stop':
                    raise ValueError('Incomplete generation: ' + str(raw['finish_reason']))
                decoded = strict_json(raw['content'])
                Draft202012Validator(original['schema']).validate(decoded)
                result['schema_valid'] = True
                _, generation = controller.v6.adapters()
                candidate = controller.v6.generation_assemble(spec, decoded, generation)
                write_json(output / f'{key}.candidate.json', candidate)
                result['assembled'] = True
            except Exception as exc:
                result['error'] = repr(exc)
            write_json(output / f'{key}.result.json', result)
            return result
        results = await asyncio.gather(*(replay(i, row) for i, row in enumerate(selected)))
    write_json(output / 'summary.json', dict(total=len(results),
        schema_valid=sum(r.get('schema_valid', False) for r in results),
        assembled=sum(r.get('assembled', False) for r in results),
        production_changed=False, quality_accepted=False, results=results))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--selection', type=Path)
    parser.add_argument('--disable-reasoning-output', action='store_true')
    args = parser.parse_args()
    asyncio.run(run(args.root, args.output, args.selection, args.disable_reasoning_output))
