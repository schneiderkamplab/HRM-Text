"""Print cumulative extension targets; this does not launch GPU work."""
import json
from pathlib import Path

import typer
import yaml

app = typer.Typer()
CONFIG = Path(__file__).with_name("multilingual_extension.yaml")


def targets(config, milestone):
    divisor = config["milestone_divisors"][milestone]
    rows = []
    for language, language_divisor in config["languages"].items():
        for family, settings in config["families"].items():
            count, remainder = divmod(settings["full_priority_rows"], divisor * language_divisor)
            if remainder:
                raise ValueError("Targets must divide exactly")
            rows.append({
                "repo_id": f"schneiderkamplab/dfm12-multilingual-{family}-{language}",
                "language": language,
                "family": family,
                "accepted_target": count,
                "estimated_training_tokens": count * settings["estimated_tokens_per_row"],
                # Milestone deliberately absent: expansion must retain record identities.
                "id_namespace": f"{config['campaign']}/{language}/{family}",
            })
    return rows


@app.command()
def main(milestone: str = "quarter", config: Path = CONFIG):
    specification = yaml.safe_load(config.read_text())
    if milestone not in specification["milestone_divisors"]:
        raise typer.BadParameter("Choose quarter, half or full")
    rows = targets(specification, milestone)
    typer.echo(json.dumps({
        "milestone": milestone,
        "accepted_target": sum(row["accepted_target"] for row in rows),
        "estimated_training_tokens": sum(row["estimated_training_tokens"] for row in rows),
        "datasets": rows,
    }, indent=2))


if __name__ == "__main__":
    app()
