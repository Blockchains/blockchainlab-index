#!/usr/bin/env python3
"""Blockchain Lab full-source ingestion.
Shallow, blob-filtered, no-checkout clone of each Blockchains fork -> structured code index.
Usage: ingest.py <repos.json> <outdir> [--workdir DIR] [--jobs N] [--keep]
repos.json: list of {slug, fork, branch, upstream, category, ...}. Reads blobs from git objects (no working tree)."""
import json, os, re, subprocess, sys, shutil, hashlib, collections, concurrent.futures as cf, time, datetime
MAXBLOB = 400_000
SKIP_DIRS = re.compile(r"(^|/)(node_modules|vendor|third_party|3rdparty|dist|build|out|target|\.git|artifacts|cache|coverage|\.next|bower_components|site-packages|testdata|fixtures?)(/|$)", re.I)
TEST_DIRS = re.compile(r"(^|/)(tests?|spec|mocks?|examples?|scripts?|benches|e2e|certora|echidna|fuzz)(/|$)|\.t\.sol$|_test\.go$|\.test\.[tj]sx?$|\.spec\.[tj]sx?$", re.I)
EXT_LANG = {".sol":"Solidity",".vy":"Vyper",".move":"Move",".rs":"Rust",".cairo":"Cairo",".go":"Go",".ts":"TypeScript",".tsx":"TypeScript",".js":"JavaScript",".mjs":"JavaScript",".py":"Python",".circom":"Circom",".nr":"Noir",".java":"Java",".kt":"Kotlin",".c":"C",".cc":"C++",".cpp":"C++",".h":"C/C++ header",".hpp":"C++",".swift":"Swift",".zig":"Zig",".hs":"Haskell",".ml":"OCaml",".ex":"Elixir",".rb":"Ruby",".cs":"C#",".yul":"Yul",".huff":"Huff",".fe":"Fe",".scala":"Scala",".dart":"Dart",".php":"PHP"}
LIC_FILE = re.compile(r"^(LICEN[CS]E|COPYING|UNLICENSE)([-._][A-Za-z0-9.-]+)?(\.md|\.txt)?$", re.I)

def sh(cmd, cwd=None, inp=None, timeout=900):
    return subprocess.run(cmd, cwd=cwd, input=inp, capture_output=True, timeout=timeout, env={**os.environ, "GIT_LFS_SKIP_SMUDGE": "1", "GIT_TERMINAL_PROMPT": "0"})

class Repo:
    def __init__(s, d): s.d = d
    def ls(s):
        p = sh(["git", "ls-tree", "-r", "-l", "--full-tree", "HEAD"], cwd=s.d)
        out = []
        for line in p.stdout.decode("utf-8", "replace").splitlines():
            meta, _, path = line.partition("\t")
            parts = meta.split()
            if len(parts) < 4 or parts[1] != "blob": continue
            size = int(parts[3]) if parts[3].isdigit() else 0
            out.append((path, size, parts[2]))
        return out
    def read_many(s, shas):
        """batch read blobs present locally; returns {sha: text}"""
        if not shas: return {}
        res = {}
        p = subprocess.Popen(["git", "cat-file", "--batch"], cwd=s.d, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                             env={**os.environ, "GIT_NO_LAZY_FETCH": "1"})
        data, _ = p.communicate(("\n".join(shas) + "\n").encode())
        i = 0
        while i < len(data):
            nl = data.index(b"\n", i); hdr = data[i:nl].decode(); i = nl + 1
            parts = hdr.split()
            if len(parts) < 3 or parts[1] == "missing": continue
            n = int(parts[2]); res[parts[0]] = data[i:i+n].decode("utf-8", "replace"); i += n + 1
        return res

