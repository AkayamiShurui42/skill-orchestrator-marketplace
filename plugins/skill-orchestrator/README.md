# Skill Orchestrator v0.2.1 — portable ChatGPT / Codex plugin

A packaged skill-driven orchestrator plus optional local Codex hooks and an MCP server adapter. This package is a plugin folder, not an automatically connected ChatGPT account.

## Codex Desktop on Windows

Extract the ZIP. In PowerShell **from the extracted ZIP parent**:

```powershell
py -3 .\skill-orchestrator\install.py --dry-run
py -3 .\skill-orchestrator\install.py
```

The installer copies it to `%USERPROFILE%\.codex\plugins\skill-orchestrator` and registers a personal marketplace entry in `%USERPROFILE%\.agents\plugins\marketplace.json`. Existing installations require **replace**, **keep both**, or **deny** selection; no silent upgrade. It also adds an identifiable policy section to `.codex\AGENTS.md` (omit via `--no-global-policy`). Restart Codex and explicitly review/trust its hooks in the local Plugins Directory.

For a collision, pass `--on-conflict replace`, `--on-conflict keep-both` or `--on-conflict deny` only after choosing that outcome.

## ChatGPT

See `chatgpt/CONNECT.md`. The included `server/mcp_server.py` must be separately deployed over an authenticated, secure MCP connection; a ZIP alone does not activate backend tools in ChatGPT. A skills-only local plugin may be loaded on eligible desktop/Work surfaces. Hook automation is Codex-specific and host-dependent.

## Validation

Unzip the source/test package, or run `python -m unittest discover -s tests -v` in the development distribution. The packaged files have been checked for valid manifests and Python syntax.

No newly discovered GitHub skills are installed without explicit user approval. Skill activation is required every task when this plugin is actually invoked, even while the discovery cache remains fresh. Execution logs are self-reports, not proof that work was done.
