#!/usr/bin/env python3
"""Install Skill Orchestrator as one local agent skill; no elevated privileges needed."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import shutil
import sys
import uuid

SOURCE = Path(__file__).resolve().parent / "skill-orchestrator"

def install(home=None, location="agents", destination=None, conflict="ask", dry_run=False):
    if not (SOURCE / "SKILL.md").is_file():
        raise FileNotFoundError("Missing skill-orchestrator/SKILL.md")
    home = Path(home or Path.home()).expanduser()
    roots = {"agents": home / ".agents" / "skills", "codex": home / ".codex" / "skills"}
    base = Path(destination).expanduser() if destination else roots[location]
    target = base / "skill-orchestrator"
    original = target
    if target.exists() and conflict == "ask":
        if dry_run:
            print("An existing skill was found; installation will require a choice.")
        elif not sys.stdin.isatty():
            raise RuntimeError("Existing skill found. Choose --conflict replace|keep-both|deny explicitly.")
        else:
            choice = input("Existing skill: [r]eplace / [k]eep both / [d]eny? ").strip().lower()
            conflict = {"r":"replace", "k":"keep-both", "d":"deny"}.get(choice, "deny")
    if target.exists() and conflict == "deny":
        print("Denied: the existing skill is unchanged.")
        return None
    if target.exists() and conflict == "keep-both":
        target = base / ("skill-orchestrator-alt-" + uuid.uuid4().hex[:8])
    print("Target:", target)
    if dry_run:
        print("Dry run only. No files changed.")
        return target
    if target.resolve() == SOURCE.resolve():
        raise ValueError("Refusing to overwrite installer source")
    if target.exists() and conflict not in ("replace",):
        raise RuntimeError("Refusing overwrite without explicit replace")
    base.mkdir(parents=True, exist_ok=True)
    temp = base / (".skill-orchestrator-staging-" + uuid.uuid4().hex)
    backup = None
    try:
        shutil.copytree(SOURCE, temp)
        if original.exists() and conflict == "keep-both":
            p = temp / "SKILL.md"
            content = p.read_text(encoding="utf-8")
            p.write_text(content.replace("name: skill-orchestrator\n", "name: " + target.name + "\n", 1), encoding="utf-8")
        if target.exists() and conflict == "replace":
            backup = base / ("skill-orchestrator.backup-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6])
            target.rename(backup)
        temp.rename(target)
    except Exception:
        if temp.exists():
            shutil.rmtree(temp)
        if backup and backup.exists() and not original.exists():
            backup.rename(original)
        raise
    if backup:
        print("Old version saved at:", backup)
    print("Installed:", target)
    return target

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Install the local Skill Orchestrator agent skill")
    parser.add_argument("--home", help="Override user home for testing")
    parser.add_argument("--location", choices=("agents", "codex"), default="agents")
    parser.add_argument("--destination", help="Explicit skills parent directory")
    parser.add_argument("--conflict", choices=("ask", "replace", "keep-both", "deny"), default="ask")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    install(args.home, args.location, args.destination, args.conflict, args.dry_run)