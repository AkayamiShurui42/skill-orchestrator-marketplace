"""ChatGPT + Codex remote MCP adapter. Install: python -m pip install -r server/requirements.txt
Run: python server/mcp_server.py (localhost-only streamable HTTP at /mcp).
Do not directly expose to the public internet without identity-aware authentication.
"""
from __future__ import annotations
import os
try:
    from mcp.server.fastmcp import FastMCP
except ImportError as exc:
    raise SystemExit('Missing MCP SDK. Run: python -m pip install -r server/requirements.txt') from exc
try:
    from . import api
except ImportError:
    import api

HOST = os.environ.get('SKILL_ORCHESTRATOR_BIND', '127.0.0.1')
PORT = int(os.environ.get('SKILL_ORCHESTRATOR_PORT', '8765'))
if HOST not in ('127.0.0.1','localhost','::1') and os.environ.get('SKILL_ORCHESTRATOR_ALLOW_EXTERNAL_BIND') != 'I_UNDERSTAND_THE_SECURITY_RISK':
    raise SystemExit('Refusing external bind. Use a secure authenticated tunnel. Do not expose this write-enabled API unauthenticated.')

mcp = FastMCP(name='Skill Orchestrator', instructions=(
    'Before substantial task work, call prepare_task. For EACH required_skill returned, call activate_skill, '
    'perform the instructions appropriately, report_skill_result honestly, then audit_task. '
    'For candidate replacements, present replace / keep both / reject and require explicit user permission. '
    'Never silently install or replace. Search/update TTL is seven days but activation is per task.'
),host=HOST,port=PORT)

@mcp.tool()
def prepare_task(prompt: str, project_root: str = '', task_id: str = '') -> dict:
    """Start task planning, map ALL relevant skill areas, reuse approved skills, run GitHub discovery only if due per seven-day cache. Must be called before substantive work when the plugin is in use. Read-only for user files, but writes audit/cache metadata."""
    return api.prepare_task(prompt, project_root, task_id)

@mcp.tool()
def activate_skill(task_id: str, skill_id: str) -> dict:
    """REQUIRED individually for each applicable approved skill on EVERY task, even if update discovery is cached. Returns its full SKILL.md; reading it alone does not count as performing its workflow."""
    return api.activate_skill(task_id, skill_id)

@mcp.tool()
def report_skill_result(task_id: str, skill_id: str, status: str, summary: str, verification: str = '') -> dict:
    """After actual execution, record skill completed or blocked, with truthful evidence and verification. Never report a skill successful merely because it was loaded. This does not prove independent validation."""
    return api.report_skill_result(task_id, skill_id, status, summary, verification)

@mcp.tool()
def audit_task(task_id: str) -> dict:
    """Inspect required skills versus per-task activations and completion evidence; disclose incomplete or blocked steps."""
    return api.audit_task(task_id)

@mcp.tool()
def list_skills() -> dict:
    """List approved local and managed skills available to the orchestrator, with capabilities and provenance."""
    return api.list_skills()

@mcp.tool()
def review_candidate(candidate_id: str) -> dict:
    """Show GitHub candidate and overlapping installed skills for comparison. This only provides metadata, NOT a security review, and does not install anything."""
    return api.review_candidate(candidate_id)

@mcp.tool()
def decide_candidate(candidate_id: str, action: str, explicitly_user_approved: bool = False, replace_id: str = '') -> dict:
    """WRITE ACTION with download and registry changes! Only call AFTER user explicitly chooses 'replace', 'keep both', or 'reject' for THIS named candidate and after security review. 'replace' requires replace_id. No decision means no change. Do not invent user consent."""
    return api.decide_candidate(candidate_id, action, explicitly_user_approved, replace_id)

if __name__=='__main__':
    mcp.run(transport='streamable-http')
