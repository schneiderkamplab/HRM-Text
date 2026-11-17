import json
import pytest

from scripts.publish_verified_dfm_transforms import require_verified


def test_publication_requires_both_verified_predecessors(tmp_path):
    with pytest.raises(ValueError, match="DFM2"):
        require_verified(tmp_path)
    for version in (2, 3):
        root = tmp_path / f"dfm{version}"
        root.mkdir()
        (root / "verified.json").write_text(json.dumps({"status": "matched"}))
        if version == 2:
            with pytest.raises(ValueError, match="DFM3"):
                require_verified(tmp_path)
    require_verified(tmp_path)
