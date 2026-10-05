"""Select direct native Persian tasks without repeated or reverse templates."""
from .wave4_instructions import convert


SELECTIONS = {
    'farstail': 'can_you_infer',
    'pn_sum': 'summarize_the_article',
    'wiki_sum': 'summarize_article',
    'persian_qa': 'answer_Q_A',
    'parsinlu_comp': 'give_short_answer',
}


def messages(row, template):
    if row['template'] != template:
        return None
    return [dict(role='user', content=row['inputs']),
            dict(role='assistant', content=row['outputs'])]


def main():
    for subset, template in SELECTIONS.items():
        convert('ParsiAI/FarsInstruct', 'fa', [f'{subset}/train-*.parquet'],
                lambda row, template=template: messages(row, template),
                selection='-' + subset)


if __name__ == '__main__':
    main()
