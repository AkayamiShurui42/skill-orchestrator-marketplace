# Skill Orchestrator — standalone install kit v0.3.0

The self-contained skill is under `skill-orchestrator/` and contains a genuine `SKILL.md` plus Python CLI for local discovery, state and execution audit. It works with agent hosts supporting skills; it does not install itself into an account-wide ChatGPT plugin.

Install: `python install_skill.py --dry-run`, then `python install_skill.py`. Windows: `py -3 .\install_skill.py`.

For ChatGPT's personal Plugin Creator, import the `skill-orchestrator/SKILL.md` instructions if skill import is supported on your account. The plugin itself must still be created and authorized within the ChatGPT UI. Publishing to GitHub does not activate it in ChatGPT.

Existing installation: installer asks for replace/keep-both/reject; non-interactive installs fail closed. Run `python install_skill.py --help` for options.

The `scripts/orchestrator.py` program uses Python standard library, local SQLite, and GitHub's public API only when a task preflight needs discovery. No remote code is automatically executed.