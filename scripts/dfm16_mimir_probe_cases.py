"""Short grammaticality and instruction checks, positive and negative controls."""


def cases():
    language_pairs = {
        'da': [
            ('Kvinden kom ind i en m\u00f8rk frakke.', 'Kvinden kom ind i m\u00f8rkt frakke.'),
            ('Barnet l\u00e6ser en bog.', 'Barnet l\u00e6se en bog.'),
            ('Vores signal er d\u00f8dt.', 'Vores signal er d\u00f8d.'),
            ('Hun ville hj\u00e6lpe sin landsby.', 'Hun ville hj\u00e6lpe sit landsby.'),
        ],
        'en': [
            ('The child reads a book.', 'The child readed a books.'),
            ('They were waiting outside.', 'They was wait outside.'),
        ],
        'hi': [
            ('\u0935\u0939 \u091a\u093e\u092f \u0915\u0940 \u0915\u0947\u0924\u0932\u0940 \u0909\u0920\u093e\u0924\u093e \u0939\u0948\u0964',
             '\u0935\u0939 \u091a\u093e\u092f \u0915\u093e \u0915\u0947\u0924\u0932\u0940 \u0909\u0920\u093e\u0924\u093e \u0939\u0948\u0964'),
        ],
        'ja': [
            ('\u79c1\u306f\u672c\u3092\u8aad\u307f\u307e\u3059\u3002', '\u79c1\u306f\u672c\u3092\u8aad\u307f\u307e\u3059\u3060\u3002'),
        ],
    }
    for language, pairs in language_pairs.items():
        for index, pair in enumerate(pairs):
            for bad, text in enumerate(pair):
                prompt = (f'S\u00e6tning: {text}\n\nBestem om s\u00e6tningen er grammatisk korrekt eller ej. '
                          'Svar kun med ja eller nej, og intet andet.' if language == 'da' else
                          f'Is the following {language} sentence grammatically correct? '
                          f'Answer only yes or no.\n\n{text}')
                key = f'language-{language}-{index}-{bad}'
                yield dict(id=key, audit_id=key, language=language, task='sentence_grammar',
                    comparison_cohort='controlled_probe', prompt=prompt,
                    expected='reject' if bad else 'accept')
    content_pairs = [
        ('What is 2 + 2?', '4', '5'),
        ('Respond with exactly one word: name a color.', 'Blue', 'Light blue'),
        ('Summarize this fact: Alice visited Paris on Monday.',
         'Alice went to Paris on Monday.', 'Bob went to Rome on Tuesday.'),
        ('Change only the verb to past tense: She walks home.', 'She walked home.', 'He walked to school.'),
    ]
    for index, (instruction, good, bad) in enumerate(content_pairs):
        for wrong, answer in enumerate((good, bad)):
            key = f'content-{index}-{wrong}'
            yield dict(id=key, audit_id=key, language='en', task='correctness_instruction',
                comparison_cohort='controlled_probe', expected='reject' if wrong else 'accept',
                prompt=f'User request: {instruction}\nAssistant answer: {answer}\n\n'
                       'Does the assistant answer correctly follow the user request? Answer only yes or no.')
