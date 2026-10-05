import yaml
import pytest
from dfm12.wave_translation_release import card_languages


@pytest.mark.parametrize('pair,languages,variants',[
    ('lb-pt_pt',['lb','pt'],['lb','pt-PT']),
    ('pt_pt-sq',['pt','sq'],['pt-PT','sq']),
])
def test_affected_cards_keep_portuguese_variant(pair,languages,variants):
    before=pair
    card=yaml.safe_load(card_languages(pair))
    assert card=={'language':languages,'language_bcp47':variants}
    assert pair==before and 'pt_pt' in pair


def test_unaffected_card_has_no_variant_change():
    assert yaml.safe_load(card_languages('lb-sq'))=={'language':['lb','sq']}
