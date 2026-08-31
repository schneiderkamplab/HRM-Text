from scripts.repair_dst_table_prompts import clean_target, extract_table


def test_extract_table_uses_authoritative_length() -> None:
    table = "| A | B |\n| --- | --- |\n| x | 1 |"
    prompt = f"Intro\n\n{table}. trailing request"
    assert extract_table(prompt, len(table)) == table


def test_clean_target_removes_publication_footer() -> None:
    target = (
        "Første faktuelle afsnit.\n\nAndet faktuelle afsnit.\n\n"
        "Emnestatistik  april 2026\n\n22. april 2026 - Nr. 97\n\n"
        "Hent som PDF\n\nKontakt\n\nNavn"
    )
    assert clean_target(target) == "Første faktuelle afsnit.\n\nAndet faktuelle afsnit."


def test_clean_target_stops_at_ui_without_date_block() -> None:
    target = "En fuldstændig artikel.\n\nKontakt\n\nEn person"
    assert clean_target(target) == "En fuldstændig artikel."
