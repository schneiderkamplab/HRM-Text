import pytest

from dfm12.norwegian_disposition import omission_reason, run


@pytest.mark.parametrize("labels", [["nob"], ["nno"], ["no"], []])
def test_reasoning_never_infers_variant(labels):
    assert omission_reason("reasoning-norwegian", labels) == "unsupported_nb_nn_variant"


@pytest.mark.parametrize("labels", [["nob", "nno"], ["nno", "nob"]])
def test_mixed_samtale_omitted(labels):
    assert omission_reason("nb-samtale-pairs", labels) == "mixed_nb_nn_speaker_orthography"


@pytest.mark.parametrize("labels", [["nob"], ["nno"]])
def test_single_variant_samtale_preserved(labels):
    assert omission_reason("nb-samtale-pairs", labels) is None


@pytest.mark.parametrize("name,labels", [("NorQuAD", ["nob"]), ("FLEURS", ["nno"]),
                                         ("nb-samtale-pairs", ["no"]),
                                         ("magpie-qwen3-bokmaal", ["nno"])])
def test_unexpected_input_fails_closed(name, labels):
    with pytest.raises(ValueError):
        omission_reason(name, labels)


def test_no_overwrite(tmp_path):
    path = tmp_path / "final-variant-disposition.json"
    path.write_text("unchanged")
    with pytest.raises(FileExistsError):
        run(tmp_path)
    assert path.read_text() == "unchanged"
