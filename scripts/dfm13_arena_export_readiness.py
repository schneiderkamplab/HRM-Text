"""Read-only export-preparation guard. This module never exports or admits rows."""
import argparse
import copy
import fcntl
from pathlib import Path
import sqlite3
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from dfm12.io import digest, file_hash, load, write_json
from dfm12.multilingual_calibration_v6 import strict_json

HOLDS=ROOT/'docs/reports/dfm13_bulk_repair_independent_holds_20261001.json'
ASSESSMENT=ROOT/'docs/reports/dfm13_bulk_repair_sample_assessment_20261001.md'
ORIGINAL_ASSESSMENT=ROOT/'docs/reports/dfm13_original_keep_manual10_20261001.md'


def resolve(path):
    path=Path(path)
    return (path if path.is_absolute() else ROOT/path).resolve()


def blocked(record, ledger, holds):
    if holds.get('schema')!='dfm13-independent-quality-holds-v1':
        raise ValueError('Unknown hold schema')
    findings=[]
    for hold in holds['holds']:
        if hold.get('disposition') not in ('hard_hold','verification_hold'):
            raise ValueError('Unknown hold disposition; explicit reconciliation required')
        same_hash=hold['candidate_sha256']==record['candidate_sha256']
        same_identity=(resolve(hold['ledger'])==resolve(ledger) and hold['seq']==record['seq'])
        same_source=bool(hold.get('source_id')) and hold['source_id']==record.get('source_id')
        if same_hash or same_identity or same_source:
            # A changed candidate hash does not silently release a source-level hold.
            findings.append(dict(seq=record['seq'],candidate_sha256=record['candidate_sha256'],
                held_candidate_sha256=hold['candidate_sha256'],reason=hold['reason'],
                release_required=True))
    return findings


def source_row(db, manifest, seq, checked):
    job=db.execute('SELECT source,source_id,offset,length,status,result,line FROM jobs WHERE seq=?',(seq,)).fetchone()
    if not job:
        raise ValueError('Missing source job')
    index,sid,offset,length,status,raw,line=job
    source=manifest['sources'][index]
    path=resolve(source['path'])
    if path not in checked:
        if file_hash(path)!=source['sha256']:
            raise ValueError('Source file hash drift')
        checked.add(path)
    with path.open('rb') as stream:
        stream.seek(offset)
        candidate=strict_json(stream.read(length).decode())
    target=candidate.get('target_message_index')
    messages=candidate.get('messages',[])
    if (candidate.get('id')!=sid or type(target) is not int or
            not 0<=target<len(messages) or messages[target].get('role')!='assistant'):
        raise ValueError('Source identity/assistant target drift')
    audit=strict_json(raw) if raw else None
    if audit and (audit.get('seq')!=seq or audit.get('source_line')!=line
                  or audit.get('row_sha256')!=digest(candidate) or audit.get('source_id')!=sid
                  or audit.get('source_sha256')!=source['sha256']):
        raise ValueError('Source audit provenance hash drift')
    return candidate,status,audit,source,line


def completed_stage(db, seq, stage, result):
    rows=db.execute("SELECT n,hash,record FROM attempts WHERE seq=? AND stage=? AND status='complete'",(seq,stage)).fetchall()
    if len(rows)!=1:
        raise ValueError('Expected one completed '+stage+' attempt')
    n,request_hash,raw=rows[0]
    attempt=strict_json(raw)
    if (attempt.get('seq')!=seq or attempt.get('stage')!=stage or attempt.get('attempt')!=n
            or attempt.get('status')!='complete' or attempt.get('finish_reason')!='stop'
            or not request_hash or attempt.get('request_sha256')!=request_hash
            or not attempt.get('raw_request_id') or attempt.get('result')!=result):
        raise ValueError('Completed '+stage+' evidence mismatch')
    return attempt


def check_selection(ledger, selection, holds, evidence=None):
    findings=[]
    seen=set()
    checked=set()
    proofs=[]
    classes={'original':0,'recovered':0,'repaired':0}
    root=resolve(ledger).parent
    with sqlite3.connect('file:'+str(resolve(ledger))+'?mode=ro',uri=True) as db:
        db.execute('BEGIN')
        repair_root=(root/'plan.json').exists()
        if repair_root:
            plan=load(root/'plan.json')
            if file_hash(root/'plan.json')!=load(root/'seal.json')['sha256']:
                raise ValueError('Repair plan seal drift')
            manifest=plan['manifest']
            source_root=resolve(plan['source'])
            for name in ('manifest.json','seal.json'):
                path=source_root/name
                if file_hash(path)!=plan['pins'].get(str(path)):
                    raise ValueError('Repair source pin drift')
            if load(source_root/'manifest.json')!=manifest:
                raise ValueError('Repair manifest lineage drift')
            if file_hash(root/'input.sqlite')!=load(root/'snapshot.json')['sha256']:
                raise ValueError('Repair input snapshot drift')
        else:
            manifest=load(root/'manifest.json')
            if file_hash(root/'manifest.json')!=load(root/'seal.json')['manifest_sha256']:
                raise ValueError('Original manifest drift')
        source_db=sqlite3.connect('file:'+str(root/'input.sqlite')+'?mode=ro',uri=True) if repair_root else db
        try:
            return _selection_rows(db,source_db,manifest,selection,holds,ledger,repair_root,
                                   checked,seen,proofs,classes,findings,evidence)
        finally:
            if source_db is not db:
                source_db.close()


