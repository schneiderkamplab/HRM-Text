"""Preserve primary notice and local OPUS terms without changing source data."""
from pathlib import Path
from html.parser import HTMLParser
import requests
import zipfile
from dfm12.io import file_hash, write_json

root = Path(__file__).parent/'evidence-europarl'
root.mkdir(exist_ok=False)
url = 'https://www.europarl.europa.eu/legal-notice/en'
r = requests.get(url, timeout=60)
r.raise_for_status()
if 'Any partial reproduction' not in r.text:
    raise ValueError('Expected primary legal notice absent')
(root/'legal-notice.html').write_bytes(r.content)
class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
    def handle_data(self, data):
        if data.strip():
            self.parts.append(data.strip())
p = Text()
p.feed(r.text)
(root/'legal-notice.txt').write_text('\n'.join(p.parts))
archives = dict(lt=Path('/work/mimir/DaLA/la_output/resources/lithuanian-extension-v4/Europarl-v8-lt.zip'),
    lv=Path('/work/mimir/DaLA/la_output/resources/latvian-extension-v2/raw/europarl-lv.zip'))
pins = {}
for lang,path in archives.items():
    pins[lang] = dict(path=str(path), sha256=file_hash(path))
    with zipfile.ZipFile(path) as archive:
        for name in ('README', 'LICENSE'):
            (root/(lang+'-'+name+'.txt')).write_bytes(archive.read(name))
write_json(root/'receipt.json', dict(primary_url=url, final_url=r.url, status=r.status_code,
    archives=pins, files={p.name:file_hash(p) for p in root.iterdir()},
    disposition='No publication authorized by this evidence capture; scope assessment in report.md'))
