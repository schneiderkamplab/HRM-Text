"""Check the production terminal client's native formatting and tokenization against HF."""
import argparse
import json
from pathlib import Path
import subprocess

__all__ = []


def _main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client", type=Path, required=True)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--reference", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.reference.read_text())
    commands = "".join(json.dumps(case["request"]) + "\n" for case in cases)
    result = subprocess.run([str(args.client), "--model", str(args.model), "--json", "--inspect", "--device", "cpu"],
                            input=commands, capture_output=True, text=True, timeout=120)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".log").write_text(result.stderr)
    replies = [json.loads(line) for line in result.stdout.splitlines()]
    assert result.returncode == 0 and replies.pop(0) == {"event": "ready"}, result.stderr
    assert len(replies) == len(cases)
    checks = []
    for case, reply in zip(cases, replies, strict=True):
        match = {key: reply.get(key) == case[key] for key in ["tokens", "text", "decoded"] if key in case}
        checks.append({"id": case["id"], "pass": all(match.values()), "checks": match,
                       **({"actual": reply, "expected": case} if not all(match.values()) else {})})
    report = {"pass": all(check["pass"] for check in checks), "cases": checks}
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Tokenizer/template: {sum(check['pass'] for check in checks)}/{len(checks)} cases")
    if not report["pass"]:
        raise SystemExit("Tokenizer/template parity failed")


if __name__ == "__main__":
    _main()
