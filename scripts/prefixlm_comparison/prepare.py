"""Recreate isolated, pinned llama.cpp variants without modifying the submodule."""

import argparse
import hashlib
import json
import platform
from pathlib import Path
import subprocess

__all__ = []

_BASE = "c9a5eeeb34ab8f794ea7510ca52d25da13728a5b"
_ORIGINAL = "66c7c5ed26b8251a45534ecb9d173275d7ee65a1"
_ROOT = Path(__file__).resolve().parents[2]
_HERE = Path(__file__).resolve().parent


def _git(repo, *args, **kwargs):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, **kwargs)


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, default=_ROOT / "logs/prefixlm-comparison")
    parser.add_argument("--variants", nargs="+", choices=["baseline", "existing", "replacement", "proposal-original"],
                        default=["baseline", "existing", "replacement", "proposal-original"])
    parser.add_argument("--build", action="store_true")
    parser.add_argument("--jobs", type=int, default=8)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    source = _ROOT / "llama.cpp"
    probe = subprocess.run(["git", "-C", str(source), "cat-file", "-e", _ORIGINAL], capture_output=True)
    if probe.returncode:
        _git(source, "fetch", "https://github.com/noctrex/llama.cpp.git", _ORIGINAL)
    harness = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in _HERE.iterdir()
               if p.is_file() and p.suffix in {".py", ".cpp", ".txt", ".lock"}}
    manifest = {"base_revision": _BASE, "original_proposal_revision": _ORIGINAL,
                "host": platform.platform(), "machine": platform.machine(), "harness_sha256": harness,
                "original_proposal_url": "https://github.com/noctrex/llama.cpp/pull/1", "variants": {}}
    for variant in args.variants:
        revision = _ORIGINAL if variant == "proposal-original" else _BASE
        worktree = workspace / "worktrees" / variant
        if not worktree.exists():
            _git(source, "worktree", "add", "--detach", str(worktree), revision)
        actual = _git(worktree, "rev-parse", "HEAD", capture_output=True, text=True).stdout.strip()
        if actual != revision:
            raise RuntimeError(f"Refusing worktree with unexpected HEAD: {worktree}")
        patch = _HERE / "patches" / f"{variant}.patch"
        if patch.exists():
            reverse = subprocess.run(["git", "-C", str(worktree), "apply", "--reverse", "--check", str(patch)],
                                     capture_output=True)
            if reverse.returncode:
                _git(worktree, "apply", "--check", str(patch))
                _git(worktree, "apply", str(patch))
        diff = _git(worktree, "diff", "HEAD", capture_output=True).stdout
        expected = patch.read_bytes() if patch.exists() else b""
        if diff != expected:
            raise RuntimeError(f"Unexpected tracked changes in {worktree}; refusing to benchmark")
        untracked = _git(worktree, "ls-files", "--others", "--exclude-standard", capture_output=True).stdout
        if untracked:
            raise RuntimeError(f"Unexpected untracked files in {worktree}")
        info = {"revision": revision, "diff_sha256": hashlib.sha256(diff).hexdigest(), "path": str(worktree)}
        if args.build:
            build = workspace / "build" / variant
            commands = [
                ["cmake", "-S", str(_HERE), "-B", str(build), f"-DLLAMA_SOURCE={worktree}",
                 "-DCMAKE_BUILD_TYPE=Release", "-DGGML_METAL=ON", "-DGGML_BLAS=OFF"],
                ["cmake", "--build", str(build), "--target", "prefixlm-runner", "-j", str(args.jobs)],
            ]
            for label, command in zip(["configure", "build"], commands, strict=True):
                with (workspace / f"{label}-{variant}.log").open("w") as log:
                    subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
            info["build_commands"] = commands
            binary = build / "bin/prefixlm-runner"
            info["binary_sha256"] = hashlib.sha256(binary.read_bytes()).hexdigest()
        manifest["variants"][variant] = info
    (workspace / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(workspace / "manifest.json")


if __name__ == "__main__":
    _main()
