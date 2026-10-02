"""Import completed European DaLA outputs using the existing isolated CPU pipeline."""
import argparse
import os
from pathlib import Path

from .dala_integrate import STANDARDS, TASKS, integrate, verify_inputs
from .dala_refresh import contained, evidence
from .dala_swedish import pin_previous
from .dala_verify import verify
from .european_expansion import ROOT
from .io import file_hash, load, lock, write_json

CONFIG = Path(__file__).with_name('dala_european_sources.yaml')


def snapshot(producer, output, selections):
    marker = output/'inputs.json'
    if marker.exists():
        saved = load(marker)
        if saved.get('european_selections') != selections:
            raise ValueError('European source selections changed')
        return saved
    sources, exclusions, pins = {}, {}, {}
    for lang, selection in selections.items():
        folder = contained(producer,selection['output'])
        status_path = producer/'wiki/artifacts/european-pilots'/selection['run']/(lang+'-status.json')
        status, status_receipt = evidence(status_path)
        if (status.get('language') != lang or status.get('exit_code') != 0
                or contained(producer,status['output']) != folder):
            raise ValueError('No successful selected producer output for '+lang)
        manifest, receipt = evidence(folder/'manifest.json')
        if manifest.get('language') != lang or str(manifest.get('schema_version')) != '2':
            raise ValueError('Wrong language/schema')
        for check in ('exact_edit_reconstruction','correction_roundtrip','document_split_isolation'):
            if manifest.get('verification',{}).get(check) is not True:
                raise ValueError('Missing producer verification: '+check)
        for task in TASKS:
            if STANDARDS[lang] not in manifest['prompts'][task].casefold():
                raise ValueError('Missing explicit language in prompt')
        profile_path = producer/'la_output/resources/european-expansion'/selection['run']/lang/'profile.json'
        profile, profile_receipt = evidence(profile_path)
        if profile_receipt['sha256'] != manifest['profile_sha256']:
            raise ValueError('Producer profile changed')
        review, review_receipt = [], None
        if profile['build'].get('review_exclusions'):
            review_path = contained(producer,profile['build']['review_exclusions'])
            review, review_receipt = evidence(review_path)
            if review_receipt['sha256'] != manifest['review_exclusions_sha256']:
                raise ValueError('Producer review exclusions changed')
        elif manifest.get('review_exclusions_sha256') is not None:
            raise ValueError('Review exclusions missing from profile')
        if not isinstance(review,list) or not all(isinstance(h,str) and len(h)==64 for h in review):
            raise ValueError('Unexpected review exclusion schema')
        exclusions[lang] = [dict(original_sha256=h) for h in review]
        pins[lang] = dict(status=status_receipt,profile=profile_receipt)
        if review_receipt:
            pins[lang]['review'] = review_receipt
        sources[lang] = dict(raw=str(folder),selected=str(folder),status_receipt=status_receipt,
            raw_manifest=manifest,selected_manifest=manifest,raw_receipt=receipt,selected_receipt=receipt)
    exclusion_path = output/'evidence/late-review-exclusions.json'
    write_json(exclusion_path,exclusions)
    result = dict(scope=list(selections),sources=sources,producer_finalized=False,
        producer_status='Selected per-language outputs complete; wider campaign still independent',
        excluded_running_languages=[],late_exclusions=exclusions,
        late_exclusions_receipt=dict(path=str(exclusion_path),sha256=file_hash(exclusion_path)),
        european_selections=selections,european_evidence=pins)
    write_json(marker,result)
    return result


def register(output, root):
    """Publish only verified immutable candidates, not accepted training data."""
    proof=load(output/'verification.json')
    if proof['integration_sha256'] != file_hash(output/'integration.json'):
        raise ValueError('Verification no longer covers integration')
    integration=load(output/'integration.json')
    with lock(root/'screened/.pipeline.lock'):
        marker=root/'local-integrations.json'
        state=load(marker) if marker.exists() else dict(components=[],integrations=[])
        for entry in integration['components']:
            source=Path(entry['path']).parent.resolve()
            if file_hash(entry['path']) != entry['sha256']:
                raise ValueError('Local DaLA candidates changed')
            dest=root/'candidates'/entry['component']
            if dest.exists() or dest.is_symlink():
                if not dest.is_symlink() or dest.resolve()!=source:
                    raise ValueError('Existing component has different ownership')
            else:
                dest.symlink_to(source,target_is_directory=True)
            if entry['component'] not in state['components']:
                state['components'].append(entry['component'])
        pin=dict(path=str(output/'integration.json'),sha256=file_hash(output/'integration.json'))
        if pin not in state['integrations']:
            state['integrations'].append(pin)
        state['pending'] = [p for p in state.get('pending',[]) if p != str(output)]
        write_json(marker,state)


def main():
    import yaml
    p=argparse.ArgumentParser(__doc__)
    p.add_argument('--output',type=Path,default=Path('data/dfm12/dala-fi-ca-cs-es-20260926-v1'))
    p.add_argument('--previous',type=Path,default=Path('data/dfm12/dala-pl-is-20260925-v1'))
    p.add_argument('--expansion-root',type=Path,default=ROOT)
    p.add_argument('--workers',type=int,default=8)
    args=p.parse_args()
    if not 1 <= args.workers <= 16:
        p.error('workers must be 1..16')
    cfg=yaml.safe_load(CONFIG.read_text())
    producer=Path(cfg['producer_root']).resolve()
    output,previous=args.output.resolve(),args.previous.resolve()
    if output.is_relative_to(producer) or output.is_relative_to(previous):
        raise ValueError('Separate import root required')
    os.environ.update(CUDA_VISIBLE_DEVICES='',TOKENIZERS_PARALLELISM='false',OMP_NUM_THREADS='1',
                      MKL_NUM_THREADS='1',OPENBLAS_NUM_THREADS='1',RAYON_NUM_THREADS='1')
    with lock(output/'.european-import.lock'):
        root = args.expansion_root.resolve()
        with lock(root/'screened/.pipeline.lock'):
            marker = root/'local-integrations.json'
            state = load(marker) if marker.exists() else dict(components=[],integrations=[],pending=[])
            for language in cfg['sources']:
                for task in TASKS:
                    name = f'dala-{language}-{task}'
                    if name not in state['components']:
                        state['components'].append(name)
            if str(output) not in state.setdefault('pending',[]):
                state['pending'].append(str(output))
            write_json(marker,state)
        inputs=snapshot(producer,output,cfg['sources'])
        for pin in inputs['european_evidence'].values():
            for item in pin.values():
                if file_hash(item['path'])!=item['sha256']:
                    raise ValueError('Producer evidence changed')
        seed=pin_previous(previous,output)
        integrate(producer,output,args.workers,tuple(cfg['sources']),seed,final_outputs=False)
        verify_inputs(inputs)
        verify(output,tuple(cfg['sources']))
        register(output,args.expansion_root.resolve())
    from .european_screen import run
    run(args.expansion_root.resolve(),workers=64)
    print('EUROPEAN_DALA_SCREENED_AND_QUEUED',output,flush=True)


if __name__ == '__main__':
    main()
