from scripts.audit_repaired_dolci_tool_use import original_source_file, stable_seed


def test_stable_seed_is_task_specific_and_deterministic() -> None:
    assert stable_seed("task-a", 7) == stable_seed("task-a", 7)
    assert stable_seed("task-a", 7) != stable_seed("task-b", 7)


def test_original_source_file_removes_only_tokenizer_part_suffix() -> None:
    assert original_source_file("source.part-006.jsonl") == "source.jsonl"
    assert original_source_file("source.jsonl") == "source.jsonl"
    assert original_source_file("source.part-name.jsonl") == "source.part-name.jsonl"
