#!/bin/bash
# DFM10 -> DFM11 handoff watchdog. Waits for the guarded runner to finish
# DFM10 with a matched receipt, then enables DFM11 and relaunches the
# runner. One attempt per state transition; every action is logged.
set -u
cd /work/dfm/HRM-Text
Q=data/rebuild_hf_dfm/serial-queue
PY=/home/ucloud/miniforge3/envs/hrm/bin/python
export PATH="/home/ucloud/miniforge3/envs/hrm/bin:$PATH"
log() { echo "$(date +%F\ %T) $*" >> logs/rebuild/dfm11-handoff.log; }

runner_alive() { pgrep -f "queue_dfm_hf_rebui[l]d run" >/dev/null; }
ver() { [ -f "$Q/dfm$1/verified.json" ] && "$PY" -c "import json;print(json.load(open('$Q/dfm$1/verified.json'))['status'])" 2>/dev/null; }
row_recipe() { "$PY" -c "import json;print(json.load(open('$Q/plan.json'))['rows'][$1 - 1]['recipe'])" 2>/dev/null; }
row_status() { "$PY" -c "import json;print(json.load(open('$Q/plan.json'))['rows'][$1 - 1]['status'])" 2>/dev/null; }

log "watchdog started"
while true; do
    sleep 300
    s10=$(ver 10); s11=$(ver 11)
    if [ "$s10" = "matched" ] && [ "$s11" != "matched" ] \
            && [ "$(row_recipe 11)" = "None" ] && ! runner_alive; then
        log "DFM10 matched; enabling DFM11"
        if "$PY" -m scripts.queue_dfm_hf_rebuild enable-dfm11 --queue "$Q" \
                >> logs/rebuild/dfm11-handoff.log 2>&1; then
            log "DFM11 enabled; relaunching runner"
            setsid "$PY" -m scripts.queue_dfm_hf_rebuild run --queue "$Q" \
                >> logs/rebuild/dfm9-runner7.log 2>&1 < /dev/null &
            log "runner relaunched (pid $!)"
        else
            log "enable-dfm11 FAILED; stopping watchdog"
            exit 1
        fi
    fi
    if [ "$s11" = "matched" ]; then
        log "DFM11 matched; chain complete"
        exit 0
    fi
    st=$(row_status 10); st11=$(row_status 11)
    if [ "$st" != "running" ] && [ "$st" != "pending" ] && [ "$st" != "done" ] \
            && [ "$st" != "blocked" ]; then
        log "unexpected DFM10 row status: $st"
    fi
    if [ "$st" = "blocked" ] && ! runner_alive && [ "$s10" != "matched" ]; then
        log "DFM10 row blocked and runner down; stopping watchdog for manual repair"
        exit 1
    fi
done
