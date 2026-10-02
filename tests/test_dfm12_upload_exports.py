import pytest

from dfm12 import upload_exports
from dfm12.io import write_json


def fixture(root):
    write_json(root / "manifest.json", {"packages": [{"name": "dfm12-example", "rows": 1}]})
    write_json(root / "dfm12-example/metadata/manifest.json", {"upload_ready": True})


def test_existing_remote_not_overwritten(tmp_path, monkeypatch):
    fixture(tmp_path)
    class API:
        def whoami(self):
            return {}

        def repo_info(self, *args, **kwargs):
            return object()
    monkeypatch.setattr(upload_exports, "HfApi", API)
    with pytest.raises(ValueError, match="existing unowned"):
        upload_exports.publish(tmp_path, "example")


def test_unsafe_package_name_rejected(tmp_path, monkeypatch):
    fixture(tmp_path)
    write_json(tmp_path / "manifest.json", {"packages": [{"name": "../metadata", "rows": 1}]})
    class API:
        def whoami(self):
            return {}
    monkeypatch.setattr(upload_exports, "HfApi", API)
    with pytest.raises(ValueError, match="Unsafe package"):
        upload_exports.publish(tmp_path, "example")


def test_upload_allowlist_excludes_root_snapshots(tmp_path, monkeypatch):
    import httpx
    from types import SimpleNamespace
    from dfm12.io import load
    from huggingface_hub.errors import RepositoryNotFoundError
    fixture(tmp_path)
    folder = tmp_path / "dfm12-example"
    write_json(folder / "metadata/manifest.json", {"upload_ready": True,
               "data_files": [{"file": "data/train.jsonl"}], "metadata_files": []})
    write_json(folder / "data/train.jsonl", {"messages": []})
    (folder / "validate_dataset.py").write_text("# validator\n")
    (folder / "README.md").write_text("Accepted only\n")
    write_json(tmp_path / "metadata/private-snapshot.json", {"rejected": "never upload"})
    uploaded = []
    class API:
        def whoami(self):
            return {}
        def repo_info(self, *args, **kwargs):
            raise RepositoryNotFoundError("not yet published", response=httpx.Response(
                404, request=httpx.Request("GET", "https://example.org/dataset")))
        def create_repo(self, *args, **kwargs):
            pass
        def create_commit(self, *args, operations, **kwargs):
            uploaded.extend(op.path_in_repo for op in operations)
            return SimpleNamespace(oid="commit", commit_url="https://example.org/commit")
        def list_repo_files(self, *args, **kwargs):
            return uploaded + [".gitattributes"]
    monkeypatch.setattr(upload_exports, "HfApi", API)
    monkeypatch.setattr(upload_exports, "validate", lambda path: {"rows": 1})
    upload_exports.publish(tmp_path, "example")
    assert set(uploaded) == {"data/train.jsonl", "metadata/manifest.json", "README.md", "validate_dataset.py"}
    assert load(tmp_path / "metadata/upload-receipts.json")["example/dfm12-example"]["status"] == "verified"
