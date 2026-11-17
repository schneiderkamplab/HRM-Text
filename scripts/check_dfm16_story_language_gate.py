"""Small diagnostic of the Qwen prose-quality gate; does not admit training data."""
from scripts.queue_dfm16_stories_qwen import DEFAULT, prepare_stage, run_stage
from scripts.dfm16_story_v3 import AUDITOR
from dfm12.io import rows, write_json
import time


def main():
    base = DEFAULT.resolve()
    records = [dict(row, audit_id=row['id']) for row in rows(base/'manual-review.jsonl')]
    prepare_stage(base/'language-check', records, 'diagnostic_language_check')
    run_stage(base, 'language-check', 'story-language', [8505, 8506, 8507], AUDITOR, 128)
    write_json(base/'status.json', dict(phase='quality_hold', production_authorized=False,
        diagnostic_complete=True, time=time.time(),
        note='Review diagnostic against manual findings; no automatic admission or scale-up'))


if __name__ == '__main__':
    main()
