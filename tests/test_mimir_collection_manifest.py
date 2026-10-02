import contextlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_mimir_collection_manifest import main


def test_membership_and_replacements():
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        main()
    manifest = json.loads(output.getvalue())
    v1, v15 = [set(c['datasets']) for c in manifest['collections']]
    assert len(v1) == 159
    assert not manifest['unresolved_dfm11_prefixes']
    assert 'teknium/OpenHermes-2.5' not in v1 | v15
    assert 'schneiderkamplab/dfm8-openhermes-en' in v1 & v15
    assert 'schneiderkamplab/dfm8-synthetic-native-tool-calling' in v1 - v15
    assert 'schneiderkamplab/dfm11-synthetic-native-tool-calling-repaired' in v15 - v1
    assert 'schneiderkamplab/dfm10-mimir-ifeval-verifier-sft' in v15
    assert 'schneiderkamplab/dfm11-danish-query-templatizer-training' not in v15
