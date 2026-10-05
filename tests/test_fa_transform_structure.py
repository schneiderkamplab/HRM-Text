from scripts.diagnose_fa_transform_structure import classify, line_kind


def test_categories_not_prose():
    r = classify('منابع\n\nافراد زنده\nزادگان ۱۹۶۰ (میلادی)\nبازیکنان فوتبال اهل ایران')
    assert r['flags']['category_only']
    assert r['effective_prose_paragraphs'] == 0


def test_real_sentence_with_category_prefix_retained():
    text = 'بازیکنان این تیم در مسابقات سال گذشته شرکت کردند و موفق شدند.'
    assert line_kind(text) == 'prose'
    assert not classify(text)['flags']['category_only']


def test_unknown_list_not_certified_category():
    r = classify('عنوان نامعلوم\nیک عنوان دیگر\nبرچسب نامعلوم')
    assert r['uncertain_blocks'] == 1
    assert not r['flags']['category_only']


def test_headings_and_prose():
    assert classify('منابع\n\nپیوند به بیرون')['flags']['heading_only']
    r = classify('این بازیکن در تیم ملی فوتبال ایران بازی کرده است.\n\nوی همچنین در این باشگاه مشهور فوتبال بازی کرده است.\n\nمنابع')
    assert r['effective_prose_paragraphs'] == 2
    assert not r['flags']['heading_only']


def test_empty_field_heavy_not_every_typographical_issue():
    r = classify('رافائل مید (؛ زادهٔ ) بازیکن فوتبال اهل بریتانیا است.')
    assert r['flags']['empty_field_heavy']
    r = classify('رافائل مید (؛ زادهٔ ) بازیکن فوتبال اهل بریتانیا است.\n\nاین ورزشکار در تیم ملی فوتبال کشور خود بازی کرده است.')
    assert r['flags']['empty_field_present'] and not r['flags']['empty_field_heavy']
    assert not classify('او (زادهٔ ۱۹۸۲) بازیکن فوتبال اهل این کشور است.')['flags']['empty_field_present']


def test_function_calls_not_empty_fields():
    r = classify('%Eject();\nMcb := Message_Initialize();\nexample()')
    assert not r['flags']['empty_field_present']


def test_long_useful_prose_not_heavy_from_one_empty_pair():
    r = classify('نام () ' + 'این بازیکن در تیم ملی فوتبال کشور خود بازی کرده است. ' * 10)
    assert r['flags']['empty_field_present']
    assert not r['flags']['empty_field_heavy']
