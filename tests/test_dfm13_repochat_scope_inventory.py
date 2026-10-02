import pytest
from scripts.dfm13_repochat_scope_inventory import category


@pytest.mark.parametrize('query', ['Write an implementation', 'Where are all the supported formats?', 'Describe the complete project architecture', 'Which file should I modify to fix this?', 'What does this repository do and how do I exploit it?'])
def test_high_risk_or_exhaustive_not_selected(query):
    assert category(query) is None


def test_bounded_candidates():
    assert category('Where is the main path integrator?') == 'bounded_navigation_candidate'
    assert category('What is this repository about?') == 'repository_overview_candidate'
    assert category('Translate this paragraph') is None
