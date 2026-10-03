#!/usr/bin/env python3
"""Refresh stars/description/archived for every source via the GitHub API (gh CLI)."""
import json, subprocess, sys
p = sys.argv[1]; src = json.load(open(p)); n = 0
for s in src:
    r = subprocess.run(["gh", "api", f"repos/{s['upstream']}", "--jq", "{stars: .stargazers_count, description: .description, archived: .archived, pushed_at: .pushed_at}"], capture_output=True, text=True)
    if r.returncode == 0:
        s.update(json.loads(r.stdout)); n += 1
json.dump(src, open(p, "w"), indent=1)
print(f"refreshed {n}/{len(src)}")
