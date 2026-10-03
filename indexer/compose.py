#!/usr/bin/env python3
"""Blockchain Lab idea -> project composer (reference implementation of the /forge pipeline).
  plan:  compose.py plan "<idea>" [--vm EVM] [--json out.json]
  fetch: compose.py fetch <plan.json> <outdir>   (copies selected files + import closure from Blockchains forks, writes NOTICE/LICENSE/component-map)
Index: /workspace/forge/repos/blockchainlab-index (catalog.json, components/*.json, taxonomy/*)."""
import json, re, sys, os, math, urllib.request, collections, datetime
IDX = os.environ.get("BL_INDEX", "/workspace/forge/repos/blockchainlab-index")
tax = json.load(open(f"{IDX}/taxonomy/capabilities.json")); caps = {c["id"]: c for c in tax["capabilities"]}
cat = json.load(open(f"{IDX}/catalog.json")); repos = {r["slug"]: r for r in cat["repos"]}
REMAP = {"@openzeppelin/contracts/": ("openzeppelin-contracts", "contracts/"), "@openzeppelin/contracts-upgradeable/": ("openzeppelin-contracts-upgradeable", "contracts/"),
         "account-abstraction/": ("account-abstraction", "contracts/"), "@account-abstraction/contracts/": ("account-abstraction", "contracts/"),
         "@chainlink/contracts/src/": ("chainlink-evm", "contracts/src/"), "solady/": ("solady", "src/"), "@uniswap/v4-core/": ("v4-core", ""), "v4-core/": ("v4-core", ""),
         "@uniswap/v4-periphery/": ("v4-periphery", ""), "solmate/": ("solmate", ""), "forge-std/": ("forge-std", "src/"), "permit2/": ("permit2", "")}
def parse_idea(idea):
    t = idea.lower(); scores = collections.Counter(); why = collections.defaultdict(list)
    for c in tax["capabilities"]:
        for s in c["synonyms"] + [c["label"].lower()]:
            if re.search(r"\b" + re.escape(s.lower()) + r"\b", t): scores[c["id"]] += 1.0 + 0.1 * len(s.split()); why[c["id"]].append(s)
    try:
        from fastembed import TextEmbedding
        import numpy as np
        cv = json.load(open(f"{IDX}/taxonomy/capabilities.vectors.json")); V = np.array(cv["vectors"], dtype=np.float32)
        q = np.array(list(TextEmbedding(cv["model"]).embed([idea]))[0], dtype=np.float32); q /= np.linalg.norm(q)
        s = V @ q; mu, sd = float(s.mean()), float(s.std()) or 1
        for i in np.argsort(-s)[:6]:
            z = (float(s[i]) - mu) / sd
            if z >= 1.6: scores[cv["ids"][i]] += 0.4 * z; why[cv["ids"][i]].append(f"semantic z={z:.2f}")
    except Exception as e:
        print("semantic step skipped:", e, file=sys.stderr)
    return [{"id": k, "score": round(v, 3), "why": why[k]} for k, v in scores.most_common() if v >= 0.9]
def load_components(slug):
    p = f"{IDX}/components/{slug}.json"
    return json.load(open(p)) if os.path.exists(p) else []
VM_LANGS = {"EVM": {"Solidity", "Vyper", "Circom", "Noir", "TypeScript"}, "Hedera": {"Solidity", "TypeScript", "Circom", "Noir"},
            "Move": {"Move", "TypeScript"}, "Solana": {"Rust", "TypeScript"}, "Cosmos": {"Rust", "Go", "TypeScript"}, "Starknet": {"Cairo", "TypeScript"}, "Substrate": {"Rust", "TypeScript"}}
LANG_WORDS = {"circom": "Circom", "noir": "Noir", "vyper": "Vyper", "move": "Move", "cairo": "Cairo", "solidity": "Solidity", "anchor": "Rust", "cosmwasm": "Rust", "ink!": "Rust"}
def lang_hints(idea):
    t = (idea or "").lower()
    return {v for k, v in LANG_WORDS.items() if re.search(r"\b" + re.escape(k) + r"\b", t)}