# ---------------- parsers ----------------
SOL_DECL = re.compile(r"^\s*(abstract\s+contract|contract|interface|library)\s+([A-Za-z_]\w*)\s*(is\s+([^{]+))?\{", re.M)
SOL_FUNC = re.compile(r"\bfunction\s+([A-Za-z_]\w*)\s*\(([^)]*)\)([^;{]*)", re.S)
SOL_EVENT = re.compile(r"\bevent\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*(anonymous)?\s*;", re.S)
SOL_ERROR = re.compile(r"\berror\s+([A-Za-z_]\w*)\s*\(([^)]*)\)\s*;", re.S)
SPDX = re.compile(r"SPDX-License-Identifier:\s*([A-Za-z0-9.+\- ()]+?)\s*(\*/|$)", re.M)
PRAGMA = re.compile(r"pragma\s+solidity\s+([^;]+);")
def strip_comments(src):
    src = re.sub(r"/\*.*?\*/", lambda m: "\n" * m.group(0).count("\n"), src, flags=re.S)
    return re.sub(r"//[^\n]*", "", src)
def norm_params(p):
    p = " ".join(p.split())
    out = []
    for a in [x.strip() for x in p.split(",") if x.strip()]:
        toks = [t for t in a.split() if t not in ("memory", "calldata", "storage", "payable", "indexed")]
        if not toks: continue
        out.append({"type": toks[0], "name": toks[1] if len(toks) > 1 else ""})
    return out
def block_end(src, start):
    depth = 0
    for i in range(start, len(src)):
        c = src[i]
        if c == "{": depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0: return i
    return len(src)
def parse_solidity(src):
    raw = src; src = strip_comments(src); items = []
    for m in SOL_DECL.finditer(src):
        kind = "abstract contract" if m.group(1).startswith("abstract") else m.group(1)
        bstart = m.end() - 1; bend = block_end(src, bstart); body = src[bstart:bend]
        line = src.count("\n", 0, m.start()) + 1
        bases = [b.strip().split("(")[0].strip() for b in (m.group(4) or "").split(",") if b.strip()]
        fns, abi = [], []
        for f in SOL_FUNC.finditer(body):
            mods = " ".join(f.group(3).split())
            vis = next((v for v in ("external", "public", "internal", "private") if re.search(rf"\b{v}\b", mods)), "public" if kind == "interface" else "internal")
            if vis not in ("external", "public"): continue
            mut = next((v for v in ("view", "pure", "payable") if re.search(rf"\b{v}\b", mods)), "nonpayable")
            rets = re.search(r"returns\s*\((.*)\)", mods)
            ins = norm_params(f.group(2)); outs = norm_params(rets.group(1)) if rets else []
            sig = f"{f.group(1)}({','.join(x['type'] for x in ins)})"
            fns.append(sig)
            abi.append({"type": "function", "name": f.group(1), "inputs": ins, "outputs": outs, "stateMutability": mut})
        evs = []
        for e in SOL_EVENT.finditer(body):
            ins = norm_params(e.group(2)); evs.append(f"{e.group(1)}({','.join(x['type'] for x in ins)})")
            abi.append({"type": "event", "name": e.group(1), "inputs": ins})
        errs = []
        for e in SOL_ERROR.finditer(body):
            ins = norm_params(e.group(2)); errs.append(f"{e.group(1)}({','.join(x['type'] for x in ins)})")
            abi.append({"type": "error", "name": e.group(1), "inputs": ins})
        items.append({"kind": kind, "name": m.group(2), "line": line, "bases": bases, "functions": fns, "events": evs, "errors": errs, "abi": abi})
    spdx = SPDX.search(raw); pr = PRAGMA.search(src)
    return items, (spdx.group(1).strip() if spdx else None), (pr.group(1).strip() if pr else None)
def parse_vyper(src):
    fns, evs, ext = [], [], False
    lines = src.splitlines()
    for i, l in enumerate(lines):
        if l.strip().startswith("@external") or l.strip().startswith("@view") and ext: ext = True
        m = re.match(r"def\s+(\w+)\s*\(([^)]*)\)", l)
        if m:
            deco = " ".join(x.strip() for x in lines[max(0, i-3):i])
            if "@external" in deco: fns.append(f"{m.group(1)}({' '.join(m.group(2).split())})")
        m = re.match(r"event\s+(\w+)\s*:", l)
        if m: evs.append(m.group(1))
    return [{"kind": "vyper contract", "functions": fns, "events": evs}] if fns or evs else []
