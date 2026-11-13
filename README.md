# Signal Forge

A local-first Python 3.11+ MVP for investment intelligence on Polish and EU biogas and biomethane. It uses only the standard library and SQLite. The machine fetches a feed only when the collector runs, or when you capture one URL.

## WSL, first launch

From any WSL terminal, run:

```bash
/home/aiall/projects/signal-forge/run_signal_forge.sh
```

The launcher creates a local `.venv`, installs Signal Forge, and opens the cockpit at `http://127.0.0.1:8765`. Press `Ctrl+C` in that terminal to stop the cockpit and the collector.

The source list is `config/sources.yaml`. Edit that file in any editor. The collector reads it every 15 minutes and writes findings into `signal-forge.db`. The cockpit shows the vault. It does not own the list. Adding a feed in the cockpit writes the same file.

Only sources with `scan_method: rss`, `atom`, or `feed` are fetched. The seeded entries are web pages, so they stay in the list and are skipped until you give them a feed URL.

## Manual setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python -m signal_forge init-db
python -m signal_forge sync-sources config/sources.yaml
python -m signal_forge watch --sources config/sources.yaml --interval 900
python -m signal_forge serve --sources config/sources.yaml --open
```

The source file supports JSON and a compact YAML subset. `config/sources.seed.yaml` is the starting list. The working list is `config/sources.yaml`.

## Commands

```bash
python -m signal_forge --db signal-forge.db add-source https://example.org/feed.xml --name "Example feed" --authority primary --topics policy-regulation,market-economics --scan-method rss
python -m signal_forge --db signal-forge.db collect --source-id 1
python -m signal_forge --db signal-forge.db collect --all
python -m signal_forge --db signal-forge.db ingest-url https://example.org/article --topics projects-transactions
python -m signal_forge --db signal-forge.db score
python -m signal_forge --db signal-forge.db brief --date 2026-11-12 --format md
python -m signal_forge --db signal-forge.db brief --format json
python -m signal_forge --db signal-forge.db search biomethane --format md
```

Items are deduplicated by canonical URL (fragments and common tracking parameters removed) or normalized content hash. The deterministic analyst produces a transparent score, priority, confidence, impact, why-it-matters and recommendation. `signal_forge.scoring.Analyst` is the stable interface for a future pluggable LLM analyst; no LLM is required by this MVP.

## Development

```bash
python -m unittest discover -s tests -v
```
