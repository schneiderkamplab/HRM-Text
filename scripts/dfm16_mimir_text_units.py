"""Prepare independent prose judgments without exposing conversation wrappers."""


def text_units(records):
    for row in records:
        for turn, message in enumerate(row['messages']):
            text = message.get('content')
            if message.get('role') != 'assistant' or not isinstance(text, str) or not text.strip():
                continue
            # Preserve each response intact; do not split a story into sentences.
            for aspect, question in (
                ('language', 'Is the text grammatically acceptable and naturally written?'),
                ('coherence', 'Is the text understandable and internally coherent?'),
            ):
                identifier = f'{row["id"]}/turn-{turn}/{aspect}'
                yield dict(id=identifier, audit_id=identifier, parent_id=row['id'],
                    turn_index=turn, language=row['language'], task=row['task'],
                    comparison_cohort=row['comparison_cohort'], aspect=aspect,
                    unit='assistant_response', text=text,
                    prompt=f'Text:\n{text}\n\n{question} Answer only yes or no.')
