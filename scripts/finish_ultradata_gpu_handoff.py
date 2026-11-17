"""Drain this UltraData audit, then let its paused owner clean up its servers."""

import json
import os
from pathlib import Path
import signal
import time


def identity(pid):
    try:
        return Path(f'/proc/{pid}/stat').read_text().split(') ', 1)[1].split()[19]
    except FileNotFoundError:
        return None


def main():
    root = Path('/work/dfm/HRM-Text')
    owner, client = 3154040, 3217260
    owner_id, client_id = identity(owner), identity(client)
    if not owner_id or not client_id:
        raise RuntimeError('Expected audit processes are missing')
    command = Path(f'/proc/{owner}/cmdline').read_bytes()
    if b'scripts.queue_dfm16_expansion' not in command:
        raise RuntimeError('Unexpected controller')
    state = root / 'data/dfm16/expansion-v1/converted/openbmb__UltraData-SFT-2605/audit/pipeline/state.json'
    # Pause only the orchestration process, not the independently running audit.
    os.kill(owner, signal.SIGSTOP)
    print('Controller paused; UltraData client and servers continue.', flush=True)
    while True:
        if identity(owner) != owner_id:
            raise RuntimeError('Controller identity changed; refusing to signal')
        phase = json.loads(state.read_text())['phase']
        client_alive = identity(client) == client_id
        if phase == 'complete':
            print('UltraData complete; requesting owner cleanup.', flush=True)
            break
        if phase == 'failed' or not client_alive:
            print(f'Audit stopped ({phase}); releasing owned servers without starting more work.', flush=True)
            break
        time.sleep(15)
    # Its SIGTERM handler enters finally and stops only its owned server tree.
    os.kill(owner, signal.SIGTERM)
    os.kill(owner, signal.SIGCONT)
    while identity(owner) == owner_id:
        time.sleep(5)
    server_root = root / 'logs/dfm16/expansion-20261027/servers-1793157360578290570'
    for gpu in range(8):
        receipt = json.loads((server_root / f'gpu{gpu}/cleanup.json').read_text())
        if receipt['survivors']:
            raise RuntimeError(f'Owned survivors on GPU {gpu}: {receipt}')
    print('Owned servers cleaned up on all eight GPUs. Qwen handoff ready.', flush=True)


if __name__ == '__main__':
    main()
