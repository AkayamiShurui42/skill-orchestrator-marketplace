---
name: setup-skill-orchestrator
description: Configure and verify the shared Skill Orchestrator plugin for ChatGPT and Codex; choose secure MCP connection and trusted hooks.
---

# Setup workflow

1. Explain that ChatGPT Work uses a connected MCP server, while Codex desktop can additionally use an explicitly trusted `UserPromptSubmit` hook.
2. Do not assume this plugin is activated in every ordinary ChatGPT conversation. The model needs to invoke the plugin and it must be available to that surface.
3. On the machine running Codex, point `SKILL_ORCHESTRATOR_DATA` to the intended writable registry path if a custom location is desired; use the same path for the MCP server to share records on the same host.
4. For local Codex, install via the provided `install.py`, inspect and explicitly trust the hook definitions, and test a fresh prompt.
5. For ChatGPT, start the MCP server on localhost, use an authenticated Secure MCP Tunnel or an authenticated HTTPS proxy, add the `/mcp` endpoint as a custom MCP server in ChatGPT Plugins, and enable it in a supported conversation such as ChatGPT Work.
6. Call `list_skills` and `prepare_task` for an example task. Activate each required approved skill separately, execute the relevant workflow, report results, and audit.
7. Test each candidate choice: replacement, keep both, rejection. Never invoke the write operation without explicit user approval.
8. Explain the seven-day cache, immediate every-task activation, known limitations and untested environments. Never claim background monitoring absent an actual scheduled service.
