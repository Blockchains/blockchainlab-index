# AGENTS.md: blockchainlab-index

Instructions for AI coding agents (Grok, Cursor, Claude Code, Codex, Copilot and others) working **in** this repo or **using it as a building block**. Humans: see [README.md](README.md).

## What this is

Nightly machine-readable code index of the curated Blockchains forks: per-repo catalog, every contract/module/circuit as a component with functions, licence and pinned raw URL, capability taxonomy, int8 embeddings, static search shards and SQLite FTS5. Feeds the composers.

- Kind: index, dataset, cli · stability: `beta` · licence: MIT
- Machine-readable manifest: [`blocks.json`](blocks.json) (schema: [BLOCKS-SCHEMA](https://github.com/Blockchains/.github/blob/main/docs/BLOCKS-SCHEMA.md))
- How it fits with the other Blockchains repos: [Build with Blocks](https://github.com/Blockchains/.github/blob/main/docs/BUILD-WITH-BLOCKS.md)

## Setup

```bash
pip install -r requirements.txt
```

## Build and test

```bash
python3 indexer/validate.py .   # catalog/component/vector consistency, file sizes
python3 indexer/build_index.py work/ingest-out . sources.json   # full rebuild (after ingest)
```

## Structure

| Path | What |
|---|---|
| `catalog.json` | one record per fork |
| `components/` | components per fork |
| `vectors/` | bge-small int8 embeddings |
| `search/` | static search shards |
| `index.sqlite` | FTS5 |
| `taxonomy/capabilities.json` | capability taxonomy |
| `taxonomy/reuse.json` | how to reuse each fork category |
| `sources.json` | fork list |
| `indexer/` | ingest, build, validate, refresh, compose, finalize; reuse.py builds the per-repo `reuse` field |
| `examples/` | worked idea → plan examples |

## Conventions

- Everything is extracted from source files, never from READMEs alone.
- Licences recorded per repo and file; compose.py refuses source-available files and flags GPL/LGPL.
- Generated files are written by the nightly workflow; edit the indexer, not the output.

## Extension points

- New capability: add it to `taxonomy/capabilities.json` (synonyms, match rules, preferred components).
- New fork: add it to fork-sync `forks.json`; `refresh_sources.py` picks it up.

## Do

- Pin the `commit` from the catalog when copying a component.

## Don't

- Hand-edit catalog.json, components/ or index.sqlite.
- Copy files whose `license_class` is not permissive without carrying the licence.
- Commit secrets, keys or `.env` files. Run `gitleaks` before pushing; CI and the org policy reject leaks.

## Using it from another project

- **catalog.json** (file): `https://raw.githubusercontent.com/Blockchains/blockchainlab-index/main/catalog.json`
- **components/<slug>.json** (file): `per-fork component list (path, kind, functions, events, SPDX, pragma, caps, raw URL)`
- **index.sqlite** (file): `FTS5: select slug,path,name from components where components match 'paymaster'`
- **indexer/compose.py** (cli): `BL_INDEX=. python3 indexer/compose.py plan "<idea>" --json plan.json && python3 indexer/compose.py fetch plan.json out/`
- **taxonomy/capabilities.json** (file): `capability ids, synonyms, standards, match rules, licence policy`

See the README section [Use as a building block](README.md#use-as-a-building-block) for a copy-paste example.

## Related blocks

- [Blockchains/blockchainlab-compose](https://github.com/Blockchains/blockchainlab-compose): consumes catalog/components/taxonomy to generate projects
- [Blockchains/fork-sync](https://github.com/Blockchains/fork-sync): keeps the indexed forks current; index runs after the sync
- [Blockchains/awesome-blockchainlab](https://github.com/Blockchains/awesome-blockchainlab): human-readable list of the same forks
- [Blockchains/forge-example-gasless-membership](https://github.com/Blockchains/forge-example-gasless-membership): composed from this index
- [Blockchains/forge-example-usd-savings-vault](https://github.com/Blockchains/forge-example-usd-savings-vault): composed from this index
