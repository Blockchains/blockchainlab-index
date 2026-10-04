#!/usr/bin/env python3
"""Build blockchainlab-index from ingest output: components, capability tags, embeddings, search shards, SQLite FTS.
Usage: build_index.py <ingest-out> <index-repo-dir> <repolist.json> [--no-embed]"""
import json, os, re, sys, glob, sqlite3, struct, hashlib, datetime, gzip, shutil
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reuse import reuse  # noqa: E402  per-repo reuse hints (taxonomy/reuse.json has category notes)
src, dst, rl = sys.argv[1], sys.argv[2], sys.argv[3]
EMBED = "--no-embed" not in sys.argv
tax = json.load(open(f"{dst}/taxonomy/capabilities.json"))
repolist = {r["slug"]: r for r in json.load(open(rl))}
caps = tax["capabilities"]
for c in caps:
    m = c["match"]; c["_name"] = re.compile(m["name_regex"]); c["_path"] = re.compile(m["path_regex"]) if m["path_regex"] else None
PERM = set(tax["license_policy"]["permissive"])
def lic_class(l):
    if not l: return "unknown"
    u = l.upper()
    if "BUSL" in u or "LICENSEREF" in u or "UNLICENSED" in u: return "source-available"
    if "AGPL" in u or re.search(r"(^|[^L])GPL", u): return "strong-copyleft"
    if "LGPL" in u or "MPL" in u: return "weak-copyleft"
    if any(p.upper() in u for p in ("MIT", "APACHE", "BSD", "ISC", "UNLICENSE", "0BSD", "CC0")): return "permissive"
    return "unknown"
def rule_caps(comp):
    out = []
    fn = set(f.split("(")[0] for f in comp.get("functions", []))
    bases = set(comp.get("bases", [])); name = comp.get("name") or ""; path = comp.get("path") or ""
    for c in caps:
        m = c["match"]; score = 0.0; via = []
        if m["base_any"] and bases & set(m["base_any"]) or name in m["base_any"]: score += 0.6; via.append("base")
        hits = len(fn & set(m["function_any"]))
        if m["function_any"] and hits >= min(3, len(m["function_any"])): score += 0.3 + 0.1 * min(hits, 3); via.append("functions")
        if c["_path"] and c["_path"].search(path): score += 0.25; via.append("path")
        if name and c["_name"].pattern != "(?i)." and c["_name"].search(name): score += 0.2; via.append("name")
        if c["id"] == "move-module" and comp.get("lang") == "Move": score += 0.8; via.append("lang")
        if c["id"] == "solana-program" and comp.get("kind") == "anchor program": score += 0.8; via.append("kind")
        if c["id"] == "substrate-pallet" and comp.get("kind") == "ink contract": score += 0.8; via.append("kind")
        if c["id"] == "zk-proof" and comp.get("lang") in ("Circom", "Noir"): score += 0.8; via.append("lang")
        if c["id"] == "cosmos-module" and comp.get("kind") == "cosmwasm": score += 0.8; via.append("kind")
        if score >= 0.45: out.append({"id": c["id"], "score": round(min(score, 1.0), 3), "via": "+".join(via)})
    return sorted(out, key=lambda x: -x["score"])[:4]
