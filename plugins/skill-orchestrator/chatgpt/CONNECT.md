# ChatGPT setup for Skill Orchestrator v0.2.1

ChatGPT does **not** run Windows hook scripts locally for every prompt. Its connection path is the included MCP server, invoked when the plugin is available in ChatGPT Work or another supported plugin-enabled surface. Personalization instructions help guide use but do not provide a mandatory runtime hook.

## 1. Run the MCP server on your computer or trusted host

Install Python 3.10+ and open PowerShell in the directory containing the extracted `skill-orchestrator` folder:

```powershell
py -3 -m pip install -r .\skill-orchestrator\server\requirements.txt
$env:SKILL_ORCHESTRATOR_DATA = "$env:USERPROFILE\.codex\skill-orchestrator"
py -3 .\skill-orchestrator\server\mcp_server.py
```

The default is **loopback only**, on `http://127.0.0.1:8765/mcp`. ChatGPT cannot connect to that URL directly. Do not port-forward this HTTP server onto the public internet; it can import/write skill files.

## 2. Expose securely

Use OpenAI's [Secure MCP Tunnel](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels) where available, or an HTTPS proxy with real authentication and authorization, per user. Never use an unauthenticated public tunnel for this write-enabled tool set. Hosting this on another computer means the state database is also on that host: both systems only share one registry automatically when pointed at the **same database on the same host**.

## 3. Add it in ChatGPT

- Open **Plugins**, select **Add custom MCP server**, and choose your securely reachable endpoint or tunnel. Follow your workspace/plan's current eligibility and authorization steps.
- Test the tools, then install the resulting personal plugin. In supported chats such as **Work**, select `@Skill Orchestrator` to invoke its tools.
- For a portable local plugin that references a remote endpoint, run the Windows installer with `--mcp-url https://YOUR-AUTHENTICATED-HOST/mcp`, then review `mcp.json`. For ChatGPT's registered `plugin_asdk_app...` connection, use `@plugin-creator` in Work (or `$plugin-creator` in Codex) to map the registered app ID to a local plugin if needed. Do not invent an app ID.
- Optionally copy [CUSTOM_INSTRUCTIONS.md](./CUSTOM_INSTRUCTIONS.md) into your ChatGPT personalization/project instructions. This is **not** equivalent to a platform-enforced always-on plugin hook.

## 4. Test the workflow

Start a task: `Build an Android APK in Kotlin and Compose`. The expected call sequence is:

`prepare_task` → `activate_skill` individually for every relevant installed skill → perform the actual work → `report_skill_result` per skill → `audit_task`.

Ask for alternatives, choose one of: replace current, keep both, reject newcomer. The write tool requires an explicit approval flag **and user authorization**. A flag alone is not a security boundary; host/app permission prompts should also be configured appropriately.

## Limitations

No automatic skill invocation can be guaranteed across all ordinary ChatGPT conversations by installing an MCP app. Calling a skill returns its instructions; applying them still depends on the assistant and other permitted tools. GitHub queries need network access and can hit rate limits. The Python SDK dependency and HTTPS tunnel must be installed and configured by you; this package doesn't deploy them or connect your account on its own.
