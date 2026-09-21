"""Transfer the completed XL endpoint and local run archive; never launch training."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SOURCE = "/work/dfm/HRM-Text"
REL = "checkpoints/dfm10/XL-from-dfm9-epoch8"
RUN = "dfm8-xl-from-dfm6-dfm7-epoch5-clean-full"
HOST = "ucloud@ssh.cloud.sdu.dk"
SSH = ["ssh", "-p", "6977", "-o", "BatchMode=yes", "-o", "ServerAliveInterval=30"]


def main():
    os.chdir(ROOT)
    receipt = ROOT / "logs/transfer_xl_dfm11"
    receipt.mkdir(parents=True, exist_ok=True)
    target = ROOT / REL
    target.mkdir(parents=True, exist_ok=True)
    names = ["fsdp2_step_2482084", "checkpoint_state_step_2482084.json",
             "all_config.yaml", "train_metadata.yaml", "hrm_nocarry_bp_warmup.py"]
    remote_code = f"""
import hashlib, json
from pathlib import Path
root = Path({(SOURCE + '/' + REL)!r})
files = []
for name in {names!r}:
    p = root / name
    for f in sorted(p.rglob('*')) if p.is_dir() else [p]:
        if f.is_file():
            with f.open('rb') as h:
                digest = hashlib.file_digest(h, 'sha256').hexdigest()
            files.append(dict(path=str(f.relative_to(root)), bytes=f.stat().st_size, sha256=digest))
print(json.dumps(files))
"""
    print("Hashing source checkpoint", flush=True)
    manifest = json.loads(subprocess.check_output(
        SSH + [HOST, "python3 -c " + shlex.quote(remote_code)], text=True))
    (receipt / "source_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    common = ["rsync", "-a", "--partial", "--info=progress2", "--bwlimit=204800",
              "-e", shlex.join(SSH)]
    subprocess.run(common + [f"{HOST}:{SOURCE}/{REL}/{name}" for name in names]
                   + [str(target) + "/"], check=True)
    for item in manifest:
        path = target / item["path"]
        assert path.stat().st_size == item["bytes"], path
        with path.open("rb") as handle:
            assert hashlib.file_digest(handle, "sha256").hexdigest() == item["sha256"], path
    print("Checkpoint SHA256 verified; copying run archives", flush=True)
    archive = receipt / "wandb"
    archive.mkdir(exist_ok=True)
    subprocess.run(common + [f"--include=run-*-{RUN}/", "--include=run-*.wandb",
                             "--include=files/", "--include=files/***", "--exclude=*",
                             f"{HOST}:{SOURCE}/wandb/", str(archive) + "/"], check=True)
    metadata = json.loads((target / "checkpoint_state_step_2482084.json").read_text())
    assert metadata["step"] == 2482084 and metadata["epoch"] == 9
    assert metadata["carry_policy"] == "none"
    alias = target / "fsdp2_epoch_9"
    if not alias.exists():
        alias.symlink_to("fsdp2_step_2482084", target_is_directory=True)
    assert alias.resolve() == (target / "fsdp2_step_2482084").resolve()
    metadata.update(tag="epoch_9", batch_in_epoch=0, global_row_cursor_in_epoch=0,
                    global_row_start_in_epoch=0)
    (target / "checkpoint_state_epoch_9.json").write_text(json.dumps(metadata, indent=2) + "\n")
    result = dict(checkpoint=str(target), step=2482084, resume_tag="epoch_9",
                  next_epoch=10, dataset_index="epoch_9", wandb_run_id=RUN,
                  checkpoint_sha256_verified=True,
                  archive_files=len(list(archive.glob("run-*/run-*.wandb"))))
    (receipt / "complete.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2), flush=True)


if __name__ == "__main__":
    main()
