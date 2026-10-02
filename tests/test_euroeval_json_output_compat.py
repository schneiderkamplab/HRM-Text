import json

import pytest

from scripts.euroeval_json_output_compat import install_json_output_guard


class Adapter:
    @staticmethod
    def _create_model_output(generation_output):
        if 'label' in generation_output:
            try:
                generation_dct = json.loads(generation_output)
                assert isinstance(generation_dct, dict)
                if set(generation_dct) == {'label'}:
                    generation_output = str(generation_dct['label']).strip()
            except json.JSONDecodeError:
                pass
        return generation_output


def test_non_object_json_preserved_and_classification_unchanged():
    class Model(Adapter):
        pass
    with pytest.raises(AssertionError):
        Model._create_model_output('[{"label": "x"}]')
    assert install_json_output_guard(Model)
    for text in ['[{"label": "x"}]', '"label"', 'ordinary label prose',
                 '{"label":"x","other":1}', 'plain answer']:
        assert Model._create_model_output(text) == text
    assert Model._create_model_output('{"label":" yes "}') == 'yes'
    assert not install_json_output_guard(Model)


def test_other_assertions_not_suppressed():
    class Model:
        @staticmethod
        def _create_model_output(generation_output):
            assert generation_output == 'valid'
            return generation_output
    assert not install_json_output_guard(Model)
    with pytest.raises(AssertionError):
        Model._create_model_output('bad')