LIC_RANK = {"permissive": 0, "weak-copyleft": 1, "strong-copyleft": 2, "unknown": 3, "source-available": 9}
def retrieve(capid, vm="EVM", k=3, idea=""):
    c = caps[capid]; okl = VM_LANGS.get(vm); hints = lang_hints(idea); pref = [p.split(":", 1) for p in c["preferred"]]
    cands = []
    for slug, r in repos.items():
        if vm and not okl and vm not in r["tags"] and vm not in ("Any",): continue
        for comp in load_components(slug):
            if okl and comp.get("lang") and comp["lang"] not in okl: continue  # VM compatibility
            if hints and comp.get("lang") in VM_LANGS.get(vm, set()) - {"TypeScript", "Solidity"} and comp["lang"] not in hints: continue  # user named a circuit language
            rule = next((x["score"] for x in comp["caps"] if x["id"] == capid), 0)
            sem = next((x["score"] for x in comp.get("caps_semantic", []) if x["id"] == capid), 0)
            boost = 1.0 if [slug, comp["path"]] in pref or any(slug == p[0] and comp["path"].startswith(p[1]) for p in pref if len(p) > 1) else 0
            if rule == 0 and boost == 0: continue
            if comp["kind"] in ("interface",) and capid not in ("price-oracle",): rule *= 0.6
            stars = math.log10((r.get("stars") or 10) + 10) / 5
            lic = LIC_RANK.get(comp["license_class"], 3)
            if lic >= 9: continue
            score = rule + 0.3 * sem + 1.2 * boost + stars - 0.15 * lic + (0.8 if comp.get("lang") in hints else 0)
            cands.append({"id": comp["id"], "slug": slug, "name": comp["name"], "path": comp["path"], "kind": comp["kind"], "lang": comp.get("lang"), "license": comp.get("spdx"),
                          "license_class": comp["license_class"], "pragma": comp.get("pragma"), "score": round(score, 3), "raw_url": comp.get("raw_url"), "commit": r["commit"], "fork": r["fork"], "upstream": r["upstream"]})
    cands.sort(key=lambda x: -x["score"])
    out, seen = [], set()
    for c in cands:  # one entry per file
        if (c["slug"], c["path"]) in seen: continue
        seen.add((c["slug"], c["path"])); out.append(c)
    return out[:k]
def license_verdict(sel, excluded=()):
    cls = [s["license_class"] for s in sel]
    note = (" Not copied (source-available, e.g. BUSL): " + ", ".join(f"{e['slug']}:{e['path']} ({e['license']})" for e in excluded) + "; use them only as unmodified dependencies under their own terms.") if excluded else ""
    if "strong-copyleft" in cls:
        gpl = sorted({s["license"] for s in sel if s["license_class"] == "strong-copyleft"})
        return {"project_license": "GPL-3.0-or-later" if not any("AGPL" in (g or "") for g in gpl) else "AGPL-3.0", "warning": f"Includes strong-copyleft files ({', '.join(gpl)}); the composed project is distributed under GPL terms." + note}
    if "weak-copyleft" in cls: return {"project_license": "MIT", "warning": "Includes LGPL/MPL files: kept unmodified with headers; LGPL text shipped in NOTICE." + note}
    return {"project_license": "MIT", "warning": note.strip() or None}
def plan(idea, vm="EVM"):
    need = parse_idea(idea)
    ids = {n["id"] for n in need}
    sub = {i for n in need for i in caps[n["id"]].get("subsumes", [])}
    need = [n for n in need if n["id"] not in sub]  # e.g. dex-hook subsumes amm-dex
    sel, per, excluded = [], {}, []
    for n in need:
        got = retrieve(n["id"], vm, idea=idea)
        per[n["id"]] = got
        if got: sel.append({**got[0], "capability": n["id"], "role": "primary"})
        # companions: preferred components for this capability that exist in the index
        for pref in caps[n["id"]]["preferred"][:4]:
            slug, _, path = pref.partition(":")
            if not path.endswith((".sol", ".circom", ".nr", ".vy")) or any(s["slug"] == slug and s["path"] == path for s in sel): continue
            comp = next((c for c in load_components(slug) if c["path"] == path and (c["type"] == "contract" or c.get("lang") in ("Circom", "Noir"))), None)
            if comp and comp.get("lang") in ("Circom", "Noir") and lang_hints(idea) & {"Circom", "Noir"} and comp["lang"] not in lang_hints(idea): continue
            if comp and LIC_RANK.get(comp["license_class"], 3) >= 9:
                excluded.append({"slug": slug, "path": path, "license": comp.get("spdx")}); continue
            if comp and repos.get(slug):
                r = repos[slug]
                sel.append({"id": comp["id"], "slug": slug, "name": comp["name"], "path": path, "kind": comp["kind"], "lang": comp.get("lang"), "license": comp.get("spdx"), "license_class": comp["license_class"],
                            "pragma": comp.get("pragma"), "score": None, "raw_url": comp.get("raw_url"), "commit": r["commit"], "fork": r["fork"], "upstream": r["upstream"], "capability": n["id"], "role": "companion"})
    always = retrieve("dev-framework", vm, 1)
    return {"idea": idea, "vm": vm, "generated_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "capabilities": need,
            "selected": sel, "alternatives": {k: v[1:] for k, v in per.items()}, "license": license_verdict(sel, excluded), "excluded": excluded, "index_generated_at": cat["generated_at"]}
