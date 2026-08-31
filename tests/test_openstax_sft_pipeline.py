from __future__ import annotations

import importlib.util
from pathlib import Path
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / name
    spec = importlib.util.spec_from_file_location(path.stem, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cnxml_text_drops_media_and_keeps_surrounding_text() -> None:
    sources = load_script("openstax_sft_sources.py")
    node = ET.fromstring(
        '<content xmlns="http://cnx.rice.edu/cnxml"><para>Before '
        '<media><image src="restricted.jpg"/><caption>third-party caption</caption></media>'
        " after.</para></content>"
    )
    text = sources.text_from_cnxml(node)
    assert "Before" in text and "after" in text
    assert "restricted" not in text and "third-party" not in text


def test_long_source_copy_detection() -> None:
    model = load_script("openstax_sft_model.py")
    source = " ".join(f"word{index}" for index in range(50))
    copied = "prefix " + " ".join(f"word{index}" for index in range(10, 31))
    paraphrase = "A concise explanation using entirely distinct language and structure."
    assert model.has_long_copy(copied, source)
    assert not model.has_long_copy(paraphrase, source)


def test_policy_selects_expected_tiers() -> None:
    sources = load_script("openstax_sft_sources.py")
    rows = sources.load_manifest(
        ROOT / "config/openstax_mimir_sft.json",
        ROOT / "docs/openstax_cc_by_inventory.csv",
    )
    assert len(rows) == 61
    assert sum(row["tier"] == "primary" for row in rows) == 51
    assert sum(row["tier"] == "supplemental" for row in rows) == 10


def test_training_length_uses_rendered_gemma_conversation() -> None:
    model = load_script("openstax_sft_model.py")

    class Encoded:
        ids = [1, 2, 3, 4]

    class Tokenizer:
        def encode(self, text: str, add_special_tokens: bool):
            assert "question" in text and "answer" in text
            assert add_special_tokens is False
            return Encoded()

    template = model.jinja2.Environment().from_string(
        "{% for message in messages %}{{ message.role }}:{{ message.content }}\n{% endfor %}"
    )
    assert model.training_token_count("question", "answer", Tokenizer(), template) == 4
