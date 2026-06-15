#!/usr/bin/env python3
"""Summarize scheduler eval-attempt telemetry TSV files."""

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from pathlib import Path
from statistics import median


def as_int(value: str) -> int | None:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("telemetry", nargs="+", type=Path)
    args = parser.parse_args()

    rows: list[dict[str, str]] = []
    for path in args.telemetry:
        with path.open(newline="", encoding="utf-8") as handle:
            rows.extend(csv.DictReader(handle, delimiter="\t"))

    groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        groups[(row.get("kind", ""), row.get("task", ""))].append(row)

    print(
        "\t".join(
            [
                "kind",
                "task",
                "attempts",
                "successes",
                "ooms",
                "best_success_batch",
                "min_success_free_mib",
                "median_success_free_mib",
                "max_oom_batch",
                "max_oom_free_mib",
            ]
        )
    )
    for (kind, task), task_rows in sorted(groups.items()):
        success_rows = [row for row in task_rows if row.get("status") == "0" and row.get("oom") != "1"]
        oom_rows = [row for row in task_rows if row.get("oom") == "1"]

        success_batches = [as_int(row.get("batch_size", "")) for row in success_rows]
        success_batches = [batch for batch in success_batches if batch is not None]
        success_free = [as_int(row.get("free_before_mib", "")) for row in success_rows]
        success_free = [free for free in success_free if free is not None]
        oom_batches = [as_int(row.get("batch_size", "")) for row in oom_rows]
        oom_batches = [batch for batch in oom_batches if batch is not None]
        oom_free = [as_int(row.get("free_before_mib", "")) for row in oom_rows]
        oom_free = [free for free in oom_free if free is not None]

        print(
            "\t".join(
                [
                    kind,
                    task,
                    str(len(task_rows)),
                    str(len(success_rows)),
                    str(len(oom_rows)),
                    str(max(success_batches) if success_batches else ""),
                    str(min(success_free) if success_free else ""),
                    str(int(median(success_free)) if success_free else ""),
                    str(max(oom_batches) if oom_batches else ""),
                    str(max(oom_free) if oom_free else ""),
                ]
            )
        )


if __name__ == "__main__":
    main()
