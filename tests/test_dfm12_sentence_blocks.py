import pytest

from dfm12.sentence_blocks import (complete_sentence, fallback_candidate,
                                   PROMPTS, sentence_spans, segmenter_info)


SENTENCES = [
    "Anna examined the old building beside the river with her friends.",
    "Before entering the building they carefully checked the wooden front door.",
    "Inside the first room they discovered several interesting historical objects.",
    "One of the objects was a small machine used by local workers.",
    "The group decided to photograph the machine before leaving the room.",
    "After their visit they returned to the village to discuss their findings.",
]


class Renderer:
    def count(self, messages):
        return 250


@pytest.mark.parametrize("lang,abbreviation", [("nb", "f.eks."), ("nn", "t.d."),
                                                ("sv", "t.ex."), ("nl", "bijv.")])
def test_abbreviations_do_not_count_as_sentences(lang, abbreviation):
    text = f"Dr. Hansen studied {abbreviation} several old buildings near the village. " + SENTENCES[0]
    spans = sentence_spans(text, lang)
    assert len(spans) == 2
    assert text[slice(*spans[0])].startswith("Dr. Hansen")
    assert complete_sentence(text[slice(*spans[0])], lang)


@pytest.mark.parametrize("quotes", [('"', '"'), ("\u00ab", "\u00bb"), ("\u201c", "\u201d"), ("\u201d", "\u201d")])
def test_quotes_keep_closer_and_offsets(quotes):
    text = quotes[0] + SENTENCES[0] + quotes[1] + " " + SENTENCES[1]
    spans = sentence_spans(text, "nn")
    assert len(spans) == 2
    assert text[slice(*spans[0])] == quotes[0] + SENTENCES[0] + quotes[1]
    assert complete_sentence(text[slice(*spans[0])], "nn")


def test_target_is_ordered_pairs_and_separate_task():
    text = " ".join(SENTENCES)
    result = fallback_candidate(text, "nn", {"document_hash": "d"}, Renderer())
    assert result["task"] == "text-block-reordering"
    assert result["provenance"]["synthetic_boundaries"] is True
    assert result["messages"][0]["content"].startswith(PROMPTS["nn"])
    selection = result["provenance"]["block_selection"]
    assert selection["sentences_per_block"] == [2, 2, 2]
    blocks = result["messages"][1]["content"].split("\n\n")
    assert blocks == [" ".join(SENTENCES[i:i + 2]) for i in (0, 2, 4)]
    assert blocks == [text[a:b] for a, b in selection["block_spans"]]
    assert result == fallback_candidate(text, "nn", {"document_hash": "d"}, Renderer())


@pytest.mark.parametrize("bad", ["Fragment without any terminal punctuation", "and this starts with a fragment.",
                                  '"This sentence has an unclosed quotation near the very end.',
                                  "Dr.", "This long but uncertain fragment stops in an ellipsis...",
                                  "This contains a broken template {{ which makes the sentence invalid."])
def test_uncertain_fragments_fail_closed(bad):
    assert not complete_sentence(bad, "nb")
    text = " ".join(SENTENCES[:3] + [bad] + SENTENCES[3:5])
    with pytest.raises(ValueError, match="no_six"):
        fallback_candidate(text, "nb", {"document_hash": "d"}, Renderer())


def test_no_joining_across_runs_or_headings():
    text = " ".join(SENTENCES[:3]) + "\nHeading\n" + " ".join(SENTENCES[3:])
    with pytest.raises(ValueError, match="no_six"):
        fallback_candidate(text, "sv", {"document_hash": "d"}, Renderer())


def test_at_least_six_sentences_and_distinct_blocks():
    for sentences in [SENTENCES[:5], [SENTENCES[0]] * 6]:
        with pytest.raises(ValueError, match="no_six"):
            fallback_candidate(" ".join(sentences), "nl", {"document_hash": "d"}, Renderer())


def test_render_limit_and_size_limit():
    class Oversize:
        def count(self, messages):
            return 4097
    with pytest.raises(ValueError, match="rendered_context"):
        fallback_candidate(" ".join(SENTENCES), "nl", {"document_hash": "d"}, Oversize())
    assert not complete_sentence("Very " + "long " * 300 + "sentence.", "nl")


def test_model_receipt_and_real_gemma_renderer():
    from dfm12.io import load
    from dfm12.prepare import Renderer as RealRenderer
    info = segmenter_info("nn")
    assert info["model"] == "norwegian"
    assert info["variant_caveat"]
    assert len(info["model_files"]) == 4
    renderer = RealRenderer(load("data/sampled_dfm11/metadata.json")["tokenizer_info"], 4096)
    result = fallback_candidate(" ".join(SENTENCES), "nn", {"document_hash": "d"}, renderer)
    assert 0 < result["rendered_tokens"] <= 4096


@pytest.mark.parametrize("lang,text", [
    ("nb", "Dr. Hansen kom til byen tidlig p\u00e5 dagen. Han bes\u00f8kte f.eks. skolen sammen med flere gode venner. \u00abDette er et veldig gammelt hus ved elva.\u00bb Hun gikk deretter videre til skolen sammen med familien."),
    ("nn", "Dr. Hansen kom til byen tidleg p\u00e5 dagen. Han s\u00e5g t.d. fleire gamle hus ved elva. \u00abDette er eit veldig gammalt hus ved elva.\u00bb Ho gjekk deretter vidare til skulen saman med familien."),
    ("sv", "Dr. Andersson kom till staden tidigt p\u00e5 dagen. Han s\u00e5g t.ex. flera gamla hus vid floden. \u201dDet h\u00e4r \u00e4r ett mycket gammalt hus vid floden.\u201d Hon gick sedan vidare till skolan tillsammans med familjen."),
    ("nl", 'Dr. Jansen kwam vandaag vroeg naar de stad. Hij zag bijv. oude huizen aan de brede rivier. "Dit is een heel oud huis bij de rivier." Daarna ging hij verder naar de school met zijn familie.'),
])
def test_native_language_regressions(lang, text):
    spans = sentence_spans(text, lang)
    assert len(spans) == 4
    assert all(complete_sentence(text[a:b], lang) for a, b in spans)


def test_reject_context_unstable_quote_or_abbreviation_block():
    text = " ".join([
        "Kortgarden, tidligere S\u00f8rstranda er en liten bygd, plassert ved Fannefjordens s\u00f8rlige bredde, i Molde kommune.",
        "Bygden ligger ved foten av fjellet Sk\u00e5la (1128 moh.).",
        *SENTENCES[2:]])
    with pytest.raises(ValueError, match="no_six"):
        fallback_candidate(text, "nb", {"document_hash": "d"}, Renderer())
