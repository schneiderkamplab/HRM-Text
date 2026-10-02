"""Bound bracketed plain URLs before adjacent CJK prose; preserve source identity."""
import re
from scripts import dfm13_search_links_v4 as previous


def parse_view(answer):
    # This view is used only for URL parsing, never persisted as candidate text.
    return re.sub(r'\[(https?://[^\s\[\]<>]+)\](?!\()',lambda m:'[source]('+m[1]+')',answer)


def check(answer,pages,supporting_urls):
    return previous.check(parse_view(answer),pages,supporting_urls)
