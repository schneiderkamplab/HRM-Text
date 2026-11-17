"""Add the full matched EMA suite, contingent on Muon training and export."""
import time
from collections import Counter
import json

import schedule_mimir2_3820k as base
from schedule_muon_pilot import RUN, EXPORT, SUCCESSOR
from recover_pilot_evaluations_20261022 import clone, terminal, SOURCE
from eval_scheduler.model import JobStatus


def main():
    store = base.SQLiteJobStore(base.plan_database(base.base.PLAN / 'plan.tsv'))
    assert not store.get_admin_lock()
    store.set_admin_lock(True)
    try:
        jobs = store.load_jobs()
        by_id = {j.job_id: j for j in jobs}
        prefix = 'mimir2-muon-3820000-'
        assert not any(j.job_id.startswith(prefix) for j in jobs)
        assert by_id[RUN].status == by_id[SUCCESSOR].status == JobStatus.PENDING
        rows = clone([j for j in jobs if j.job_id.startswith(SOURCE)], prefix,
            base.ROOT / 'logs/scheduler/mimir2_muon_3820000', RUN, EXPORT, RUN,
            validate_export=False)
        end = terminal(prefix, rows)
        rows.append(end)
        updated = []
        for j in jobs:
            if j.job_id == SUCCESSOR:
                updated.extend(rows)
                j = j.with_updates(deps=(*j.deps, end.job_id))
            updated.append(j)
        store.backup(base.base.PLAN / f'before-muon-evals-{int(time.time())}.sqlite')
        store.import_jobs(updated, preserve_runtime=True, require_admin_lock=True)
        store.export_tsv(base.base.PLAN / 'plan.tsv')
        print(json.dumps(dict(run=RUN, rows=len(rows),
            actions=dict(Counter(j.action.value for j in rows))), indent=2))
    finally:
        store.set_admin_lock(False)
        store.backup(base.base.PLAN / 'state.backup.sqlite')


if __name__ == '__main__':
    main()
