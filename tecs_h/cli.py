"""TECS-H CLI entry point."""

import logging
import sys
import click
import yaml


def _setup_logging(log_dir: str = "logs"):
    import os
    from datetime import date
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f"{date.today().isoformat()}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[logging.FileHandler(log_file, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
    )


@click.group()
def main():
    """TECS-H: Topological Emergence Computation System — Hypothesis"""
    _setup_logging()


@main.command()
@click.option("--entities", required=True, help="Comma-separated Wikidata QIDs")
@click.option("--rounds", default=5, help="Number of collision rounds")
@click.option("--hop", default=2, help="BFS hop depth")
def run(entities: str, rounds: int, hop: int):
    """Run collision loop for a single entity group."""
    from tecs_h.loop.batch import run_batch
    entity_list = [e.strip() for e in entities.split(",")]
    seed_groups = [{"entities": entity_list, "hop": hop}]
    results = run_batch(seed_groups, rounds_per_group=rounds)
    click.echo(f"\n{len(results)} hypotheses generated.")


@main.command()
@click.option("--domain", required=True, help="Domain name from configs/domains.yaml")
@click.option("--rounds-per-group", default=5, help="Rounds per seed group")
@click.option("--config", default="configs/domains.yaml", help="Config file path")
def batch(domain: str, rounds_per_group: int, config: str):
    """Run batch collision loop for a domain."""
    from tecs_h.loop.batch import run_batch
    with open(config) as f:
        domains = yaml.safe_load(f)
    if domain not in domains["domains"]:
        click.echo(f"Domain '{domain}' not found. Available: {list(domains['domains'].keys())}")
        sys.exit(1)
    seed_groups = domains["domains"][domain]["seed_groups"]
    results = run_batch(seed_groups, rounds_per_group=rounds_per_group)
    click.echo(f"\n{len(results)} hypotheses generated.")


@main.command()
@click.option("--date", "target_date", default=None, help="Date (YYYY-MM-DD)")
def results(target_date: str):
    """Show generated hypotheses."""
    import json, os
    from datetime import date as dt_date
    if target_date is None:
        target_date = dt_date.today().isoformat()
    results_dir = os.path.join("results", target_date)
    if not os.path.exists(results_dir):
        click.echo(f"No results for {target_date}")
        return
    files = sorted(f for f in os.listdir(results_dir) if f.endswith(".json"))
    click.echo(f"\n{len(files)} hypotheses found for {target_date}:\n")
    for fname in files:
        with open(os.path.join(results_dir, fname)) as f:
            hyp = json.load(f)
        click.echo(f"  [{hyp['id']}] confidence={hyp['confidence']:.2f}")
        click.echo(f"    {hyp['hypothesis'][:100]}")
        click.echo()