def _selection_rows(db, source_db, manifest, selection, holds, ledger, repair_root,
                    checked, seen, proofs, classes, findings, evidence):
        for item in selection['candidates']:
            seq=item['seq']
            if type(seq) is not int or seq in seen:
                raise ValueError('Duplicate/invalid selected seq')
            seen.add(seq)
            kind=item.get('kind','repaired')
            if kind not in classes or (kind=='original')==repair_root:
                raise ValueError('Candidate kind/ledger mismatch; original keeps use original jobs ledger')
            original,status,audit,source,line=source_row(source_db,manifest,seq,checked)
            original_hash=digest(original)
            sid=original['id']
            proof=dict(seq=seq,kind=kind,original_row_sha256=original_hash,audit=audit)
            if kind=='original':
                if status!='complete' or not audit or audit.get('result',{}).get('verdict')!='keep':
                    raise ValueError('Original candidate is not a keep')
                if original_hash!=item['candidate_sha256']:
                    raise ValueError('Original candidate hash drift')
                findings.extend(blocked(dict(seq=seq,source_id=sid,candidate_sha256=original_hash),ledger,holds))
                classes[kind]+=1
                proofs.append(proof)
                continue
            row=db.execute('SELECT record FROM accepted WHERE seq=?',(seq,)).fetchone()
            if not row:
                raise ValueError('Selected row is not an accepted candidate')
            record=strict_json(row[0])
            if (record.get('seq')!=seq or record.get('source_id')!=sid or record.get('source_line')!=line
                    or record.get('original_row_sha256')!=original_hash
                    or record.get('source')!={k:source[k] for k in ('path','sha256')}
                    or record.get('original_audit')!=audit):
                raise ValueError('Accepted candidate provenance drift')
            for table in ('rejected','needs_review'):
                if db.execute(f'SELECT 1 FROM {table} WHERE seq=?',(seq,)).fetchone():
                    raise ValueError('Conflicting terminal dispositions')
            decision=record.get('decision',{})
            if status=='complete':
                if not audit or decision!=audit.get('result'):
                    raise ValueError('Original decision drift')
            elif status in ('invalid_response','abort_status_unknown','preflight_blocked'):
                proof['retry_audit']=completed_stage(db,seq,'retry_audit',decision)
            else:
                raise ValueError('Source job is not terminal')
            if kind=='recovered':
                if (status=='complete' or decision.get('verdict')!='keep' or
                        any(record.get(k) is not None for k in ('candidate','candidate_sha256','correction','fresh_reaudit'))):
                    raise ValueError('Expected recovered unchanged keep')
                actual=original_hash
            else:
                correction=record.get('correction',{})
                review=record.get('fresh_reaudit',{})
                if (decision.get('verdict')!='repair' or correction.get('status')!='corrected'
                        or not isinstance(correction.get('content'),str) or not correction['content'].strip()
                        or review.get('verdict')!='keep'):
                    raise ValueError('Expected correction and completed fresh keep')
                expected=copy.deepcopy(original)
                expected['messages'][original['target_message_index']]['content']=correction['content']
                if record.get('candidate')!=expected:
                    raise ValueError('Correction modified history/tools or mismatched target content')
                actual=digest(expected)
                if actual!=record.get('candidate_sha256'):
                    raise ValueError('Candidate hash drift')
                proof['correction']=completed_stage(db,seq,'correction',correction)
                proof['fresh_reaudit']=completed_stage(db,seq,'fresh_reaudit',review)
            if actual!=item['candidate_sha256']:
                raise ValueError('Candidate hash drift')
            findings.extend(blocked(dict(seq=seq,source_id=sid,candidate_sha256=actual),ledger,holds))
            proof['accepted']=record
            proofs.append(proof)
            classes[kind]+=1
        if not seen:
            raise ValueError('Empty selection')
        if evidence is not None:
            evidence.update(classifications=classes,selection_evidence_sha256=digest(proofs))
        return findings


def terminal_ready(ledger):
    root=resolve(ledger).parent
    try:
        with (root/'controller.lock').open('rb') as handle:
            fcntl.flock(handle,fcntl.LOCK_EX|fcntl.LOCK_NB)
            with sqlite3.connect('file:'+str(resolve(ledger))+'?mode=ro',uri=True) as db:
                db.execute('BEGIN')
                if (root/'plan.json').exists():
                    total=load(root/'plan.json')['manifest']['total']
                    counts={t:db.execute(f'SELECT count(*) FROM {t}').fetchone()[0]
                            for t in ('accepted','rejected','needs_review')}
                    unique=db.execute('SELECT count(*) FROM (SELECT seq FROM accepted UNION SELECT seq FROM rejected UNION SELECT seq FROM needs_review)').fetchone()[0]
                    return ((root/'complete.json').exists() and load(root/'complete.json').get('counts')==counts
                            and unique==sum(counts.values())==total
                            and db.execute("SELECT count(*) FROM attempts WHERE status='inflight'").fetchone()[0]==0)
                counts=dict(db.execute('SELECT status,count(*) FROM jobs GROUP BY status'))
                return (sum(counts.values())==load(root/'manifest.json')['total'] and
                        set(counts)<= {'complete','invalid_response','abort_status_unknown','preflight_blocked'})
    except (BlockingIOError,FileNotFoundError):
        return False


