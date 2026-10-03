#!/usr/bin/env python3
"""Sanity checks: catalog consistency, every shard parses, vector files match component counts, no file > 45 MB."""
import json, os, sys, struct, glob
d = sys.argv[1]; cat = json.load(open(f"{d}/catalog.json")); errs = []
for r in cat["repos"]:
    comps = json.load(open(f"{d}/{r['components_url']}"))
    if len(comps) != r["component_count"]: errs.append(f"{r['slug']}: count mismatch")
    vp = f"{d}/vectors/{r['slug']}.i8"
    if comps and os.path.exists(vp):
        magic, n, dim = struct.unpack("<4sII", open(vp, "rb").read(12))
        if magic != b"BLV1" or n != len(comps) or os.path.getsize(vp) != 12 + n * dim: errs.append(f"{r['slug']}: vector file mismatch")
    elif comps: errs.append(f"{r['slug']}: missing vectors")
for f in glob.glob(f"{d}/**/*", recursive=True):
    if os.path.isfile(f) and os.path.getsize(f) > 45_000_000 and "/.git/" not in f: errs.append(f"too large: {f}")
for f in cat["search_shards"] + cat["symbol_shards"]: json.load(open(f"{d}/{f}"))
print(json.dumps({"repos": cat["repo_count"], "components": cat["component_count"], "errors": errs[:20]}))
sys.exit(1 if errs else 0)
