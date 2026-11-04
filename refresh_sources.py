#!/usr/bin/env python3
"""Cache original X videos and author avatars without changing review status."""
import argparse
import copy
import json
import shutil
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import store
import xsource


def refresh_group(cases):
    errors = []
    try:
        metadata = xsource.resolve_post(cases[0]["source"]["url"])
    except Exception as e:
        metadata = {}
        errors.append(str(e))
    shared = next((c["media"] for c in cases if xsource.playable(c.get("media") or {})), None)
    updated = []
    for original in cases:
        case = copy.deepcopy(original)
        if shared:
            case["media"] = shared
        case, issues = xsource.enrich(case, metadata=metadata)
        errors.extend(issues)
        if xsource.playable(case.get("media") or {}):
            shared = case["media"]
        updated.append(case)
    with store.locked():
        current = store.load_cases()
        by_id = {c["id"]: c for c in current}
        for case in updated:
            live = by_id.get(case["id"])
            if not live or live.get("source", {}).get("url") != case["source"]["url"]:
                continue
            for key in ("media", "source", "discovery", "updated_at"):
                if key in case:
                    live[key] = case[key]
            live["tags"] = [t for t in live.get("tags") or [] if t != "launchvideos.gallery"]
        store.save_cases(current)
    return {"ids": [c["id"] for c in updated], "videos": sum(xsource.playable(c.get("media") or {}) for c in updated),
            "avatars": sum(bool(c.get("source", {}).get("avatar")) for c in updated), "errors": errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", help="Refresh one case and other cases from the same X post")
    parser.add_argument("--workers", type=int, default=2)
    args = parser.parse_args()
    cases = [c for c in store.load_cases() if c.get("type") in {"video", "showcase"}
             and c.get("status") != "rejected" and xsource.post_id(c.get("source", {}).get("url"))]
    groups = {}
    for case in cases:
        groups.setdefault(store.norm_url(case["source"]["url"]), []).append(case)
    if args.id:
        groups = {key: group for key, group in groups.items() if any(c["id"] == args.id for c in group)}
    backup = Path(store.DATA) / "backups" / ("cases-before-x-media-" + store.now_iso().replace(":", "-") + ".json")
    backup.parent.mkdir(exist_ok=True)
    with store.locked():
        shutil.copy2(store.CASES, backup)
    print(json.dumps({"groups": len(groups), "records": sum(map(len, groups.values())), "backup": str(backup)}, ensure_ascii=False), flush=True)
    with ThreadPoolExecutor(max_workers=max(1, min(4, args.workers))) as pool:
        jobs = [pool.submit(refresh_group, group) for group in groups.values()]
        for count, future in enumerate(as_completed(jobs), 1):
            print(json.dumps({"completed": count, "total": len(jobs), **future.result()}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
