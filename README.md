# Signal Forge

A local-first Python 3.11+ MVP for investment intelligence on Polish and EU biogas and biomethane. It uses only the standard library and SQLite. No data leaves the machine except when a user explicitly runs `collect` or `ingest-url`.

## WSL, first launch

From any WSL terminal, run:

```bash
/home/aiall/projects/signal-forge/run_signal_forge.sh
```

The launcher creates a local `.venv`, installs Signal Forge, initializes the SQLite database, imports the GGP source registry only for a fresh database, and opens the cockpit at `http://127.0.0.1:8765`. Press `Ctrl+C` in that terminal to stop the local app.

The dashboard is local-only: it does not contact the network until you explicitly click **Run RSS / Atom scan** (or invoke the existing CLI collection/URL-ingest commands). Add only RSS or Atom source URLs for scanning.

## Manual setup

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e .
python -m signal_forge init-db
python -m signal_forge import-sources config/sources.seed.yaml
python -m signal_forge serve --open
```

The source file supports JSON and a compact YAML subset. Seed sources are primarily web pages, so their deliberately unsupported scan methods are reported cleanly until a collector is added. RSS/Atom sources use `scan_method: rss`, `atom`, or `feed`.

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