MOVE_MOD = re.compile(r"\bmodule\s+([\w:]+)\s*[{;]")
MOVE_FUN = re.compile(r"\bpublic(?:\s*\((?:friend|package)\))?\s+(entry\s+)?fun\s+(\w+)(?:<[^>]*>)?\s*\(([^)]*)\)", re.S)
MOVE_STRUCT = re.compile(r"\b(?:public\s+)?struct\s+(\w+)(?:<[^>]*>)?\s*(?:has\s+([\w, ]+))?")
def parse_move(src):
    src = strip_comments(src); out = []
    mods = list(MOVE_MOD.finditer(src))
    for idx, m in enumerate(mods):
        body = src[m.end(): mods[idx+1].start() if idx+1 < len(mods) else len(src)]
        fns = [("entry " if f.group(1) else "") + f"{f.group(2)}({' '.join(f.group(3).split())[:120]})" for f in MOVE_FUN.finditer(body)]
        structs = [s.group(1) + (f" has {s.group(2).strip()}" if s.group(2) else "") for s in MOVE_STRUCT.finditer(body)]
        out.append({"kind": "move module", "name": m.group(1), "line": src.count("\n", 0, m.start()) + 1, "functions": fns[:150], "structs": structs[:80]})
    return out
def parse_rust_contract(src):
    out = []
    if "#[program]" in src:
        m = re.search(r"#\[program\]\s*pub\s+mod\s+(\w+)", src)
        if m:
            body = src[m.end(): block_end(src, src.find("{", m.end()))]
            fns = re.findall(r"pub\s+fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(", body)
            out.append({"kind": "anchor program", "name": m.group(1), "functions": fns})
    if "ink::contract" in src or "#[ink(message" in src:
        m = re.search(r"pub\s+mod\s+(\w+)", src)
        fns = re.findall(r"#\[ink\(message[^\]]*\)\]\s*pub\s+fn\s+(\w+)", src)
        evs = re.findall(r"#\[ink\(event\)\]\s*pub\s+struct\s+(\w+)", src)
        out.append({"kind": "ink contract", "name": m.group(1) if m else "", "functions": fns, "events": evs})
    if "sol_storage!" in src or "#[public]" in src and "stylus" in src:
        fns = re.findall(r"pub\s+fn\s+(\w+)", src)
        out.append({"kind": "stylus contract", "functions": fns[:100]})
    if "#[cw_serde]" in src or "cosmwasm_std" in src and "pub fn execute" in src:
        msgs = re.findall(r"pub\s+enum\s+(\w*Msg)\b", src)
        out.append({"kind": "cosmwasm", "messages": msgs})
    return out
def parse_cairo(src):
    out = []
    for m in re.finditer(r"#\[starknet::(contract|interface|component)\]\s*(?:pub\s+)?(?:mod|trait)\s+(\w+)", src):
        body = src[m.end(): block_end(src, src.find("{", m.end()))]
        fns = re.findall(r"fn\s+(\w+)\s*(?:<[^>]*>)?\s*\(", body)
        evs = re.findall(r"#\[derive\([^)]*starknet::Event[^)]*\)\]\s*(?:pub\s+)?(?:struct|enum)\s+(\w+)", body)
        out.append({"kind": f"cairo {m.group(1)}", "name": m.group(2), "functions": fns[:150], "events": evs})
    return out
def parse_go(src):
    pkg = re.search(r"^package\s+(\w+)", src, re.M)
    exp = re.findall(r"^func\s+(?:\([^)]*\)\s*)?([A-Z]\w*)\s*\(", src, re.M)
    types = re.findall(r"^type\s+([A-Z]\w*)\s+(struct|interface)", src, re.M)
    return (pkg.group(1) if pkg else None), exp, types
