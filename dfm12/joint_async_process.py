"""Retained pilot processing with an asynchronous, durable owner fingerprint claim.

Integration must pin this module in a fresh runtime. No live controller is patched.
The supplied pilot (or controller.pilot) owns all generation/review semantics.
"""
import asyncio
import time

from .io import digest, write_json


class AsyncRemoteSeen:
    """Use a dedicated AsyncRPC connection, not the synchronous claim transport."""
    def __init__(self, rpc, role, key):
        self.rpc, self.role, self.key = rpc, role, key
        self.broken = False

    async def claim(self, fingerprint):
        try:
            result = await self.rpc.call('claim', role=self.role, key=self.key,
                                         fingerprint=fingerprint)
            if type(result) is not bool:
                raise ValueError('Owner fingerprint claim must return a boolean')
            return result
        except BaseException:
            self.broken = True
            raise


async def process(spec, endpoint, root, stages, health, generation, review, seen, *, pilot):
    """Same contract as pilot.process; seen.claim atomically inserts at the owner."""
    pilot = getattr(pilot, 'pilot', pilot)
    v6 = pilot.v6
    key = pilot.slot_key(spec)
    outcome = pilot.base_outcome(spec)
    path = root / 'outcomes' / f'{key}.json'
    write_json(path, outcome)
    try:
        payload = v6.generation_request(spec, generation, endpoint_models=list(health.values()))
        payload.update(temperature=.75 if spec['family'] == 'tool-dialogue' else .65,
                       repetition_penalty=1.15)
        payload, schema = v6.compact_request(payload)
        state = await stages.call(key, 'generate', payload, schema, endpoint,
                                  v6.endpoint_limit(health[endpoint]), spec=spec)
        outcome.update(generation_status=state['status'], **{k: state.get(k, False) for k in
            ('json_valid', 'structure_valid', 'content_constraints_valid')})
        if state['status'] != 'complete':
            outcome.update(status=state['status'], error=state.get('error'))
            return outcome
        candidate = v6.generation_assemble(spec, state['output'], generation)
        write_json(root / 'candidates' / f'{key}.json', candidate)
        fingerprint = digest({k: candidate[k] for k in ('messages', 'tools')})
        outcome.update(assembled=True, fingerprint=fingerprint)
        if not await seen.claim(fingerprint):
            outcome.update(status='duplicate', duplicate=True)
            return outcome
        record = v6.audit_record(candidate)
        payload = v6.review_request(record, review)
        payload.update(temperature=0, frequency_penalty=.5)
        payload, schema = v6.compact_request(payload)
        state = await stages.call(key, 'review', payload, schema, endpoint,
                                  v6.endpoint_limit(health[endpoint]))
        outcome['review_status'] = state['status']
        if state['status'] != 'complete':
            outcome.update(status='review_' + state['status'], error=state.get('error'))
        else:
            outcome.update(v6.review_result(state['output'], record, review))
    except asyncio.CancelledError:
        outcome.update(status='abort_status_unknown', error='Interrupted slot; no automatic replay')
        raise
    except Exception as exc:
        outcome.update(status='invalid_output', error=repr(exc))
    finally:
        outcome.update(terminal=True, completed=time.time(), **pilot.POLICY)
        write_json(path, outcome)
    return outcome
