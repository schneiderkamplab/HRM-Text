#!/usr/bin/env python3
"""Upload selected export-upload/ folders as Hugging Face dataset repos."""

from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from huggingface_hub import HfApi


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload export-upload/* folders to Hugging Face dataset repos."
    )
    parser.add_argument("--org", default="schneiderkamplab")
    parser.add_argument("--root", default="export-upload")
    parser.add_argument("--log", default="logs/hf_export_upload_20260617.log")
    parser.add_argument(
        "--include-glob",
        default="*",
        help="Only upload direct child folders whose names match this glob.",
    )
    parser.add_argument("--private", action="store_true")
    parser.add_argument(
        "--skip-create",
        action="store_true",
        help="Do not create repos; upload only to already existing dataset repos.",
    )
    parser.add_argument(
        "--token-env",
        default="HF_TOKEN",
        help="Environment variable containing a Hugging Face write token.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    token = os.environ.get(args.token_env)
    if not token:
        raise SystemExit(f"Missing Hugging Face token in ${args.token_env}")

    root = Path(args.root)
    folders = sorted(path for path in root.glob(args.include_glob) if path.is_dir())
    if not folders:
        raise SystemExit(f"No dataset folders found under {root} matching {args.include_glob}")

    log_path = Path(args.log)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    api = HfApi(token=token)

    with log_path.open("a", encoding="utf-8") as log:
        log.write(
            f"[{datetime.now().isoformat()}] Starting upload of "
            f"{len(folders)} datasets to {args.org} from {root}/{args.include_glob}\n"
        )
        for folder in folders:
            repo_id = f"{args.org}/{folder.name}"
            if args.skip_create:
                print(f"SKIP CREATE {repo_id}", flush=True)
                log.write(f"[{datetime.now().isoformat()}] SKIP CREATE {repo_id}\n")
            else:
                print(f"CREATE {repo_id}", flush=True)
                log.write(f"[{datetime.now().isoformat()}] CREATE {repo_id}\n")
                api.create_repo(
                    repo_id=repo_id,
                    repo_type="dataset",
                    exist_ok=True,
                    private=args.private,
                    token=token,
                )

            print(f"UPLOAD {repo_id}", flush=True)
            log.write(f"[{datetime.now().isoformat()}] UPLOAD {repo_id}\n")
            info = api.upload_folder(
                repo_id=repo_id,
                repo_type="dataset",
                folder_path=str(folder),
                commit_message="Upload dataset export package",
                token=token,
                ignore_patterns=["__pycache__/*", "*.pyc"],
            )
            print(f"DONE {repo_id} {info.commit_url}", flush=True)
            log.write(
                f"[{datetime.now().isoformat()}] DONE {repo_id} "
                f"{info.commit_url}\n"
            )


if __name__ == "__main__":
    main()
