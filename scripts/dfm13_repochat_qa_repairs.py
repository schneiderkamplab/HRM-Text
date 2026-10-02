"""Additive source-grounded QA repairs followed by independent thinking review."""
import asyncio
import fcntl
from pathlib import Path
from types import SimpleNamespace
from scripts import dfm13_repochat_targeted_repair as repair
from scripts import dfm13_repochat_review_saved as audit

SOURCE = Path('data/dfm13/repochat-simple-qa-68-20261001-v1')
ROOT = Path('data/dfm13/repochat-qa-repairs-20261001-v1')
FEEDBACK = {
    'a7c9c0710fbbfe98171f98d1580364d69835f922c9697db7be60f6e605ed480a':
        'Narrow source-grounding repair: esphome/components/voice_kit/voice_kit.h declares VoiceKit as i2c::I2CDevice, configuration enums and firmware/DFU support. This does not establish USB configuration or that all audio algorithms are available upstream. Read the header, implementation and actual firmware configuration references. Identify what is implemented locally versus a linked external firmware source. Qualify external availability not verified in this snapshot. Preserve the useful navigation answer; do not invent algorithm locations.',
    '0473ded19862cbd5142535b3ff37804146bfe0173714f18b959da26d9e2ed455':
        'Narrow qualification repair: the pinned README describes Minimal as minimal changes, not maximum safety. Remove that unsupported guarantee while preserving the accurate project overview. Read the README; note that administrative system-wide changes are involved without inventing safety certification or claiming execution.',
}


async def run():
    b = repair.b
    pins = {str(Path(p).resolve()): b.file_sha(p) for p in
            (__file__, repair.__file__, audit.__file__, audit.probe.__file__, audit.probe.r.__file__)}
    manifest = {'pins': pins, 'source': str(SOURCE), 'feedback': FEEDBACK,
                'authorization': 'User requested narrow XMOS and WinUtil repairs with fresh independent review.',
                'admission': False}
    path = ROOT / 'repair-manifest.json'
    if path.exists() and b.load(path) != manifest:
        raise ValueError('repair implementation drift')
    b.save(path, manifest)
    # Reuse the frozen bounded native-tool runner in this isolated process only.
    repair.ROOT, repair.FEEDBACK = ROOT, FEEDBACK
    repair.q = SimpleNamespace(SOURCE=SOURCE, BASELINE=SOURCE,
                               probe=repair.q.probe, __file__=repair.q.__file__)
    await repair.run()
    await audit.run(SimpleNamespace(source=ROOT, root=ROOT / 'independent-review', ids=None, thinking=True))
    b.save(ROOT / 'completion.json', {'generation_sha256': b.file_sha(ROOT / 'summary.json'),
           'review_sha256': b.file_sha(ROOT / 'independent-review/summary.json'), 'admission': False})


if __name__ == '__main__':
    ROOT.mkdir(parents=True, exist_ok=True)
    with (ROOT / 'controller.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        asyncio.run(run())