def review_matches(receipt, selection_path, holds_path, assessment_path, selected):
    if not (receipt.get('approved') is True and receipt.get('whole_target_reviewed') is True
            and receipt.get('terminal_review') is True and receipt.get('reviewer')
            and receipt.get('selection_sha256')==file_hash(selection_path)
            and receipt.get('holds_sha256')==file_hash(holds_path)
            and receipt.get('assessment_sha256')==file_hash(assessment_path)):
        return False
    scope=receipt.get('review_scope','whole_selection')
    if scope=='whole_selection':
        return True
    basis=receipt.get('sample_basis',{})
    count=basis.get('reviewed_count')
    return (scope=='sample' and type(count) is int and 0<count<=selected
            and basis.get('population_count')==selected and bool(basis.get('method'))
            and bool(basis.get('limitations')))


def prepare(ledger, selection_path, output, manual_review=None, holds_path=HOLDS, assessment_path=ASSESSMENT):
    if output.exists():
        raise ValueError('New readiness receipt required')
    holds=strict_json(holds_path.read_text())
    selection=strict_json(selection_path.read_text())
    evidence={}
    findings=check_selection(ledger,selection,holds,evidence)
    terminal=terminal_ready(ledger)
    pins={str(p.resolve()):file_hash(p) for p in (holds_path,assessment_path,selection_path,
        Path(__file__),ROOT/'tests/test_dfm13_arena_export_readiness.py')}
    if holds_path.resolve()==HOLDS.resolve():
        pins[str(ORIGINAL_ASSESSMENT.resolve())]=file_hash(ORIGINAL_ASSESSMENT)
    for hold in holds['holds']:
        if hold.get('assessment_path'):
            path=resolve(hold['assessment_path'])
            pins[str(path)]=file_hash(path)
    reviewed=False
    receipt={}
    if manual_review:
        receipt=strict_json(manual_review.read_text())
        reviewed=review_matches(receipt,selection_path,holds_path,assessment_path,len(selection['candidates']))
        if not reviewed:
            raise ValueError('Manual terminal review must bind selection, holds and assessment; sample review needs an explicit basis')
        pins[str(manual_review.resolve())]=file_hash(manual_review)
    status=('blocked_independent_hold' if findings else
            'terminal_review_required' if not terminal else
            'ready_for_separate_export_authorization' if reviewed else 'manual_quality_review_required')
    result=dict(version='dfm13-repaired-export-readiness-v2',ledger=str(resolve(ledger)),
        selection=str(selection_path.resolve()),holds=str(holds_path.resolve()),
        assessment=str(assessment_path.resolve()),manual_review=str(manual_review.resolve()) if manual_review else None,
        original_keep_assessment=str(ORIGINAL_ASSESSMENT.resolve()) if holds_path.resolve()==HOLDS.resolve() else None,
        pins=pins,status=status,selected=len(selection['candidates']),blocked=findings,
        **evidence,terminal=terminal,review_scope=receipt.get('review_scope'),
        sample_basis=receipt.get('sample_basis'),quality_certified=False,
        export_authorized=False,upload_authorized=False,active_ledger_modified=False)
    write_json(output,result)
    return result


def enforce(receipt_path):
    receipt=load(receipt_path)
    for path,expected in receipt['pins'].items():
        if file_hash(path)!=expected:
            raise ValueError('Readiness pin drift: '+path)
    evidence={}
    findings=check_selection(receipt['ledger'],strict_json(Path(receipt['selection']).read_text()),
                             strict_json(Path(receipt['holds']).read_text()),evidence)
    if evidence['selection_evidence_sha256']!=receipt.get('selection_evidence_sha256'):
        raise ValueError('Readiness evidence drift')
    if findings or receipt['status']!='ready_for_separate_export_authorization':
        raise ValueError('Export blocked by independent hold or missing manual quality review')
    if not terminal_ready(receipt['ledger']):
        raise ValueError('Export blocked: pipeline is not terminal/unlocked')
    manual=strict_json(Path(receipt['manual_review']).read_text())
    if not review_matches(manual,receipt['selection'],receipt['holds'],receipt['assessment'],receipt['selected']):
        raise ValueError('Manual review scope drift')
    return receipt


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=['prepare','verify'])
    parser.add_argument('--ledger',type=Path)
    parser.add_argument('--selection',type=Path)
    parser.add_argument('--receipt',type=Path,required=True)
    parser.add_argument('--manual-review',type=Path)
    args=parser.parse_args()
    if args.command=='verify':
        enforce(args.receipt)
    else:
        print(prepare(args.ledger,args.selection,args.receipt,args.manual_review)['status'])


if __name__=='__main__':
    main()