def parse_circom(src):
    return [{"kind": "circom template", "name": t} for t in re.findall(r"\btemplate\s+(\w+)\s*\(", src)]
def parse_noir(src):
    return re.findall(r"\bpub\s+fn\s+(\w+)", src)

def tags_for(langs, contracts, paths, deps, topics, packages):
    t = set(); s = " ".join(paths[:20000]).lower(); topics = set(topics or [])
    dep = " ".join(deps).lower()
    if "Solidity" in langs or "Vyper" in langs or "Yul" in langs or "Huff" in langs: t.add("EVM")
    if any(x in dep for x in ("viem", "ethers", "web3", "wagmi", "alloy", "go-ethereum", "revm")) or topics & {"ethereum", "evm"}: t.add("EVM")
    if "Move" in langs or topics & {"move", "sui", "aptos"}: t.add("Move")
    if any(c.get("kind") == "anchor program" for c in contracts) or any(x in dep for x in ("solana-program", "anchor-lang", "@solana/web3.js", "solana-sdk", "@solana/kit")) or "solana" in topics: t.add("SVM")
    if "cosmos-sdk" in dep or "cosmwasm" in dep or "cosmos" in topics or "@cosmjs" in dep: t.add("Cosmos")
    if any(x in dep for x in ("frame-support", "sp-runtime", "substrate", "ink", "@polkadot/api")) or topics & {"substrate", "polkadot"}: t.add("Substrate")
    if "Cairo" in langs or "starknet" in dep or "starknet" in topics: t.add("Starknet")
    if "bitcoin" in topics or any(x in dep for x in ("bitcoin", "bdk", "lightning", "bitcoinjs")): t.add("Bitcoin")
    if "hedera" in topics or "hashgraph" in dep or "hiero" in dep or "hedera" in s[:5000]: t.add("Hedera")
    if "Circom" in langs or "Noir" in langs or topics & {"zk", "zkp", "zero-knowledge", "zk-snarks", "zkvm", "snark"} or any(x in dep for x in ("snarkjs", "halo2", "plonky", "risc0", "sp1-", "arkworks", "ark-")): t.add("ZK")
    allf = set(); bases = set()
    for c in contracts:
        allf.update(f.split("(")[0] for f in c.get("functions", [])); bases.update(c.get("bases", [])); bases.add(c.get("name", ""))
    def has(*fs): return all(f in allf for f in fs)
    if has("transfer", "approve", "totalSupply", "balanceOf") or bases & {"ERC20", "IERC20"}: t.add("ERC-20")
    if has("safeTransferFrom", "ownerOf") or bases & {"ERC721", "IERC721"}: t.add("ERC-721")
    if has("safeBatchTransferFrom") or bases & {"ERC1155", "IERC1155"}: t.add("ERC-1155")
    if has("convertToShares", "previewDeposit") or bases & {"ERC4626", "IERC4626"}: t.add("ERC-4626")
    if "validateUserOp" in allf or bases & {"IAccount", "BaseAccount", "IEntryPoint", "EntryPoint"}: t.add("ERC-4337")
    if "permit" in allf or bases & {"ERC20Permit", "IERC20Permit"}: t.add("ERC-2612")
    if "eip712Domain" in allf or bases & {"EIP712"}: t.add("EIP-712")
    if "supportsInterface" in allf: t.add("ERC-165")
    if "upgradeToAndCall" in allf or bases & {"UUPSUpgradeable", "ERC1967Proxy", "TransparentUpgradeableProxy"}: t.add("Proxy/Upgradeable")
    if "latestRoundData" in allf or "AggregatorV3Interface" in bases: t.add("Chainlink-Feeds")
    if any(p.endswith("foundry.toml") for p in paths): t.add("Foundry")
    if any(re.search(r"hardhat\.config\.(ts|js|cjs|mjs)$", p) for p in paths): t.add("Hardhat")
    if any(p.endswith("Anchor.toml") for p in paths): t.add("Anchor")
    if any(p.endswith("Move.toml") for p in paths): t.add("Move-package")
    if any(p.endswith("Nargo.toml") for p in paths): t.add("Noir")
    if any(p.endswith("Scarb.toml") for p in paths): t.add("Scarb")
    for pk in packages:
        if pk.get("ecosystem") == "npm": t.add("npm"); break
    if any(p.get("ecosystem") == "cargo" for p in packages): t.add("Rust-crates")
    if any(p.get("ecosystem") == "go" for p in packages): t.add("Go-module")
    return sorted(t)

