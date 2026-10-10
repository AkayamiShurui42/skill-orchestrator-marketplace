# Skill Orchestrator GitHub Marketplace (v0.2.1)

A GitHub-ready **Codex/ChatGPT desktop plugin marketplace**, built from Skill Orchestrator v0.2.1. This is the **repository contents**: upload the contents of this folder to a dedicated repository root, preserving `.agents/` and `plugins/` directories. Do not upload this ZIP as the only repository file.

## Option A: GitHub distribution for Codex

1. Create an empty repository, for example `YOUR_USERNAME/skill-orchestrator-marketplace` (private or public; never assume your repo exists).
2. Push the contents of this ZIP into its default branch.
3. Install the marketplace in a recent Codex CLI:

   ```sh
   codex plugin marketplace add YOUR_USERNAME/skill-orchestrator-marketplace
   codex plugin marketplace list
   ```

4. In ChatGPT Desktop / Codex, open the Plugins Directory, find **Skill Orchestrator Marketplace**, select **Skill Orchestrator**, and install it. Review the hook scripts and grant trust only if appropriate.
5. To pick up repository updates:

   ```sh
   codex plugin marketplace upgrade skill-orchestrator-marketplace
   ```

The GitHub repository is a **distribution and update source**. It is not an MCP server. It does not force always-on ChatGPT mobile/web skill selection.

## Option B: ChatGPT GitHub-connector mode without custom MCP

The connected GitHub app can be used to discover and review skills and to work on repositories. The bundled `github-connector-mode` skill describes the fallback workflow. To make this workflow persistently available, use ChatGPT's Plugin Creator to create/install a personal skill-only plugin containing the `skills/` files plus the connected GitHub app, or install this marketplace plugin through a supported local desktop surface. Simply attaching this ZIP does **not** register it in the ChatGPT plugin directory.

**Limits:** Seven-day checks across conversations cannot be reliably enforced without persistent state. GitHub can store files and versions but cannot host a live write-enabled MCP service using a static repo. User approval is always needed for discovered skills; never auto-install unreviewed code.

## Option C: Full ChatGPT MCP orchestration

The `plugins/skill-orchestrator/server/` folder contains an MCP server. To use all orchestration tools in ChatGPT web/mobile, securely host it with authentication, register that endpoint as a custom MCP app where supported, and attach it to a personal plugin using Plugin Creator. Do **not** expose the local HTTP server publicly without auth. See `plugins/skill-orchestrator/chatgpt/CONNECT.md`.

## Tests

```sh
python -m unittest discover -s plugins/skill-orchestrator/tests -v
```

These test command lines and marketplace paths match current OpenAI plugin marketplace docs, but installation in your actual Codex/ChatGPT account must be performed by the user on a supported client.
