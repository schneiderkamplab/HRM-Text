import pytest
from scripts.dfm13_search_salvage_error4 import format_fix


def test_br_only():
    assert format_fix('99fe14a8','a<br>b [c](https://x)',{})=='a b [c](https://x)'
    with pytest.raises(ValueError):format_fix('99fe14a8','<a href="x">x</a>',{})


def test_exact_url_no_general_alias():
    old='https://liverpoolfc.com/news/alisson-becker-why-i-believe-we-have-started-season-so-well'
    new=old.replace('://', '://www.')
    assert format_fix('0cfb74ac',old,{new:{}})==new
    with pytest.raises(ValueError):format_fix('0cfb74ac',old,{})
    with pytest.raises(ValueError):format_fix('31dbdb34','uncited',{})
