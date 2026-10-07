"""Opt-in, complete-coverage headline populations with explicit metric units.

Registry JSON has schema_version=1 and populations=[{id, kind, languages,
required_tasks, metrics}]. metrics[language][task] is {suite,key,scale} with
optional artifact (relative merged-metric JSON path), or null for unavailable.
No partial population score is emitted; language means receive equal weight.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
from typing import Any


SUITES = {'standard', 'dfm', 'euroeval'}
SCALES = {'fraction': 1.0, 'percent': 100.0}


def strict_json(text: str) -> Any:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('Duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=pairs)


def definition_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
        separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def validate_registry(registry: dict) -> dict:
    if not isinstance(registry, dict) or set(registry) != {'schema_version', 'populations'}:
        raise ValueError('Registry requires schema_version and populations')
    if type(registry['schema_version']) is not int or registry['schema_version'] != 1:
        raise ValueError('Unsupported population registry version')
    if not isinstance(registry['populations'], list) or not registry['populations']:
        raise ValueError('Nonempty populations required')
    identifiers = set()
    for population in registry['populations']:
        if not isinstance(population, dict) or set(population) - {'aggregation_policy'} != {'id', 'kind', 'languages', 'required_tasks', 'metrics'}:
            raise ValueError('Invalid population fields')
        if 'aggregation_policy' in population and not available_population(population):
            raise ValueError('Available policy is restricted to explicit DFM13 populations')
        kind, identifier = population['kind'], population['id']
        pattern = {'multilingual': r'multilingual_v[1-9][0-9]*',
                   'dfm14_new_languages': r'dfm14_new_languages_v[1-9][0-9]*',
                   'dfm14_all_languages': r'dfm14_all_languages_v[1-9][0-9]*',
                   'dfm13_new_languages': r'dfm13_new_languages_v[1-9][0-9]*',
                   'dfm13_multilingual': r'dfm13_multilingual_v[1-9][0-9]*',
                   'dfm13_all_languages': r'dfm13_all_languages_v[1-9][0-9]*',
                   'cross_language': r'cross_language_v[1-9][0-9]*',
                   'english': r'english_v(?:[2-9]|[1-9][0-9]+)',
                   'english_dfm': r'english_dfm_v[1-9][0-9]*'}.get(kind, '')
        if not pattern or not isinstance(identifier, str) or not re.fullmatch(pattern, identifier):
            raise ValueError('Explicit multilingual_vN or new english_vN (N>=2) required')
        if identifier in identifiers:
            raise ValueError('Duplicate population identity')
        identifiers.add(identifier)
        languages, tasks = population['languages'], population['required_tasks']
        task_lists = list(tasks.values()) if isinstance(tasks, dict) else [tasks]
        for values, name in [(languages, 'languages'), *[(v, 'required_tasks') for v in task_lists]]:
            if (not isinstance(values, list) or not values or any(not isinstance(v, str) or
                    not re.fullmatch(r'[a-z][a-z0-9_-]*', v) for v in values) or len(set(values)) != len(values)):
                raise ValueError('Unique safe ' + name + ' required')
        if isinstance(tasks, dict) and set(tasks) != set(languages):
            raise ValueError('Per-language required_tasks must cover every language')
        if kind == 'multilingual' and (len(languages) != 19 or set(languages) & {'en', 'da'}):
            raise ValueError('Multilingual population requires exactly 19 non-da/en languages')
        if kind == 'dfm14_new_languages' and set(languages)!=set('ga mt mk eu gl cy ru tr zh ar ja id ko hi vi he'.split()):
            raise ValueError('DFM14 language population mismatch')
        if kind == 'dfm14_all_languages' and set(languages)!=set('da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk lt lv sq be bs bg hr hu lb sr sk sl fa ga mt mk eu gl cy ru tr zh ar ja id ko hi vi he'.split()):
            raise ValueError('DFM14 all-language population mismatch')
        if kind in ('dfm13_new_languages','dfm13_multilingual','dfm13_all_languages'):
            expected=set('lt lv sq be bs bg hr hu lb sr sk sl fa'.split())
            if kind in ('dfm13_multilingual','dfm13_all_languages'):
                expected.update('nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split())
            if kind=='dfm13_all_languages':expected.update(('da','en'))
            if set(languages)!=expected:raise ValueError('DFM13 language population mismatch')
        if kind == 'cross_language':
            expected = set('da en nb nn sv is fo nl pl de fr es it cs pt_pt fi et ca el ro uk'.split())
            if set(languages) != expected:
                raise ValueError('Cross-language population requires all 21 languages')
            for language in languages:
                required = tasks[language] if isinstance(tasks, dict) else tasks
                expected_tasks = {'scala', 'multiifeval', 'dfm_la', 'dfm_gec'}
                if language != 'cs':
                    expected_tasks.add('multiwikiqa')
                if set(required) != expected_tasks:
                    raise ValueError('Cross-language requires five tasks, four for Czech')
        if kind in ('english', 'english_dfm') and languages != ['en']:
            raise ValueError('English population must contain only en')
        if kind == 'english_dfm' and set(tasks['en'] if isinstance(tasks, dict) else tasks) != {'la', 'gec'}:
            raise ValueError('English DFM pair requires exactly la and gec')
        metrics = population['metrics']
        if not isinstance(metrics, dict) or set(metrics) != set(languages):
            raise ValueError('Bindings must explicitly cover every declared language')
        used = set()
        for language in languages:
            required = tasks[language] if isinstance(tasks, dict) else tasks
            if not isinstance(metrics[language], dict) or set(metrics[language]) != set(required):
                raise ValueError('Bindings must explicitly cover all required tasks (null if unavailable)')
            for binding in metrics[language].values():
                if binding is None:
                    continue
                if not isinstance(binding, dict) or not {'suite', 'key', 'scale'} <= set(binding) or set(binding) - {'suite', 'key', 'scale', 'artifact', 'metric_language'}:
                    raise ValueError('Binding requires suite/key/scale and optional artifact')
                if (not isinstance(binding['suite'], str) or not isinstance(binding['scale'], str)
                        or binding['suite'] not in SUITES or binding['scale'] not in SCALES):
                    raise ValueError('Unknown source suite or metric scale')
                if kind == 'english_dfm' and binding['suite'] != 'dfm':
                    raise ValueError('English DFM pair requires dfm bindings')
                key = binding['key']
                if not isinstance(key, str) or not key or key.startswith('/'):
                    raise ValueError('Exact nonempty metric key required')
                expected_prefix = {'standard': 'eval/', 'dfm': 'dfm_eval/', 'euroeval': 'euroeval/'}[binding['suite']]
                if not key.startswith(expected_prefix):
                    raise ValueError('Metric prefix does not match source suite')
                metric_language = binding.get('metric_language', language)
                if not isinstance(metric_language, str) or not re.fullmatch(r'[a-z][a-z0-9_-]*', metric_language):
                    raise ValueError('Invalid explicit metric language namespace')
                if binding['suite'] == 'euroeval' and not key.startswith(f'euroeval/{metric_language}/'):
                    raise ValueError('EuroEval metric language mismatch')
                artifact = binding.get('artifact')
                if artifact is not None and (not isinstance(artifact, str) or not artifact or
                        PurePosixPath(artifact).is_absolute() or '..' in PurePosixPath(artifact).parts or '\\' in artifact):
                    raise ValueError('Artifact must be a safe relative path')
                identity = (binding['suite'], key)
                if identity in used:
                    raise ValueError('A source metric cannot count twice within a population')
                used.add(identity)
    return registry


def load_registry(path: Path) -> dict:
    return validate_registry(strict_json(Path(path).read_text()))


def normalize(value: Any, scale: str) -> float | None:
    if type(value) not in (int, float):
        return None
    try:
        value = float(value)
    except (OverflowError, ValueError):
        return None
    if not math.isfinite(value) or not 0 <= value <= SCALES[scale]:
        return None
    return value / SCALES[scale]


class Artifacts:
    """Keep origin and units distinct; never dict.update colliding metric keys."""
    def __init__(self, item):
        self.item = item
        given = {'standard': item.standard_root, 'dfm': item.dfm_root, 'euroeval': item.euroeval_root}
        self.roots = {suite: [Path(p).resolve() for p in (value if isinstance(value, (list, tuple)) else [value]) if p is not None]
                      for suite, value in given.items()}
        self.root_recoveries = []
        for roots in self.roots.values():
            for index, root in enumerate(roots):
                if (not root.exists() and root.name == root.parent.name
                        and re.fullmatch(r'(?:epoch|step)_[0-9]+(?:\.[0-9]+)?', root.name)
                        and root.parent.is_dir()):
                    roots[index] = root.parent
                    self.root_recoveries.append({'requested': str(root), 'resolved': str(root.parent)})
        self.cache = {}
        self.paths = {}
        for suite, roots in self.roots.items():
            paths = set()
            for root in roots:
                paths.update(root.glob('**/merged_metrics.json'))
                extra = root / 'merged_ifeval_da_metrics.json'
                if suite == 'dfm' and extra.exists():
                    paths.add(extra)
            self.paths[suite] = sorted(paths)

    def read(self, path):
        if path not in self.cache:
            try:
                document = strict_json(path.read_text())
                if not isinstance(document, dict):
                    raise ValueError('Metric artifact must be an object')
                metrics = document.get('metrics', document)
                if not isinstance(metrics, dict):
                    raise ValueError('Artifact metrics must be an object')
                self.cache[path] = (metrics, None, document)
            except (OSError, ValueError) as exc:
                self.cache[path] = ({}, str(exc), {})
        return self.cache[path]

    def resolve(self, binding):
        if binding is None:
            return None, {'status': 'unavailable'}
        suite, key = binding['suite'], binding['key']
        roots = self.roots[suite]
        if not roots:
            return None, {'status': 'missing_root'}
        paths = self.paths[suite]
        if key=='dfm_eval/generative-talemaader/model_graded_fact_v2/accuracy':
            paths=sorted(set(paths)|{p for root in roots for p in root.glob('**/merged_metrics_v2.json')})
        if 'artifact' in binding:
            paths = set()
            for root in roots:
                path = (root / binding['artifact']).resolve()
                if not path.is_relative_to(root):
                    return None, {'status': 'unsafe_artifact'}
                if path.is_file():
                    paths.add(path)
            paths = sorted(paths)
        hits, errors = [], []
        for path in paths:
            if not any(path.resolve().is_relative_to(root) for root in roots):
                errors.append({'path': str(path), 'error': 'Artifact symlink escapes source root'})
                continue
            metrics, error, document = self.read(path)
            if error:
                errors.append({'path': str(path), 'error': error})
            if key in metrics:
                hits.append((path, metrics[key], metrics, document))
        if errors:
            return None, {'status': 'invalid_artifact', 'errors': errors}
        if len(hits) != 1:
            return None, {'status': 'missing' if not hits else 'ambiguous', 'paths': [str(h[0]) for h in hits]}
        path, raw, metrics, document = hits[0]
        checkpoint_binding = 'requested_root'
        for values in (metrics, document):
            for stamp in ('eval/train_step', 'dfm_eval/train_step', 'euroeval/train_step'):
                if stamp in values and (type(values[stamp]) not in (int, float) or values[stamp] != self.item.step):
                    return None, {'status': 'checkpoint_mismatch', 'path': str(path), 'step_key': stamp}
            for stamp in ('eval/epoch', 'dfm_eval/epoch', 'euroeval/epoch'):
                if stamp in values and (type(values[stamp]) not in (int, float) or values[stamp] != self.item.epoch):
                    return None, {'status': 'checkpoint_mismatch', 'path': str(path), 'epoch_key': stamp}
        value = normalize(raw, binding['scale'])
        detail = dict(status='valid' if value is not None else 'invalid_value', path=str(path),
                      suite=suite, key=key, scale=binding['scale'], normalized=value,
                      checkpoint_binding=checkpoint_binding)
        if value is not None:
            detail['raw_value'] = raw
        return value, detail


def available_population(population):
    return (population['id'].startswith(('dfm13_', 'dfm14_')) and
            population.get('aggregation_policy') == 'available_tasks_then_available_languages_v1')


def population_score_definition(population):
    if available_population(population):
        return dict(population, aggregation_policy='available_tasks_then_available_languages_v1')
    return population


def enable_available_dfm13(registry):
    """Explicit opt-in copy; never modify historical/legacy definitions."""
    import copy
    result = copy.deepcopy(registry)
    for population in result['populations']:
        if population['id'].startswith('dfm13_'):
            population['aggregation_policy'] = 'available_tasks_then_available_languages_v1'
    return result


def build_population_row(item, registry: dict, prefix: str = 'avg_population') -> tuple[dict, dict]:
    validate_registry(registry)
    if prefix.rstrip('/') != 'avg_population':
        raise ValueError('Population namespace is reserved as avg_population; legacy prefixes cannot be overwritten')
    artifacts = Artifacts(item)
    return _population_row(item, registry, artifacts)


def build_population_row_from_metrics(metrics, item, registry):
    """Historical API: caller supplies checkpoint-aligned raw metric values."""
    validate_registry(registry)
    class RawMetrics:
        root_recoveries = []
        def resolve(self, binding):
            if not binding: return None, {'status': 'unavailable'}
            value = normalize(metrics.get(binding['key']), binding['scale'])
            return value, {'status': 'valid' if value is not None else 'missing_or_invalid',
                           'key': binding['key'], 'normalized': value}
    return _population_row(item, registry, RawMetrics())


def _population_row(item, registry, artifacts):
    row = {'avg_population/epoch': item.epoch, 'avg_population/train_step': item.step}
    report = dict(schema_version=1, registry_sha256=definition_hash(registry), step=item.step,
                  weighting='equal tasks within language, equal languages; DFM13 available-only, legacy complete-only', populations={},
                  root_recoveries=artifacts.root_recoveries)
    for population in registry['populations']:
        base = f"avg_population/{population['id']}"
        means, valid_count, details, complete_languages = [], 0, {}, 0
        available = available_population(population)
        for language in population['languages']:
            values, details[language] = [], {}
            required = population['required_tasks']
            required = required[language] if isinstance(required, dict) else required
            for task in required:
                value, detail = artifacts.resolve(population['metrics'][language][task])
                details[language][task] = detail
                if value is not None:
                    values.append(value)
            valid_count += len(values)
            language_base = f'{base}/languages/{language}'
            row[language_base + '/valid_tasks'] = len(values)
            row[language_base + '/expected_tasks'] = len(required)
            complete = len(values) == len(required)
            row[language_base + '/complete'] = int(complete)
            row[language_base + '/coverage'] = len(values) / len(required)
            complete_languages += int(complete)
            if complete or (available and values):
                mean = math.fsum(values) / len(values)
                means.append(mean)
                row[language_base + '/score'] = mean
        expected = sum(len(population['metrics'][lang]) for lang in population['languages'])
        row.update({base + '/valid_metrics': valid_count, base + '/expected_metrics': expected,
                    base + '/complete_languages': complete_languages, base + '/available_languages': len(means), base + '/expected_languages': len(population['languages']),
                    base + '/coverage': valid_count / expected, base + '/complete': int(valid_count == expected),
                    base + '/definition_sha256': definition_hash(population_score_definition(population))})
        if valid_count == expected or (available and means):
            row[base + '/score'] = math.fsum(means) / len(means)
        report['populations'][population['id']] = dict(complete=valid_count == expected,
            definition_sha256=definition_hash(population_score_definition(population)), languages=details,
            available_metrics=available, score_available=bool(means), valid_metrics=valid_count,
            expected_metrics=expected, available_languages=len(means), complete_languages=complete_languages)
    return row, report