INSTALL_RE = re.compile(r"^\s*\$?\s*((?:npm|pnpm|yarn|bun|npx|forge|cast|anvil|foundryup|cargo|go|make|just|pip|pip3|uv|poetry|brew|docker|curl -L|git clone|nargo|circom|snarkjs|sui|aptos|anchor|solana|hardhat|scarb|rustup|apt|apt-get)\b[^\n]{0,160})$", re.M)
def readme_summary(text):
    if not text: return "", []
    t = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    cmds = []
    for blk in re.findall(r"```[^\n]*\n(.*?)```", t, flags=re.S):
        for m in INSTALL_RE.finditer(blk):
            c = m.group(1).strip()
            if c not in cmds: cmds.append(c)
    body = re.sub(r"```.*?```", "", t, flags=re.S)
    paras = []
    for p in re.split(r"\n\s*\n", body):
        q = re.sub(r"<[^>]+>", "", p); q = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", q); q = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", q)
        q = " ".join(q.split()).strip()
        if len(q) < 60 or q.startswith("#") or q.startswith("|") or q.lower().startswith(("table of contents", "build status")): continue
        paras.append(q)
        if sum(len(x) for x in paras) > 700: break
    return " ".join(paras)[:900], cmds[:25]

def index_repo(r, workdir, keep=False):
    slug = r["slug"]; d = os.path.join(workdir, slug); t0 = time.time()
    if os.path.exists(d): shutil.rmtree(d)
    url = f"https://github.com/{r['fork']}.git"
    p = sh(["git", "clone", "--depth", "1", "--single-branch", "--branch", r["branch"], f"--filter=blob:limit={MAXBLOB}", "--no-checkout", "--quiet", url, d], timeout=1800)
    if p.returncode:
        return {"slug": slug, "status": "clone-failed", "error": p.stderr.decode()[-300:]}
    R = Repo(d); head = sh(["git", "rev-parse", "HEAD"], cwd=d).stdout.decode().strip()
    files = R.ls()
    tree = [[pth, sz] for pth, sz, _ in files]
    ext_count = collections.Counter(); ext_bytes = collections.Counter()
    want = {}
    for pth, sz, sha in files:
        ext = os.path.splitext(pth)[1].lower(); lang = EXT_LANG.get(ext)
        if lang and not SKIP_DIRS.search(pth): ext_count[lang] += 1; ext_bytes[lang] += sz
        base = os.path.basename(pth)
        if sz > MAXBLOB: continue
        if SKIP_DIRS.search(pth) and not base.startswith(("README", "LICENSE")): continue
        if ext in (".sol", ".vy", ".move", ".cairo", ".circom", ".nr") or base in ("package.json", "Cargo.toml", "go.mod", "pyproject.toml", "Move.toml", "Anchor.toml", "Nargo.toml", "Scarb.toml", "foundry.toml", "remappings.txt", ".gitmodules", "setup.py") or LIC_FILE.match(base) and pth.count("/") <= 1 or (pth.count("/") == 0 and base.lower().startswith("readme")):
            want[pth] = sha
        elif ext == ".rs" and not TEST_DIRS.search(pth) and (base in ("lib.rs",) or "programs/" in pth or "contracts/" in pth or "pallets/" in pth):
            want[pth] = sha
        elif ext == ".go" and not TEST_DIRS.search(pth) and pth.count("/") <= 4:
            want[pth] = sha
        elif ext == ".json" and ("/abi" in pth.lower() or pth.lower().startswith("abi") or base.lower().endswith(".abi.json")) and sz < 200_000:
            want[pth] = sha
    # cap Go files for very large repos
    gofiles = [p for p in want if p.endswith(".go")]
    if len(gofiles) > 3000:
        for p in sorted(gofiles, key=lambda x: x.count("/"))[3000:]: want.pop(p)
    blobs = R.read_many(list(set(want.values())))
    txt = {p: blobs.get(s) for p, s in want.items() if blobs.get(s) is not None}
    contracts, packages, deps, licenses, spdx_c = [], [], set(), [], collections.Counter()
    go_pk = collections.defaultdict(lambda: {"exported": set(), "types": set(), "files": 0})
    readme = ""; abis = []
    for pth, src in sorted(txt.items()):
        base = os.path.basename(pth); ext = os.path.splitext(pth)[1].lower(); is_test = bool(TEST_DIRS.search(pth))
        try:
            if ext == ".sol":
                items, spdx, prag = parse_solidity(src)
                if spdx: spdx_c[spdx] += 1
                for it in items:
                    it.update({"path": pth, "lang": "Solidity", "pragma": prag, "spdx": spdx, "test": is_test})
                    contracts.append(it)
            elif ext == ".vy":
                for it in parse_vyper(src): it.update({"path": pth, "lang": "Vyper", "name": os.path.splitext(base)[0], "test": is_test}); contracts.append(it)
            elif ext == ".move":
                for it in parse_move(src): it.update({"path": pth, "lang": "Move", "test": is_test}); contracts.append(it)
            elif ext == ".cairo":
                for it in parse_cairo(src): it.update({"path": pth, "lang": "Cairo", "test": is_test}); contracts.append(it)
            elif ext == ".circom":
                for it in parse_circom(src): it.update({"path": pth, "lang": "Circom", "test": is_test}); contracts.append(it)
            elif ext == ".nr":
                fns = parse_noir(src)
                if fns: contracts.append({"kind": "noir module", "name": os.path.splitext(base)[0], "functions": fns, "path": pth, "lang": "Noir", "test": is_test})
            elif ext == ".rs":
                for it in parse_rust_contract(src): it.update({"path": pth, "lang": "Rust", "test": is_test}); contracts.append(it)
                m = SPDX.search(src)
                if m: spdx_c[m.group(1).strip()] += 1
            elif ext == ".go":
                pkg, exp, types = parse_go(src); key = os.path.dirname(pth) or "."
                go_pk[key]["exported"].update(exp); go_pk[key]["types"].update(f"{a} {b}" for a, b in types); go_pk[key]["files"] += 1; go_pk[key]["name"] = pkg
            elif base == "package.json":
                j = json.loads(src)
                if not isinstance(j, dict): continue
                ex = j.get("exports"); exk = sorted(ex.keys())[:60] if isinstance(ex, dict) else ([ex] if isinstance(ex, str) else [])
                dd = list((j.get("dependencies") or {}).keys()); pd = list((j.get("peerDependencies") or {}).keys())
                deps.update(dd + pd + list((j.get("devDependencies") or {}).keys())[:80])
                if j.get("name") and not is_test:
                    packages.append({"ecosystem": "npm", "name": j.get("name"), "version": j.get("version"), "path": pth, "private": bool(j.get("private")),
                                     "description": (j.get("description") or "")[:200], "license": j.get("license"), "main": j.get("main") or j.get("module"),
                                     "types": j.get("types") or j.get("typings"), "exports": exk, "bin": list(j["bin"].keys()) if isinstance(j.get("bin"), dict) else ([j["name"]] if j.get("bin") else []),
                                     "dependencies": dd[:60], "peerDependencies": pd[:30], "scripts": list((j.get("scripts") or {}).keys())[:30]})
            elif base == "Cargo.toml":
                name = re.search(r'^\[package\][^\[]*?^name\s*=\s*"([^"]+)"', src, re.M | re.S)
                ver = re.search(r'^version\s*=\s*"([^"]+)"', src, re.M); lic = re.search(r'^license\s*=\s*"([^"]+)"', src, re.M)
                dsec = re.findall(r'^\[(?:workspace\.)?dependencies\]\s*\n(.*?)(?=^\[|\Z)', src, re.M | re.S)
                dd = [l.split("=")[0].strip() for sec in dsec for l in sec.splitlines() if "=" in l and not l.strip().startswith("#")]
                deps.update(dd[:150])
                if name and not is_test: packages.append({"ecosystem": "cargo", "name": name.group(1), "version": ver.group(1) if ver else None, "path": pth, "license": lic.group(1) if lic else None, "dependencies": dd[:50]})
            elif base == "go.mod":
                mod = re.search(r"^module\s+(\S+)", src, re.M); req = re.findall(r"^\s*([\w.\-/]+\.[\w.\-/]+)\s+v[\w.\-+]+", src, re.M)
                deps.update(req[:200])
                if mod: packages.append({"ecosystem": "go", "name": mod.group(1), "path": pth, "dependencies": req[:60]})
            elif base == "pyproject.toml":
                n = re.search(r'^name\s*=\s*"([^"]+)"', src, re.M)
                if n: packages.append({"ecosystem": "pypi", "name": n.group(1), "path": pth})
            elif base == "Move.toml":
                n = re.search(r'^name\s*=\s*"([^"]+)"', src, re.M); packages.append({"ecosystem": "move", "name": n.group(1) if n else None, "path": pth})
            elif base == "Scarb.toml":
                n = re.search(r'^name\s*=\s*"([^"]+)"', src, re.M); packages.append({"ecosystem": "scarb", "name": n.group(1) if n else None, "path": pth})
            elif base == "Nargo.toml":
                n = re.search(r'^name\s*=\s*"([^"]+)"', src, re.M); packages.append({"ecosystem": "nargo", "name": n.group(1) if n else None, "path": pth})
            elif base == ".gitmodules":
                deps.update(re.findall(r"url\s*=\s*(\S+)", src))
            elif LIC_FILE.match(base):
                first = " ".join(src.strip().split()[:40])
                guess = next((k for k, pat in [("MIT", r"Permission is hereby granted, free of charge"), ("Apache-2.0", r"Apache License"), ("GPL-3.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 3"), ("GPL-2.0", r"GNU GENERAL PUBLIC LICENSE\s+Version 2"), ("LGPL-3.0", r"GNU LESSER GENERAL PUBLIC LICENSE\s+Version 3"), ("AGPL-3.0", r"GNU AFFERO"), ("BUSL-1.1", r"Business Source License"), ("MPL-2.0", r"Mozilla Public License"), ("BSD-3-Clause", r"Redistributions in binary form.*?Neither the name"), ("BSD-2-Clause", r"Redistributions in binary form"), ("ISC", r"ISC License|Permission to use, copy, modify, and/or distribute"), ("Unlicense", r"This is free and unencumbered")] if re.search(pat, src[:6000], re.S | re.I)), None)
                licenses.append({"path": pth, "detected": guess, "head": first[:200]})
            elif pth.count("/") == 0 and base.lower().startswith("readme"):
                readme = src
            elif ext == ".json":
                j = json.loads(src); a = j.get("abi") if isinstance(j, dict) else j
                if isinstance(a, list) and a and isinstance(a[0], dict) and "type" in a[0]:
                    abis.append({"path": pth, "functions": [x.get("name") for x in a if x.get("type") == "function"][:80], "events": [x.get("name") for x in a if x.get("type") == "event"][:40]})
        except Exception as e:
            pass
    gopk = []
    for k, v in sorted(go_pk.items()):
        if not v["exported"] and not v["types"]: continue
        gopk.append({"dir": k, "package": v.get("name"), "files": v["files"], "exported_funcs": sorted(v["exported"])[:120], "exported_types": sorted(v["types"])[:80]})
    summary, cmds = readme_summary(readme)
    langs = dict(ext_bytes.most_common())
    tags = tags_for(langs, contracts, [x[0] for x in tree], list(deps), r.get("topics"), packages)
    prod = [c for c in contracts if not c.get("test")]
    idx = {"slug": slug, "fork": r["fork"], "upstream": r["upstream"], "branch": r["branch"], "commit": head, "indexed_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "category": r.get("category"), "description": r.get("description"), "readme_summary": summary, "install_commands": cmds,
           "languages_bytes": langs, "file_count": len(tree), "total_bytes": sum(x[1] for x in tree),
           "licenses": licenses, "license_spdx_github": r.get("license_spdx"), "spdx_headers": dict(spdx_c.most_common(10)),
           "packages": packages[:400], "dependencies": sorted(deps)[:600], "tags": tags,
           "contracts": [{k: v for k, v in c.items() if k != "abi"} for c in prod][:3000],
           "contracts_test_count": len(contracts) - len(prod), "go_packages": gopk[:800], "abi_files": abis[:200],
           "raw_base": f"https://raw.githubusercontent.com/{r['fork']}/{r['branch']}/"}
    abi_map = {f"{c['path']}:{c['name']}": c["abi"] for c in prod if c.get("abi") and c.get("lang") == "Solidity"}
    if not keep: shutil.rmtree(d, ignore_errors=True)
    return {"slug": slug, "status": "ok", "index": idx, "tree": tree, "abi": abi_map, "secs": round(time.time() - t0, 1)}

