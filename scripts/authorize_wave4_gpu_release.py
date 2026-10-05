"""Issue factual GPU-release receipt after the user-authorized final GPU pass."""
import time

from dfm12.io import load,lock,write_json
from scripts import resume_xl_after_wave4 as watcher


def main():
    root=watcher.WORK
    with lock(root/'release-gate.lock'):
        authorization=load(root/'release-authorization.json')
        if (authorization.get('no_additional_gpu_work') is not True
                or authorization.get('cpu_recovery_may_continue') is not True
                or authorization.get('authorize_existing_dfm12_resume') is not True):
            raise ValueError('Explicit current-pass release authorization required')
        armed=load(root/'armed.json')
        launch=load(watcher.CAMPAIGN/'supervisor-launch.json')
        try:
            while time.time()<armed['deadline']:
                watcher.verify_pins(armed)
                terminal=watcher.CAMPAIGN/'terminal.json'
                if terminal.exists():
                    document=load(terminal)
                    if watcher.pass_finished(document,launch):
                        ready,details=watcher.gate_servers()
                        if ready:
                            write_json(root/'gpu-work-complete.json',dict(time=time.time(),
                                gpu_work_complete=True,all_shared_gpu_clients_finished=True,
                                remaining_gpu_work=0,recovery_disposition_final=True,
                                recovery_disposition='User authorized CPU-only recovery; no further GPU work',
                                authorize_training_resume=True,cpu_recovery_may_continue=True,
                                campaign_root=str(watcher.CAMPAIGN),server_root=str(watcher.SERVERS),
                                plan=str(watcher.PLAN),terminal=document,quiescence=details))
                            return
                    elif not watcher.same(launch):
                        raise RuntimeError('GPU pass failed; no automatic release')
                time.sleep(10)
            raise TimeoutError('Release gate deadline')
        except BaseException as exc:
            write_json(root/'release-gate-error.json',dict(time=time.time(),error=repr(exc)))
            raise


if __name__=='__main__':main()