comps_all, repos_out = [], []
os.makedirs(f"{dst}/repos", exist_ok=True); os.makedirs(f"{dst}/components", exist_ok=True); os.makedirs(f"{dst}/search", exist_ok=True); os.makedirs(f"{dst}/vectors", exist_ok=True)
for ipath in sorted(glob.glob(f"{src}/repos/*/index.json")):
    slug = ipath.split("/")[-2]; idx = json.load(open(ipath)); meta = repolist.get(slug, {})
    lic = meta.get("license_note") or idx.get("license_spdx_github") or next((l["detected"] for l in idx["licenses"] if l.get("detected")), None)
    comps = []
    for c in idx["contracts"]:
        if c.get("test"): continue
        if c.get("lang") == "Solidity" and c["kind"] == "interface" and not c.get("functions"): continue
        cid = f"{slug}:{c['path']}:{c.get('name','')}"
        comps.append({"id": cid, "slug": slug, "type": "contract", "kind": c["kind"], "lang": c.get("lang"), "name": c.get("name") or os.path.basename(c["path"]),
                      "path": c["path"], "line": c.get("line"), "bases": c.get("bases", []), "functions": c.get("functions", [])[:80], "events": c.get("events", [])[:40],
                      "errors": c.get("errors", [])[:20], "spdx": c.get("spdx") or lic, "pragma": c.get("pragma")})
    for p in idx["packages"]:
        if p.get("private") or re.search(r"(^|/)(tests?|examples?|bench|fixtures?)/", p["path"]): continue
        comps.append({"id": f"{slug}:{p['path']}:{p['name']}", "slug": slug, "type": "package", "kind": f"{p['ecosystem']} package", "lang": {"npm": "TypeScript", "cargo": "Rust", "go": "Go", "pypi": "Python", "move": "Move", "scarb": "Cairo", "nargo": "Noir"}.get(p["ecosystem"]),
                      "name": p["name"], "path": p["path"], "version": p.get("version"), "description": p.get("description", ""), "exports": p.get("exports", [])[:40], "bin": p.get("bin", []),
                      "dependencies": p.get("dependencies", [])[:40], "spdx": p.get("license") or lic, "functions": []})
    for g in sorted(idx.get("go_packages", []), key=lambda x: -len(x["exported_funcs"]))[:150]:
        comps.append({"id": f"{slug}:{g['dir']}:go", "slug": slug, "type": "module", "kind": "go package", "lang": "Go", "name": g.get("package") or g["dir"], "path": g["dir"],
                      "functions": g["exported_funcs"][:60], "types": g["exported_types"][:40], "spdx": lic})
    for c in comps:
        c["caps"] = rule_caps(c); c["license_class"] = lic_class(c.get("spdx")); c["vm"] = idx["tags"]
        c["raw_url"] = f"{idx['raw_base']}{c['path']}" if c["type"] != "module" else None
        c["github_url"] = f"https://github.com/{idx['fork']}/blob/{idx['branch']}/{c['path']}" if c["type"] != "module" else f"https://github.com/{idx['fork']}/tree/{idx['branch']}/{c['path']}"
    comps = comps[:4000]
    json.dump(comps, open(f"{dst}/components/{slug}.json", "w"), separators=(",", ":"))
    # copy per-repo index + tree + abi (gz tree if large)
    od = f"{dst}/repos/{slug}"; os.makedirs(od, exist_ok=True)
    shutil.copy(ipath, f"{od}/index.json")
    for fn in ("tree.json", "abi.json"):
        p = f"{src}/repos/{slug}/{fn}"
        if os.path.exists(p):
            if os.path.getsize(p) > 20_000_000:
                with open(p, "rb") as fi, gzip.open(f"{od}/{fn}.gz", "wb") as fo: shutil.copyfileobj(fi, fo)
            else: shutil.copy(p, f"{od}/{fn}")
    capc = {}
    for c in comps:
        for k in c["caps"]: capc[k["id"]] = capc.get(k["id"], 0) + 1
    repos_out.append({"slug": slug, "name": idx["fork"].split("/")[1], "fork": idx["fork"], "fork_url": f"https://github.com/{idx['fork']}", "upstream": idx["upstream"], "upstream_url": f"https://github.com/{idx['upstream']}",
                      "branch": idx["branch"], "commit": idx["commit"], "indexed_at": idx["indexed_at"], "category": meta.get("category") or idx.get("category"), "license": lic, "license_class": lic_class(lic),
                      "license_spdx_github": idx.get("license_spdx_github"), "stars": meta.get("stars"), "description": meta.get("description") or idx.get("description"), "readme_summary": idx["readme_summary"],
                      "install_commands": idx["install_commands"][:12], "languages_bytes": dict(list(idx["languages_bytes"].items())[:8]), "file_count": idx["file_count"], "tags": idx["tags"],
                      "component_count": len(comps), "capabilities": dict(sorted(capc.items(), key=lambda x: -x[1])), "packages": [p["name"] for p in idx["packages"] if not p.get("private")][:30],
                      "raw_base": idx["raw_base"], "index_url": f"repos/{slug}/index.json", "components_url": f"components/{slug}.json", "tree_url": f"repos/{slug}/tree.json", "wave": meta.get("wave"), "tier": meta.get("tier")})
    repos_out[-1]["reuse"] = reuse(repos_out[-1], idx["packages"])
    comps_all.extend(comps)
# embeddings
if EMBED:
    sys.path.insert(0, "")
    from fastembed import TextEmbedding
    import numpy as np
    model = TextEmbedding("BAAI/bge-small-en-v1.5")
    rdesc = {r["slug"]: (r["description"] or "")[:160] for r in repos_out}
    def text(c):
        return f"{c['name']} ({c['kind']}, {c.get('lang') or ''}) from {c['slug']}: {rdesc.get(c['slug'],'')}. " + " ".join(c.get("bases", [])[:8]) + " " + " ".join(f.split('(')[0] for f in c.get("functions", [])[:30]) + " " + c.get("description", "") + " " + c["path"]
    capt = [f"{c['label']}: {c['description']} " + ", ".join(c["synonyms"]) for c in caps]
    capv = np.array(list(model.embed(capt)), dtype=np.float32)
    capv /= np.linalg.norm(capv, axis=1, keepdims=True)
    json.dump({"model": "BAAI/bge-small-en-v1.5", "dim": 384, "pooling": "cls", "normalize": True, "ids": [c["id"] for c in caps], "vectors": [[round(float(x), 5) for x in v] for v in capv]}, open(f"{dst}/taxonomy/capabilities.vectors.json", "w"), separators=(",", ":"))
    by_slug = {}
    for c in comps_all: by_slug.setdefault(c["slug"], []).append(c)
    for slug, cs in by_slug.items():
        V = np.array(list(model.embed([text(c) for c in cs], batch_size=128)), dtype=np.float32)
        V /= np.linalg.norm(V, axis=1, keepdims=True)
        sims = V @ capv.T
        for c, srow in zip(cs, sims):
            mu, sd = float(srow.mean()), float(srow.std()) or 1.0
            top = np.argsort(-srow)[:3]
            c["caps_semantic"] = [{"id": caps[i]["id"], "score": round(float(srow[i]), 3), "z": round((float(srow[i]) - mu) / sd, 2)} for i in top if (srow[i] - mu) / sd >= 2.0]
        q = np.clip(np.round(V * 127), -127, 127).astype(np.int8)
        with open(f"{dst}/vectors/{slug}.i8", "wb") as f:
            f.write(struct.pack("<4sII", b"BLV1", len(cs), 384)); f.write(q.tobytes())
        json.dump(cs, open(f"{dst}/components/{slug}.json", "w"), separators=(",", ":"))