def main():
    src, outdir = sys.argv[1], sys.argv[2]
    workdir = sys.argv[sys.argv.index("--workdir") + 1] if "--workdir" in sys.argv else "/workspace/bl-ingest"
    jobs = int(sys.argv[sys.argv.index("--jobs") + 1]) if "--jobs" in sys.argv else 4
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    keep = "--keep" in sys.argv
    os.makedirs(workdir, exist_ok=True); os.makedirs(f"{outdir}/repos", exist_ok=True)
    repos = json.load(open(src))
    if only: repos = [r for r in repos if r["slug"] in only]
    status = {}
    sp = f"{outdir}/ingest-status.json"
    if os.path.exists(sp): status = json.load(open(sp))
    def run(r):
        free = shutil.disk_usage(workdir).free / 1e9
        if free < 8: return {"slug": r["slug"], "status": "skipped-disk-low", "free_gb": round(free, 1)}
        if "--force" not in sys.argv and status.get(r["slug"], {}).get("status") == "ok" and os.path.exists(f"{outdir}/repos/{r['slug']}/index.json"):
            p = sh(["git", "ls-remote", f"https://github.com/{r['fork']}.git", f"refs/heads/{r['branch']}"], timeout=60)
            remote = p.stdout.decode().split("\t")[0].strip()
            if remote and remote == status[r["slug"]].get("commit"):
                return {"slug": r["slug"], "status": "unchanged"}
        try: return index_repo(r, workdir, keep)
        except Exception as e: return {"slug": r["slug"], "status": "error", "error": repr(e)[:300]}
    with cf.ThreadPoolExecutor(jobs) as ex:
        for res in ex.map(run, repos):
            s = res["slug"]
            if res["status"] == "ok":
                od = f"{outdir}/repos/{s}"; os.makedirs(od, exist_ok=True)
                json.dump(res["index"], open(f"{od}/index.json", "w"), separators=(",", ":"))
                json.dump(res["tree"], open(f"{od}/tree.json", "w"), separators=(",", ":"))
                json.dump(res["abi"], open(f"{od}/abi.json", "w"), separators=(",", ":"))
                status[s] = {"status": "ok", "commit": res["index"]["commit"], "files": res["index"]["file_count"], "contracts": len(res["index"]["contracts"]), "secs": res["secs"]}
            elif res["status"] == "unchanged":
                continue
            else:
                status[s] = {k: v for k, v in res.items() if k != "slug"}
            print(datetime.datetime.now().strftime("%H:%M:%S"), s, status[s], flush=True)
            json.dump(status, open(sp, "w"), indent=1)
if __name__ == "__main__": main()
