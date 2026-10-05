"""Offline production-capacity approval from pinned31B measurement evidence."""
import argparse
from pathlib import Path
from .io import load, write_json, file_hash
from .wave4_gemma31_download import MODEL, ROOT as DOWNLOAD


def validate(profile):
    ready=load(DOWNLOAD/'ready.json')
    if profile.get('model')!=MODEL or profile.get('revision')!=ready['revision']:
        raise ValueError('Wrong measured model/revision')
    c=profile.get('aggregate_client_concurrency_per_server');seq=profile.get('server_max_num_seqs')
    if type(c) is not int or not 1<=c<=64 or type(seq) is not int or not c<=seq<=1024:
        raise ValueError('Invalid measured capacity bounds')
    allocations=profile.get('client_allocations',{})
    if (set(allocations)!={'wave4','baltic'} or any(type(v) is not int or v<1 for v in allocations.values())
        or sum(allocations.values())>c):
        raise ValueError('Aggregate wave allocations exceed measured capacity')
    measurements=profile.get('measurements',[])
    if not measurements:raise ValueError('Actual measurements required')
    observed=[]
    for item in measurements:
        path=Path(item['path'])
        if file_hash(path)!=item['sha256']:raise ValueError('Measurement drift')
        m=load(path)
        if (m.get('model')!=MODEL or m.get('revision')!=ready['revision']
            or m.get('duration_seconds',0)<300 or set(m.get('servers',{}))!={str(p) for p in range(8800,8808)}):
            raise ValueError('Five-minute all-eight31B measurements required')
        for port,s in m['servers'].items():
            if (s.get('aggregate_concurrency')!=c or s.get('max_num_seqs')!=seq
                or type(s.get('completed')) is not int or s['completed']<=0
                or not 0<=s.get('kv_high_water',2)<=.90 or s.get('preemptions_delta')!=0
                or s.get('request_errors_delta')!=0 or s.get('oom_count')!=0
                or not isinstance(s.get('p95_seconds'),(float,int)) or s['p95_seconds']<=0):
                raise ValueError('Unstable or mismatched capacity measurement: '+port)
        observed.append(m)
    if profile.get('selected_after_ramp_review') is not True or not profile.get('reviewer'):
        raise ValueError('Ramp review missing; no automatic capacity approval')
    return c,seq


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--profile',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();profile=load(a.profile);c,seq=validate(profile)
    write_json(a.output,dict(model=MODEL,revision=profile['revision'],
        profile_sha256=file_hash(a.profile),aggregate_client_concurrency_per_server=c,
        server=dict(tensor_parallel_size=1,gpu_memory_utilization=.95,max_num_seqs=seq,
                    max_model_len=32768,max_num_batched_tokens=16384),
        admission_kv_limit=.90,not_a_launch_command=True,production_approval_separate=True))


if __name__=='__main__':main()