# search shards (compact)
lite = [[c["id"], c["slug"], c["name"], c["kind"], c.get("lang"), [k["id"] for k in c["caps"]] + [k["id"] for k in c.get("caps_semantic", []) if k["id"] not in [x["id"] for x in c["caps"]]], c["license_class"], c["path"]] for c in comps_all]
for f in glob.glob(f"{dst}/search/components-*.json"): os.remove(f)
chunk, n, size = [], 0, 0
for row in lite:
    chunk.append(row); size += len(json.dumps(row))
    if size > 4_000_000:
        json.dump({"fields": ["id", "slug", "name", "kind", "lang", "caps", "license_class", "path"], "rows": chunk}, open(f"{dst}/search/components-{n:03d}.json", "w"), separators=(",", ":")); n += 1; chunk, size = [], 0
if chunk: json.dump({"fields": ["id", "slug", "name", "kind", "lang", "caps", "license_class", "path"], "rows": chunk}, open(f"{dst}/search/components-{n:03d}.json", "w"), separators=(",", ":")); n += 1
# symbol shards by first char
sym = {}
for c in comps_all:
    for s in [c["name"]] + [f.split("(")[0] for f in c.get("functions", [])] + [e.split("(")[0] for e in c.get("events", [])]:
        if not s: continue
        k = s[0].lower(); k = k if k.isalnum() else "_"
        sym.setdefault(k, []).append([s, c["id"]])
for f in glob.glob(f"{dst}/search/symbols-*.json"): os.remove(f)
for k, v in sym.items():
    json.dump(v, open(f"{dst}/search/symbols-{k}.json", "w"), separators=(",", ":"))
# sqlite FTS
dbp = f"{dst}/index.sqlite"
if os.path.exists(dbp): os.remove(dbp)
db = sqlite3.connect(dbp)
db.execute("CREATE TABLE repos(slug TEXT PRIMARY KEY, json TEXT)")
db.execute("CREATE VIRTUAL TABLE components USING fts5(id UNINDEXED, slug, name, kind, lang, path, caps, functions, events, description, license_class UNINDEXED, tokenize='unicode61')")
db.executemany("INSERT INTO repos VALUES(?,?)", [(r["slug"], json.dumps(r)) for r in repos_out])
db.executemany("INSERT INTO components VALUES(?,?,?,?,?,?,?,?,?,?,?)", [(c["id"], c["slug"], c["name"], c["kind"], c.get("lang") or "", c["path"], " ".join(k["id"] for k in c["caps"] + c.get("caps_semantic", [])), " ".join(c.get("functions", [])), " ".join(c.get("events", [])), c.get("description", ""), c["license_class"]) for c in comps_all])
db.commit(); db.execute("VACUUM"); db.close()
if os.path.exists(f"{src}/ingest-status.json"): shutil.copy(f"{src}/ingest-status.json", f"{dst}/ingest-status.json")
cat = {"generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "owner": "Blockchains", "repo_count": len(repos_out), "component_count": len(comps_all),
       "embedding": {"model": "BAAI/bge-small-en-v1.5", "dim": 384, "format": "vectors/<slug>.i8: header '<4sII' (magic BLV1, count, dim) + int8[count*dim], row order = components/<slug>.json, value/127 ~ L2-normalised float", "query_pooling": "cls", "normalize": True},
       "search_shards": [f"search/components-{i:03d}.json" for i in range(n)], "symbol_shards": sorted(f"search/symbols-{k}.json" for k in sym), "sqlite": "index.sqlite", "taxonomy": "taxonomy/capabilities.json", "reuse_notes": "taxonomy/reuse.json", "repos": repos_out}
json.dump(cat, open(f"{dst}/catalog.json", "w"), indent=1)
print(json.dumps({"repos": len(repos_out), "components": len(comps_all), "sqlite_mb": round(os.path.getsize(dbp) / 1e6, 1)}))
