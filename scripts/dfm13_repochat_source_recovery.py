"""CPU-only public-source recovery, isolated from frozen campaign receipts."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import fcntl
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from scripts import dfm13_repochat_recovery as recovery

b = recovery.b
LIMIT = 128 * 1024 ** 2


def retryable(status, headers):
    return status in (429, 500, 502, 503, 504) or (
        status == 403 and (headers.get('X-RateLimit-Remaining') == '0' or headers.get('Retry-After')))


class Fetcher:
    def __init__(self, root):
        self.root = root
        self.lock = threading.Lock()
        self.last = 0
        # Explicit environment credential only, never repository files or git helpers.
        self.token = os.environ.get('GITHUB_TOKEN') or os.environ.get('GH_TOKEN')
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), b.NoRedirect())

    def fetch(self, url, limit):
        parsed = urllib.parse.urlsplit(url)
        if parsed.scheme != 'https' or parsed.netloc not in ('api.github.com', 'codeload.github.com') or parsed.username:
            raise ValueError('network host refused')
        headers = {'User-Agent': 'DFM13-RepoChat-public-source-recovery', 'Accept': 'application/vnd.github+json'}
        if self.token and parsed.netloc == 'api.github.com':
            headers['Authorization'] = 'Bearer ' + self.token
        key = b.sha(url.encode())
        for attempt in range(3):
            with self.lock:
                time.sleep(max(0, .5 - (time.monotonic() - self.last)))
                self.last = time.monotonic()
            try:
                request = urllib.request.Request(url, headers=headers)
                with self.opener.open(request, timeout=90) as response:
                    data = response.read(limit + 1)
                if len(data) > limit:
                    raise ValueError('download size limit')
                b.save(self.root / 'requests' / (key + f'-{attempt}.json'), {
                    'url': url, 'attempt': attempt + 1, 'status': 'ok', 'sha256': b.sha(data),
                    'authenticated_api': bool(self.token and parsed.netloc == 'api.github.com')})
                return data
            except urllib.error.HTTPError as exc:
                again = retryable(exc.code, exc.headers)
                b.save(self.root / 'requests' / (key + f'-{attempt}.json'), {'url': url, 'attempt': attempt + 1,
                    'http_status': exc.code, 'retryable': bool(again), 'authenticated_api': bool(self.token and parsed.netloc == 'api.github.com')})
                if not again or attempt == 2:
                    raise ValueError(f'public_source_http_{exc.code}') from None
                delay = max(10 * (attempt + 1), float(exc.headers.get('Retry-After', '0')))
                reset = exc.headers.get('X-RateLimit-Reset')
                if reset:
                    delay = max(delay, float(reset) - time.time() + 1)
                if delay > 60:
                    raise ValueError('source_rate_limit_deferred_no_early_retry') from None
                time.sleep(delay)
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                b.save(self.root / 'requests' / (key + f'-{attempt}.json'), {'url': url, 'attempt': attempt + 1,
                                                                          'transport_error_type': type(exc).__name__})
                if attempt == 2:
                    raise ValueError('public_source_transport_exhausted') from None
                time.sleep(10 * (attempt + 1))


def public_metadata(document):
    if document.get('private') is not False or not document.get('default_branch'):
        raise ValueError('public repository identity not established')
    return document


def resolve(job, root, fetcher):
    task = job['task']; repo = task['repository']; suffix = task['source_suffix']
    key = b.sha(b.canonical([repo.lower(), suffix]))
    out = root / 'sources' / key
    if (out / 'outcome.json').exists():
        return b.load(out / 'outcome.json')
    result = {'repository': repo, 'source_suffix': suffix, 'admission': False,
              'original_failure': job['source_failure'], 'generation_started': False}
    try:
        old = recovery.PARENT / 'sources' / key / 'repositories' / repo.replace('/', '--')
        # Successful safe extraction may already exist despite a later context failure.
        if not suffix and (old / 'snapshot.json').exists():
            source = b.load(old / 'snapshot.json')
            result.update(status='source_ready', snapshot=str(old / 'snapshot.json'),
                          snapshot_sha256=b.file_sha(old / 'snapshot.json'), commit=source['commit'], cache_reused=True)
        else:
            prior = job['source_failure'].get('error', '')
            if any(x in prior for x in ('download size limit', 'expanded archive limit', 'archive member limit',
                                         'specific_issue_or_pull_context_required', 'redirect refused')):
                raise ValueError('safety_or_scope_hold_not_retried')
            metadata = public_metadata(json.loads(fetcher.fetch(f'https://api.github.com/repos/{repo}', 2_000_000)))
            b.save(out / 'public-metadata.json', metadata)
            context = None
            if suffix and suffix[0] in ('issues', 'pull'):
                if len(suffix) != 2 or not suffix[1].isdigit():
                    raise ValueError('specific_issue_or_pull_context_required')
                issue = json.loads(fetcher.fetch(f'https://api.github.com/repos/{repo}/issues/{suffix[1]}', 2_000_000))
                context = {k: issue.get(k) for k in ('html_url', 'title', 'body', 'state')}
            old_pin = b.load(old / 'pin.json') if (old / 'pin.json').exists() else None
            if old_pin:
                commit = old_pin['commit']
            elif suffix and suffix[0] in ('tree', 'blob', 'commit'):
                # An ambiguous slash-containing ref is held, never silently mapped to HEAD.
                if len(suffix) < 2 or not re.fullmatch('[0-9a-f]{40}', suffix[1]):
                    raise ValueError('explicit_named_ref_requires_cpu_resolution_no_substitution')
                commit = suffix[1]
            else:
                ref = urllib.parse.quote(metadata['default_branch'], safe='')
                commit = json.loads(fetcher.fetch(f'https://api.github.com/repos/{repo}/commits/{ref}', 2_000_000))['sha']
            if not re.fullmatch('[0-9a-f]{40}', commit):
                raise ValueError('invalid pinned commit')
            out.mkdir(parents=True, exist_ok=True)
            archive = out / 'archive.tar.gz'
            if not archive.exists():
                data = fetcher.fetch(f'https://codeload.github.com/{repo}/tar.gz/{commit}', LIMIT)
                temporary = out / 'archive.partial'; temporary.write_bytes(data); os.replace(temporary, archive)
            with tempfile.TemporaryDirectory(dir=out) as temp:
                files = b.extract(archive, Path(temp) / 'files')
                if (out / 'files').exists():
                    if any(b.file_sha(out / 'files' / p) != digest for p, digest in files.items()):
                        raise ValueError('interrupted source drift')
                else:
                    os.replace(Path(temp) / 'files', out / 'files')
            snapshot = {'repository': repo, 'commit': commit, 'files': files, 'archive_sha256': b.file_sha(archive),
                        'license': 'Preserve pinned repository license; no inferred grant', 'public_metadata_sha256': b.file_sha(out / 'public-metadata.json')}
            b.save(out / 'snapshot.json', snapshot)
            result.update(status='source_ready', snapshot=str(out / 'snapshot.json'), snapshot_sha256=b.file_sha(out / 'snapshot.json'), commit=commit)
            if context is not None:
                b.save(out / 'source-context.json', context)
                result.update(context=str(out / 'source-context.json'), context_sha256=b.file_sha(out / 'source-context.json'))
    except Exception as exc:
        result.update(status='source_held', error=f'{type(exc).__name__}: {exc}')
    b.save(out / 'outcome.json', result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=recovery.ROOT)
    parser.add_argument('--execute', action='store_true', help='CPU source requests only; default writes inventory')
    args = parser.parse_args()
    plan = recovery.prepare(args.root)
    out = args.root / 'source-recovery'; out.mkdir(parents=True, exist_ok=True)
    with (out / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        grouped = {}
        for job in plan['jobs']:
            if job['kind'] == 'source':
                grouped.setdefault((job['task']['repository'].lower(), tuple(job['task']['source_suffix'])), []).append(job)
        inventory = {'task_count': sum(map(len, grouped.values())), 'distinct_sources': len(grouped),
                     'jobs': [[j['id'] for j in group] for group in grouped.values()], 'script': recovery.pin(__file__),
                     'plan_sha256': b.file_sha(args.root / 'plan.json'), 'admission': False}
        if (out / 'inventory.json').exists() and b.load(out / 'inventory.json') != inventory:
            raise ValueError('source recovery pin drift')
        b.save(out / 'inventory.json', inventory)
        if args.execute:
            fetcher = Fetcher(out)
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda group: resolve(group[0], out, fetcher), grouped.values()))
            b.save(out / 'completion.json', {'results': results, 'admission': False, 'generation_started': False})
        print(json.dumps({k: inventory[k] for k in ('task_count', 'distinct_sources')}))


if __name__ == '__main__':
    main()
