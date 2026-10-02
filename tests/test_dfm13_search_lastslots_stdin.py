from io import StringIO
import pytest
from scripts.dfm13_search_lastslots_stdin import read_credential


def test_single_line_in_memory():
    assert read_credential(StringIO('test-placeholder\n')) == 'test-placeholder'


@pytest.mark.parametrize('value', ['', 'has space\n', 'x' * 4097])
def test_malformed_input_rejected_without_echo(value):
    with pytest.raises(ValueError, match='expected one nonempty credential line'):
        read_credential(StringIO(value))
