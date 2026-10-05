"""Freeze separately verified publisher evidence for one exact Latvian article."""
from pathlib import Path
import requests
from pypdf import PdfReader
from dfm12.io import file_hash, write_json

root = Path(__file__).parent/'evidence-lv'
root.mkdir(exist_ok=False)
url = 'https://journals.rta.lv/index.php/ER/article/download/6497/5538'
r = requests.get(url, timeout=60)
r.raise_for_status()
if not r.content.startswith(b'%PDF'):
    raise ValueError('Expected publisher PDF')
(root/'article.pdf').write_bytes(r.content)
text = '\n'.join(p.extract_text() for p in PdfReader(root/'article.pdf').pages)
if 'Creative Commons Attribution 4.0 International License' not in text:
    raise ValueError('Missing article license')
(root/'article.txt').write_text(text)
for name in ('CC-BY-4.0.txt', 'ODC-BY-1.0.html'):
    (root/name).write_bytes((root.parent/'evidence'/name).read_bytes())
docs = {'<urn:uuid:37076053-bd9b-4805-891f-5e5a51191efe>': dict(row=31841,
    url='http://journals.rta.lv/index.php/ER/article/download/6497/5538',
    author='Inese Brivere; Livija Levinska',
    title='Elements of Escape Games in Latvian History Lessons in Primary School Classes (2021)',
    evidence='article.pdf')}
write_json(root/'receipt.json', dict(documents=docs, document_license='cc-by-4.0',
    database_license='odc-by-1.0', primary_url=url, final_url=r.url,
    files={p.name:file_hash(p) for p in root.iterdir()},
    scope='Exact article 6497 only; no publisher-wide grant; page-one CC BY notice'))
print(file_hash(root/'receipt.json'))
