# blockchainlab-index

[![Nightly index](https://github.com/Blockchains/blockchainlab-index/actions/workflows/nightly-index.yml/badge.svg)](https://github.com/Blockchains/blockchainlab-index/actions/workflows/nightly-index.yml)

A machine-readable code index of the curated **Blockchains** forks. It is built from shallow clones of the fork source, not from READMEs. The Blockchain Lab `/forge` composer uses it to turn a plain-language idea into a working project. Rebuilt nightly at 03:41 UTC, after [fork-sync](https://github.com/Blockchains/fork-sync) runs.

## Layout
| Path | What |
|---|---|
| [`catalog.json`](catalog.json) | One record per repo: fork, upstream, pinned commit, licence, stars, VM/standard tags, packages, install commands, component counts, file URLs |
| `components/<slug>.json` | Every production contract, module, circuit, program and Go package. Each entry has its path, kind, functions/events/errors, SPDX licence, pragma, rule-based and semantic capability tags, and a raw URL at the pinned commit |
| `vectors/<slug>.i8` | Per-component embeddings: `BLV1` header, then int8 rows. BAAI/bge-small-en-v1.5, 384 dimensions, CLS pooling, L2-normalised, scale 127 |
| `search/components-NNN.json`, `search/symbols-<c>.json` | Static search shards for browsers (component and symbol lookup) |
| [`index.sqlite`](index.sqlite) | SQLite with FTS5 over components and symbols, for server-side search |
| [`taxonomy/capabilities.json`](taxonomy/capabilities.json) | Capability taxonomy: id, synonyms, standards, VM, match rules, preferred components, licence policy |
| `repos/<slug>/{index,tree,abi}.json` | Raw per-repo ingest output: file tree, parsed sources, ABI files |
| [`sources.json`](sources.json) | The forks to index (generated from the fork waves) |
| [`examples/`](examples/) | Five worked examples (idea → components → repo layout), produced by the real pipeline |
| `indexer/` | `ingest.py`, `build_index.py`, `validate.py`, `refresh_sources.py`, `compose.py` (idea → plan → fetch), `finalize.py` |

## Use
```bash
sqlite3 index.sqlite "select slug,path,name from components where components match 'paymaster' limit 10"
pip install -r requirements.txt
BL_INDEX=. python3 indexer/compose.py plan "gasless NFT membership with a paymaster" --json plan.json
BL_INDEX=. python3 indexer/compose.py fetch plan.json out/
```
Raw files: `https://raw.githubusercontent.com/Blockchains/blockchainlab-index/main/catalog.json`.

**Fully automated composition:** [blockchainlab-compose](https://github.com/Blockchains/blockchainlab-compose) (CLI + `compose.yml` Action) turns an idea into a new Blockchains repo: capabilities → components from this index → pragma/licence checks → generated glue, tests, deploy script, CI → `forge test` → repo → CI result. Composed by it with no hand edits:
- [forge-dao-governance-token](https://github.com/Blockchains/forge-dao-governance-token)
- [forge-usd-priced-membership-nft](https://github.com/Blockchains/forge-usd-priced-membership-nft)

Composed with this index (CI green, deployed to Pages):
- [forge-example-usd-savings-vault](https://github.com/Blockchains/forge-example-usd-savings-vault)
- [forge-example-gasless-membership](https://github.com/Blockchains/forge-example-gasless-membership)

## Licences
The index code is MIT. Indexed code keeps its own licence, recorded per repo and per file. `compose.py` will not copy source-available files (e.g. BUSL-1.1), and it flags GPL/LGPL so composed projects inherit the right terms.
