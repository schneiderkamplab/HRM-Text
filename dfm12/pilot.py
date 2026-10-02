"""Explicit pilot sign-off before broad teacher usage."""
from .io import load


def require_pilot(root, cfg):
    path = root / "pilot-approval.json"
    if not path.is_file():
        raise ValueError(f"Pilot review required before bulk work: {path}")
    approval = load(path)
    if (approval.get("model") != cfg["model"] or approval.get("approved") is not True
            or set(approval.get("languages", [])) != set(cfg["languages"])
            or not approval.get("evidence")):
        raise ValueError("Pilot approval must cover the chosen model and all nine languages, with review evidence")
