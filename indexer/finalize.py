#!/usr/bin/env python3
"""Write README (component map), LICENSE, CI + Pages workflows for a composed repo. Usage: finalize.py <repo-dir> <repo-name> <title> <summary-md-file>"""
import json, sys, os, urllib.request
d, name, title, summ = sys.argv[1:5]
m = json.load(open(f"{d}/component-map.json")); lic = m["license"]["project_license"]
rows = "\n".join(f"| {s['capability']} ({s.get('role','primary')}) | [`{s['name']}`](https://github.com/{s['fork']}/blob/{next((f['commit'] for f in m['copied_files'] if f['slug']==s['slug']), s['commit'])}/{s['path']}) | [{s['fork']}](https://github.com/{s['fork']}) (upstream [{s['upstream']}](https://github.com/{s['upstream']})) | {s['license']} |" for s in m["selected"])
srcs = {}
for f in m["copied_files"]: srcs.setdefault((f["fork"], f["commit"], f.get("tag"), f["upstream"]), []).append(f["path"])
src_rows = "\n".join(f"| [{k[0]}](https://github.com/{k[0]}/tree/{k[1]}) | {k[2] or k[1][:10]} | {len(v)} |" for k, v in srcs.items())
caps = ", ".join(f"`{c['id']}`" for c in m["capabilities"])
badge = f"[![CI](https://github.com/Blockchains/{name}/actions/workflows/ci.yml/badge.svg)](https://github.com/Blockchains/{name}/actions/workflows/ci.yml) [![Pages](https://github.com/Blockchains/{name}/actions/workflows/pages.yml/badge.svg)](https://blockchains.github.io/{name}/) [![Open in Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/Blockchains/{name}?quickstart=1)"
readme = f"""# {title}

{badge}

> **Idea:** {m['idea']}

This repository was composed automatically by **[Blockchain Lab Forge](https://blockchainlab.com/forge)**. Forge parsed the idea into capabilities ({caps}), retrieved matching components from the [Blockchains fork index](https://github.com/Blockchains/blockchainlab-index), pinned them to release tags, copied their exact source files (with full import closure) from the Blockchains forks, and added glue code, tests, a deploy script and a web front end.

{open(summ).read()}

## Component map
| Capability | Component | From | Licence |
|---|---|---|---|
{rows}

Copied sources (unmodified, under `lib/<project>/`, listed file by file in [NOTICE](NOTICE)):

| Fork | Pinned | Files |
|---|---|---|
{src_rows}

Machine-readable: [`component-map.json`](component-map.json) · plan: [`plan.json`](plan.json)

## Licence
**{lic}**. {m['license'].get('warning') or 'All copied components are permissively licensed.'} Every copied file keeps its original SPDX header. Attribution is in [NOTICE](NOTICE).

Not audited. Review the code yourself before you put real value on mainnet.
"""
open(f"{d}/README.md", "w").write(readme)
spdx = "gpl-3.0" if lic.startswith("GPL") else ("agpl-3.0" if lic.startswith("AGPL") else "mit")
import subprocess
try:
    txt = subprocess.run(["gh", "api", f"licenses/{spdx}", "--jq", ".body"], capture_output=True, text=True, check=True).stdout
except Exception:
    txt = json.loads(urllib.request.urlopen(f"https://api.github.com/licenses/{spdx}").read())["body"]
if spdx == "mit": txt = txt.replace("[year]", "2026").replace("[fullname]", "Blockchain Lab")
open(f"{d}/LICENSE", "w").write(txt)
os.makedirs(f"{d}/.github/workflows", exist_ok=True)
open(f"{d}/.github/workflows/ci.yml", "w").write("""name: CI
on:
  push:
    branches: [main]
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
jobs:
  contracts:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: foundry-rs/foundry-toolchain@v1
      - run: forge build --sizes
      - run: forge test -vv
  web:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: foundry-rs/foundry-toolchain@v1
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: forge build
      - working-directory: web
        run: npm ci && npm test && npm run build
""")
open(f"{d}/.github/workflows/pages.yml", "w").write("""name: Pages
on:
  push:
    branches: [main]
  workflow_dispatch:
permissions:
  contents: read
  pages: write
  id-token: write
concurrency:
  group: pages
  cancel-in-progress: true
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          submodules: recursive
      - uses: foundry-rs/foundry-toolchain@v1
      - uses: actions/setup-node@v4
        with:
          node-version: 20
      - run: forge build
      - working-directory: web
        run: npm ci && npm run build
      - uses: actions/upload-pages-artifact@v3
        with:
          path: web/dist
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.d.outputs.page_url }}
    steps:
      - id: d
        uses: actions/deploy-pages@v4
""")
open(f"{d}/.gitignore", "w").write("out/\ncache/\nbroadcast/*/31337/\nnode_modules/\nweb/dist/\n.env\n")
print("finalized", name, lic)