PINS = {}
def gh_json(path, method="GET", fields=None):
    import subprocess
    cmd = ["gh", "api", "-X", method, path] + sum([["-f", f"{k}={v}"] for k, v in (fields or {}).items()], [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    return json.loads(p.stdout) if p.returncode == 0 and p.stdout.strip() else None
def resolve_pin(slug, tag):
    """Pin a component repo to an upstream release tag; mirror the tag into the Blockchains fork so raw URLs resolve."""
    r = repos[slug]
    if tag == "latest":
        rel = gh_json(f"repos/{r['upstream']}/releases/latest"); tag = rel["tag_name"] if rel else None
        if not tag: return r["commit"], None
    ref = gh_json(f"repos/{r['upstream']}/git/ref/tags/{tag}")
    sha = ref["object"]["sha"]
    if ref["object"]["type"] == "tag": sha = gh_json(f"repos/{r['upstream']}/git/tags/{sha}")["object"]["sha"]
    if not gh_json(f"repos/{r['fork']}/git/ref/tags/{tag}"):
        gh_json(f"repos/{r['fork']}/git/refs", "POST", {"ref": f"refs/tags/{tag}", "sha": sha})
    return sha, tag
def commit_for(slug):
    return PINS.get(slug, (repos[slug]["commit"], None))[0]
def raw(slug, path):
    r = repos[slug]; url = f"https://raw.githubusercontent.com/{r['fork']}/{commit_for(slug)}/{path}"
    with urllib.request.urlopen(url, timeout=30) as f: return f.read().decode()
IMP = re.compile(r'^\s*import\s+(?:[^"\']*from\s+)?["\']([^"\']+)["\']', re.M)
CIRCOM_INC = re.compile(r'^\s*include\s+"([^"]+)"', re.M)
def fetch(planf, out):
    p = json.load(open(planf)); seen = {}
    for slug, tag in (p.get("pins") or {}).items():
        PINS[slug] = resolve_pin(slug, tag); print("pinned", slug, PINS[slug], file=sys.stderr)
    queue = [(s["slug"], s["path"]) for s in p["selected"] if s["path"].endswith((".sol", ".circom", ".nr", ".vy"))]
    while queue:
        slug, path = queue.pop()
        if (slug, path) in seen: continue
        src = raw(slug, path); seen[(slug, path)] = src
        for imp in IMP.findall(src) + (CIRCOM_INC.findall(src) if path.endswith(".circom") else []):
            if imp.startswith(".") or (path.endswith(".circom") and "/" not in imp):
                np_ = os.path.normpath(os.path.join(os.path.dirname(path), imp)); queue.append((slug, np_))
            else:
                for pre, (s2, base) in REMAP.items():
                    if imp.startswith(pre): queue.append((s2, base + imp[len(pre):])); break
                else: print("unresolved import", imp, "in", slug, path, file=sys.stderr)
    files = []
    for (slug, path), src in seen.items():
        dst = os.path.join(out, "lib", slug, path); os.makedirs(os.path.dirname(dst), exist_ok=True); open(dst, "w").write(src)
        files.append({"slug": slug, "path": path, "dest": f"lib/{slug}/{path}", "fork": repos[slug]["fork"], "commit": commit_for(slug), "tag": PINS.get(slug, (None, None))[1], "upstream": repos[slug]["upstream"], "license": repos[slug]["license"]})
    remaps = sorted({f"{pre}=lib/{s2}/{base}" for pre, (s2, base) in REMAP.items() if any(f['slug'] == s2 for f in files)})
    bysrc = collections.defaultdict(list)
    for f in files: bysrc[(f["slug"], f["fork"], f["commit"] + (f" (tag {f['tag']})" if f.get("tag") else ""), f["upstream"], f["license"])].append(f["path"])
    notice = ["NOTICE", "", "This project was composed by Blockchain Lab Forge (https://blockchainlab.com/forge) from the following open-source projects.",
              "Files are copied unmodified, with their original SPDX headers, under lib/<project>/.", ""]
    for (slug, fork, commit, up, lic), paths in sorted(bysrc.items()):
        notice += [f"- {up} (via https://github.com/{fork} @ {commit}) - licence: {lic}", *[f"    {x}" for x in sorted(paths)], ""]
    open(os.path.join(out, "NOTICE"), "w").write("\n".join(notice))
    json.dump({"idea": p["idea"], "capabilities": p["capabilities"], "selected": p["selected"], "license": p["license"], "copied_files": files, "remappings": remaps}, open(os.path.join(out, "component-map.json"), "w"), indent=1)
    print(json.dumps({"copied": len(files), "remappings": remaps}, indent=1))
if __name__ == "__main__":
    if sys.argv[1] == "plan":
        vm = sys.argv[sys.argv.index("--vm") + 1] if "--vm" in sys.argv else "EVM"
        pl = plan(sys.argv[2], vm)
        if "--json" in sys.argv: json.dump(pl, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=1)
        print(json.dumps({"capabilities": pl["capabilities"], "selected": [(s["capability"], s["slug"], s["path"], s["name"], s["license"], s["score"]) for s in pl["selected"]], "license": pl["license"]}, indent=1))
    elif sys.argv[1] == "fetch": fetch(sys.argv[2], sys.argv[3])
