from scripts.prepare_dfm10_dynaword_sft_candidates import literary_chunks, speech_windows


def test_speech_windows_preserve_segment_order() -> None:
    segments = [(2, "tredje segment"), (0, "første segment"), (1, "andet segment")]
    rows = list(speech_windows("recording", segments, min_chars=1, max_chars=1000))
    assert rows == [("recording:window-000", "første segment andet segment tredje segment")]


def test_literary_chunks_are_bounded() -> None:
    text = "Første afsnit.\n\nAndet afsnit.\n\nTredje afsnit."
    rows = list(literary_chunks(text, min_chars=10, max_chars=32))
    assert rows
    assert all(10 <= len(row) <= 32 for row in rows)
