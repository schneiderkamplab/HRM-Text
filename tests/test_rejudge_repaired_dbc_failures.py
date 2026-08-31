from scripts.rejudge_repaired_dbc_failures import RESPONSE_FORMAT


def test_rejudge_schema_uses_only_bounded_fields() -> None:
    schema = RESPONSE_FORMAT["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert schema["properties"]["primary_problem"]["enum"][0] == "none"
