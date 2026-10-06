"""Versioned standalone-label parsing for DFM acceptability, without prose extraction."""
import unicodedata

ENGLISH = ({'yes', 'correct', 'right'}, {'no', 'incorrect', 'wrong'})
NATIVE = {
    # Conservative standalone yes/no labels for the DFM13 expansion.
    'lt': ({'taip'}, {'ne'}),
    'lv': ({'jā'}, {'nē'}),
    'sq': ({'po'}, {'jo'}),
    'be': ({'так'}, {'не'}),
    'bs': ({'da'}, {'ne'}),
    'bg': ({'да'}, {'не'}),
    'hr': ({'da'}, {'ne'}),
    'hu': ({'igen'}, {'nem'}),
    'lb': ({'jo'}, {'nee'}),
    'sr': ({'да', 'da'}, {'не', 'ne'}),
    'sk': ({'áno'}, {'nie'}),
    'sl': ({'da'}, {'ne'}),
    'fa': ({'بله'}, {'نه', 'خیر'}),
    'en': (set(), set()),
    'da': ({'ja', 'korrekt', 'rigtig', 'rigtigt'}, {'nej', 'ukorrekt', 'forkert', 'ikke korrekt'}),
    'nb': ({'ja', 'korrekt', 'riktig', 'rett'}, {'nei', 'ukorrekt', 'feil', 'galt', 'ikke korrekt'}),
    'nn': ({'ja', 'korrekt', 'rett', 'riktig'}, {'nei', 'ukorrekt', 'feil', 'gale', 'ikkje korrekt'}),
    'sv': ({'ja', 'korrekt', 'rätt', 'riktig'}, {'nej', 'inkorrekt', 'fel', 'felaktig', 'inte korrekt'}),
    'is': ({'já', 'rétt', 'réttur'}, {'nei', 'rangt', 'rangur', 'röng', 'ekki rétt'}),
    'fo': ({'ja', 'rætt', 'rættur', 'røtt'}, {'nei', 'skeivt', 'skeivur', 'skeiv', 'ikki rætt'}),
    'nl': ({'ja', 'juist', 'goed'}, {'nee', 'onjuist', 'fout', 'oncorrect', 'niet correct'}),
    'pl': ({'tak', 'poprawne', 'poprawny', 'poprawna', 'prawidłowe', 'prawidłowy', 'prawidłowa'},
           {'nie', 'niepoprawne', 'niepoprawny', 'niepoprawna', 'nieprawidłowe', 'nieprawidłowy', 'nieprawidłowa', 'błędne', 'błędny', 'błędna'}),
    'de': ({'ja', 'richtig', 'korrekt'}, {'nein', 'falsch', 'inkorrekt', 'nicht korrekt'}),
    'fr': ({'oui', 'correct', 'correcte', 'juste'}, {'non', 'incorrect', 'incorrecte', 'faux', 'fausse', 'erroné', 'erronée'}),
    'es': ({'sí', 'correcto', 'correcta'}, {'no', 'incorrecto', 'incorrecta', 'erróneo', 'errónea'}),
    'it': ({'sì', 'corretto', 'corretta', 'giusto', 'giusta'}, {'no', 'scorretto', 'scorretta', 'errato', 'errata', 'sbagliato', 'sbagliata', 'non corretto', 'non corretta'}),
    'cs': ({'ano', 'správně', 'správné', 'správný', 'správná'}, {'ne', 'nesprávně', 'nesprávné', 'nesprávný', 'nesprávná', 'špatně', 'chybné'}),
    'pt_pt': ({'sim', 'correto', 'correta', 'correcto', 'correcta', 'certo', 'certa'}, {'não', 'incorreto', 'incorreta', 'incorrecto', 'incorrecta', 'errado', 'errada'}),
    'fi': ({'kyllä', 'oikein', 'oikea'}, {'ei', 'väärin', 'väärä', 'virheellinen'}),
    'et': ({'jah', 'õige', 'korrektne'}, {'ei', 'vale', 'ebaõige', 'ebakorrektne', 'vigane'}),
    'ca': ({'sí', 'correcte', 'correcta'}, {'no', 'incorrecte', 'incorrecta', 'erroni', 'errònia'}),
    'el': ({'ναι', 'σωστό', 'σωστή', 'σωστός', 'ορθό', 'ορθή', 'ορθός'}, {'όχι', 'λάθος', 'λανθασμένο', 'λανθασμένη', 'λανθασμένος', 'εσφαλμένο', 'εσφαλμένη'}),
    'ro': ({'da', 'corect', 'corectă'}, {'nu', 'incorect', 'incorectă', 'greșit', 'greșită'}),
    'uk': ({'так', 'правильно', 'правильне', 'правильний', 'правильна', 'коректно', 'коректне', 'коректний', 'коректна'},
           {'ні', 'неправильно', 'неправильне', 'неправильний', 'неправильна', 'некоректно', 'некоректне', 'некоректний', 'некоректна', 'хибне', 'помилкове'}),
}


def normalize_label(text):
    text = unicodedata.normalize('NFC', text).casefold().strip()
    while text and (unicodedata.category(text[0]).startswith('P') or text[0].isspace()):
        text = text[1:]
    while text and (unicodedata.category(text[-1]).startswith('P') or text[-1].isspace()):
        text = text[:-1]
    return ' '.join(text.split())


def extract_semantic_label(text, language):
    if language not in NATIVE:
        raise ValueError('Unsupported acceptability language: ' + language)
    if not isinstance(text, str):
        return None
    label = normalize_label(text)
    positive, negative = NATIVE[language]
    if label in {normalize_label(x) for x in positive | ENGLISH[0]}:
        return 'correct'
    if label in {normalize_label(x) for x in negative | ENGLISH[1]}:
        return 'incorrect'
    return None


def semantic_pairs(samples, language):
    result = []
    for sample in samples:
        metadata = sample.get('metadata') or {}
        if metadata.get('language', language) != language:
            raise ValueError('Sample/task language mismatch')
        target = sample.get('target')
        if target not in ('correct', 'incorrect'):
            raise ValueError('Unknown acceptability target')
        output = sample.get('output') or {}
        truncated = any(c.get('stop_reason') == 'max_tokens' for c in output.get('choices', []))
        prediction = None if truncated else extract_semantic_label(output.get('completion'), language)
        result.append((target, prediction))
    return result
