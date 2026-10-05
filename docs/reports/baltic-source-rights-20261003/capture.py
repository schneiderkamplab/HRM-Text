"""Capture the two reviewed publisher PDFs and primary license texts, CPU only."""
import json
from pathlib import Path
from pypdf import PdfReader
from datetime import datetime, timezone
import requests
from dfm12.finepdf_rights_subset import DOCS
from dfm12.io import file_hash, write_json

root = Path(__file__).parent / 'evidence'
root.mkdir(exist_ok=True)
if (root/'receipt.json').exists():
    raise ValueError('Already sealed; preserve evidence')
urls = {doc['evidence']: doc['url'] for doc in DOCS.values()}
urls.update({'CC-BY-4.0.txt': 'https://creativecommons.org/licenses/by/4.0/legalcode.txt',
             'ODC-BY-1.0.html': 'https://opendatacommons.org/licenses/by/1-0/'})
responses = {}
for name, url in urls.items():
    path = root / name
    response = requests.get(url, timeout=60)
    response.raise_for_status()
    if name.endswith('.pdf') and not response.content.startswith(b'%PDF'):
        raise ValueError('Publisher returned non-PDF')
    if path.exists() and path.read_bytes() != response.content:
        raise ValueError('Changed evidence during unsealed capture')
    if not path.exists():
        path.write_bytes(response.content)
    responses[name] = dict(url=url, final_url=response.url, sha256=file_hash(path))
    if name.endswith('.pdf'):
        path.with_suffix('.txt').write_text('\n'.join(page.extract_text() for page in PdfReader(path).pages))
        if 'Creative Commons Attribution 4.0' not in path.with_suffix('.txt').read_text():
            raise ValueError('Expected reviewed document license notice absent')
write_json(root/'receipt.json', dict(time=datetime.now(timezone.utc).isoformat(), documents=DOCS,
    document_license='cc-by-4.0', database_license='odc-by-1.0', responses=responses,
    files={p.name:file_hash(p) for p in root.iterdir() if p.is_file()},
    scope='Two exact LT documents only; other documents, domains and LV remain unapproved'))
print(json.dumps(responses, indent=2))
