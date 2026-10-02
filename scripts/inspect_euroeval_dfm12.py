"""CPU-only source inspection: no EuroEval imports, dependency resolution or evaluation."""
import ast
import hashlib
import io
import json
from pathlib import Path
import tarfile
import urllib.request

COMMIT = '1b801b5f2fa123302a1429030612cb57a41a7e86'
MODULES = ('danish dutch english estonian faroese finnish french german greek icelandic '
           'italian norwegian polish portuguese romanian spanish swedish ukrainian catalan czech').split()


def value(node):
    try:
        return ast.literal_eval(node)
    except (ValueError, TypeError):
        if isinstance(node, (ast.List, ast.Tuple)):
            return [value(item) for item in node.elts]
        return ast.unparse(node)


def calls(text, constructor):
    result = {}
    for node in ast.parse(text).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)) and isinstance(node.value, ast.Call):
            call = node.value
            if ast.unparse(call.func) != constructor:
                continue
            name = node.targets[0].id if isinstance(node, ast.Assign) else node.target.id
            result[name] = {kw.arg:value(kw.value) for kw in call.keywords}
            result[name]['line'] = node.lineno
    return result


def inspect(get, reference):
    tasks_text = get('tasks.py')
    tasks = calls(tasks_text, 'Task')
    languages = calls(get('languages.py'), 'Language')
    records = {}
    pins = {'tasks.py':hashlib.sha256(tasks_text.encode()).hexdigest()}
    for module in MODULES:
        relative = 'dataset_configs/'+module+'.py'
        text = get(relative)
        pins[relative] = hashlib.sha256(text.encode()).hexdigest()
        for cfg in calls(text, 'DatasetConfig').values():
            task = tasks[cfg['task']]
            records[cfg['name']] = dict(cfg, module=module, task_category=task['name'],
                metrics=task.get('metrics'), task_group=task.get('task_group'),
                language_codes=[languages[s].get('code', languages[s].get('code_1') or languages[s].get('code_3')) for s in cfg['languages']],
                code_ref=reference+'/'+relative+'#L'+str(cfg['line']))
    return dict(datasets=records, tasks=tasks, languages=languages, file_sha256=pins)


def main():
    archive = urllib.request.urlopen('https://api.github.com/repos/EuroEval/EuroEval/tarball/'+COMMIT).read()
    with tarfile.open(fileobj=io.BytesIO(archive), mode='r:gz') as tar:
        members = {m.name.split('/',1)[1]:m for m in tar.getmembers() if m.isfile()}
        def upstream(relative):
            return tar.extractfile(members['src/euroeval/'+relative]).read().decode()
        current = inspect(upstream, 'https://github.com/EuroEval/EuroEval/blob/'+COMMIT+'/src/euroeval')
        docs = {module:tar.extractfile(members['src/frontend/md/datasets/'+module+'.md']).read().decode()
                for module in MODULES}
        project = tar.extractfile(members['pyproject.toml']).read().decode()
    local = {}
    for version, root in [('17.3.0','/home/ucloud/miniforge3/envs/hrm/lib/python3.13/site-packages/euroeval'),
                          ('18.1.0','/work/mimir/.home/.cache/uv/archive-v0/20ddS3xsiCOjW0qI/euroeval')]:
        local[version] = inspect(lambda relative:(Path(root)/relative).read_text(), root)
        local[version]['path'] = root
    result = dict(commit=COMMIT, archive_sha256=hashlib.sha256(archive).hexdigest(),
                  pyproject=project, current=current, installed=local, docs=docs)
    Path('/tmp/dfm12-euroeval-research.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    for module in MODULES:
        print(module, [(d['name'], d['task_category'], d['language_codes'])
            for d in current['datasets'].values() if d['module']==module and not d.get('unofficial')])


if __name__=='__main__':
    main()
