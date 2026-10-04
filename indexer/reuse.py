"""Per-repo reuse hints for catalog.json (additive field `reuse`). Category notes live in taxonomy/reuse.json.

reuse(entry, packages) -> {"method", "pin", "install", "notes", "license_note", "category_notes"}
`entry` is a catalog repo entry (needs fork, name, commit, category, license_class, languages_bytes, tags, install_commands);
`packages` is the per-repo index.json `packages` list (dicts with ecosystem/name/path/private).
"""

import re

LICENSE_NOTES = {
    "permissive": "Permissive licence: keep the copyright/licence notice and SPDX headers; add a NOTICE when copying files.",
    "weak-copyleft": "Weak copyleft (LGPL/MPL): modified files stay under the same licence; linking/importing unmodified files is fine.",
    "strong-copyleft": "Strong copyleft (GPL/AGPL): distributing a combined work makes it GPL/AGPL too; use as a separate process or tool, or accept the licence.",
    "source-available": "Source-available (e.g. BUSL-1.1): do not copy into production code; read for reference only.",
    "unknown": "No clear licence detected: treat as all rights reserved; reference only until the upstream licence is confirmed.",
}


# Repos whose language bytes mislead the heuristic (vendored/generated Solidity in an app repo).
OVERRIDES = {"rainbowkit": "npm", "trueblocks-core": "source"}


def _top_lang(entry):
    lb = entry.get("languages_bytes") or {}
    return max(lb, key=lb.get) if lb else None


def _pkgs(packages, eco):
    return [p for p in packages or [] if isinstance(p, dict) and p.get("ecosystem") == eco and not p.get("private")]


def reuse(entry, packages):
    fork, name, commit = entry["fork"], entry["fork"].split("/")[1], entry["commit"]
    lang, tags = _top_lang(entry), set(entry.get("tags") or [])
    lb = entry.get("languages_bytes") or {}
    out = {"method": "source", "pin": commit, "install": [], "notes": "",
           "license_note": LICENSE_NOTES.get(entry.get("license_class") or "unknown", LICENSE_NOTES["unknown"]),
           "category_notes": f"taxonomy/reuse.json#{entry.get('category')}"}
    npm, go, cargo, pypi = _pkgs(packages, "npm"), _pkgs(packages, "go"), _pkgs(packages, "cargo"), _pkgs(packages, "pypi")
    sol_share = lb.get("Solidity", 0) / (sum(lb.values()) or 1)
    forced = OVERRIDES.get(name)
    if forced is None and entry.get("category") in ("languages-compilers", "security"):
        forced = "auto"   # compilers/analysers ship Solidity test fixtures, not contracts to import
    if forced in (None, "forge") and (lang == "Solidity" or sol_share >= 0.3) or forced == "forge":
        out["method"] = "forge"
        out["install"] = [f"forge install {fork}@{commit}"]
        root_npm = sorted((p for p in npm if p.get("path") in ("package.json", "contracts/package.json")), key=lambda p: p["path"] != "contracts/package.json")
        if root_npm:
            out["install"].append(f"# or, for Hardhat/npm projects: npm i {root_npm[0]['name']}")
        out["notes"] = (f"Add a remapping to the folder that holds the contracts, e.g. `{name}/=lib/{name}/<contracts-dir>/`; "
                        "pin the same OpenZeppelin release the fork uses (Blockchains/openzeppelin-contracts@<tag>). Copy single files only with their SPDX header.")
    elif forced == "source":
        pass
    elif (lang in ("TypeScript", "JavaScript") or forced == "npm") and npm:
        root = [p for p in npm if p.get("path") == "package.json"]
        if root and len(npm) == 1:
            out["method"] = "npm-git"
            out["install"] = [f"npm i github:{fork}#{commit}"]
            out["notes"] = f"Package name `{root[0]['name']}`; if it is published, `npm i {root[0]['name']}` at the matching upstream version is usually simpler (no build step)."
        else:
            out["method"] = "npm-registry"
            key = re.sub(r"[^a-z0-9]", "", name.lower())
            cand = [p["name"] for p in npm if p.get("path") != "package.json"] or [p["name"] for p in npm]
            cand = [n for n in cand if not re.search(r"test|example|template|internal|site$|app$|frontend|backend|^src$|_build", n)]
            cand = [n for n in cand if n.startswith("@") or key in re.sub(r"[^a-z0-9]", "", n.lower())]
            names = sorted(cand, key=lambda n: (re.sub(r"[^a-z0-9]", "", n.split("/")[-1].lower()) != key, key not in re.sub(r"[^a-z0-9]", "", n.lower())))[:5]
            out["install"] = [f"npm i {n}" for n in names[:3]]
            if not names:
                out["method"] = "source"
            kind = f"Monorepo ({len(npm)} npm packages, e.g. {', '.join(names)})" if len(npm) > 1 or not names else f"Package `{names[0]}` lives in a sub-folder"
            out["notes"] = (f"{kind}: npm cannot install a sub-folder package from git, "
                            f"so install the published package (check with `npm view <pkg>`) and read/compare source at {fork}@{commit[:7]}.")
    elif lang == "Rust" and cargo:
        crate = cargo[0]["name"]
        out["method"] = "cargo-git"
        out["install"] = [f"cargo add {crate} --git https://github.com/{fork} --rev {commit}"]
        out["notes"] = f"{len(cargo)} crates in this workspace (e.g. {', '.join(p['name'] for p in cargo[:5])}); swap the crate name as needed. Published crates on crates.io are usually preferable."
    elif lang == "Go" and go:
        root = next((p for p in go if p.get("path") == "go.mod"), go[0])
        mod = root["name"]
        out["method"] = "go-replace"
        out["install"] = [f"go get {mod}", f"go mod edit -replace={mod}=github.com/{fork}@{commit}", "go mod tidy"]
        out["notes"] = f"The module path stays `{mod}` (upstream); the replace directive points it at the pinned fork commit."
    elif lang == "Python" and pypi:
        root = next((p for p in pypi if p.get("path") in ("pyproject.toml", "setup.py", "setup.cfg")), pypi[0])
        sub = root["path"].rsplit("/", 1)[0] if "/" in root["path"] else ""
        url = f"git+https://github.com/{fork}@{commit}" + (f"#subdirectory={sub}" if sub else "")
        out["method"] = "pip-git"
        out["install"] = [f'pip install "{url}"']
        out["notes"] = f"Distribution `{root['name']}`; the PyPI release of the same version is usually simpler."
    if out["method"] == "source":
        out["install"] = [f"git clone https://github.com/{fork} && cd {name} && git checkout {commit}"] + list(entry.get("install_commands") or [])[:4]
        out["notes"] = "Application, node or non-package project: build from source with the upstream instructions, or run the upstream release binary/container. Reuse via its RPC/API rather than importing code."
    return out
