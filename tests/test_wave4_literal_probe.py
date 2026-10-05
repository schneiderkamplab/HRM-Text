from dfm12.wave4_literal_probe import script_flags, CASES, NOTE


def test_foreign_script_diagnostic_not_rejection():
    row={'language':'hu','messages':[{'role':'assistant','content':'évek протягом'}]}
    assert script_flags(row)[0]['text']=='протягом'
    assert script_flags(row)[0]['diagnostic_only']


def test_code_and_source_preserved():
    row={'language':'hu','provenance':{'source':{'text':'idézet протягом'}},'messages':[{'role':'user','content':'idézet протягом\n```python\nx="протягом"\n```'}]}
    assert script_flags(row)==[]


def test_scope():
    assert len(CASES)==len(set(CASES))==18
    assert 'same required JSON schema' in NOTE
