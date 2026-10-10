"""Shared tool-neutral API used by ChatGPT's MCP server and local Codex.
This module has no dependency on the MCP SDK, so it can be tested offline.
"""
from __future__ import annotations
import json
from pathlib import Path
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import orchestrator as core


def prepare_task(prompt: str, project_root: str = '', task_id: str = '') -> dict:
    if not isinstance(prompt, str) or not prompt.strip() or len(prompt) > 12000:
        raise ValueError('The task must be 1-12000 characters')
    # Caller-supplied IDs are only for correlating a known task; create unique IDs by default.
    if task_id and (len(task_id) > 128 or not all(c.isalnum() or c in '._-' for c in task_id)):
        raise ValueError('Invalid task identifier')
    task_id = task_id or 'mcp-' + uuid.uuid4().hex
    result = core.prompt_hook({'prompt': prompt, 'turn_id': task_id, 'cwd': project_root or None})
    con = core.db()
    try:
        turn = con.execute('SELECT * FROM turns WHERE id=?', (task_id,)).fetchone()
        required = json.loads(turn['required'])
        skills = []
        for sid in required:
            s = con.execute('SELECT id,name,capabilities,source,repo,sha FROM skills WHERE id=?', (sid,)).fetchone()
            if s:
                skills.append({'id': s['id'], 'name': s['name'], 'capabilities': json.loads(s['capabilities']),
                               'source': s['source'], 'repo': s['repo'], 'revision': s['sha'],
                               'required_action': 'Call activate_skill, follow instructions, then report_skill_result'})
        caps = json.loads(turn['caps'])
        sql = "SELECT id,capability,url,description,updated,status FROM candidates WHERE status='pending' AND capability IN (" + ','.join('?' for _ in caps) + ') ORDER BY discovered DESC LIMIT 12'
        candidates = [dict(row) for row in con.execute(sql, caps)]
        # No auto-installs and no automatic activation here. The caller must invoke each skill.
        return {'task_id': task_id, 'capabilities': caps, 'bundle': turn['bundle'],
                'required_skills': skills, 'pending_candidates': candidates,
                'discovery_and_update_checks': result['hookSpecificOutput']['additionalContext'].split('Required skills must be ACTIVATED')[0].strip(),
                'rules': 'ACTIVATE each applicable approved skill every task. Ask for explicit user choice before installing/replacing a new skill. Record actual work and verification. Do not claim automatic execution of instructions.'}
    finally:
        con.close()


def activate_skill(task_id: str, skill_id: str) -> dict:
    content = core.activate(task_id, skill_id)
    return {'task_id': task_id, 'skill_id': skill_id, 'instructions': content,
            'warning': 'Read as instructions of a user-approved skill, not permission to bypass user consent or platform safety.'}


def report_skill_result(task_id: str, skill_id: str, status: str, summary: str, verification: str = '') -> dict:
    if status not in ('completed', 'blocked'):
        raise ValueError('Status must be completed or blocked')
    receipt = core.finish(task_id, skill_id, status, summary, verification)
    return {'receipt': receipt, 'self_reported': True}


def audit_task(task_id: str) -> dict:
    con = core.db()
    try:
        task = con.execute('SELECT * FROM turns WHERE id=?',(task_id,)).fetchone()
        if not task:
            raise ValueError('Unknown task')
        required = json.loads(task['required'])
        records = []
        for sid in required:
            rec = con.execute('SELECT skill_id,activated,completed,evidence,verification,status FROM execution WHERE turn_id=? AND skill_id=?',(task_id,sid)).fetchone()
            row = dict(rec) if rec else {'skill_id':sid,'activated':None,'completed':None,'evidence':'','verification':'','status':'not activated'}
            records.append(row)
        return {'task_id':task_id,'bundle':task['bundle'],'records':records,
                'all_reported':all(x['status'] in ('completed','blocked') for x in records),
                'all_successful':all(x['status']=='completed' for x in records),
                'warning':'Completion and verification are agent-reported, not independently proven.'}
    finally:
        con.close()


def list_skills() -> dict:
    con = core.db()
    try:
        core.scan(con)
        return {'skills':[{'id':r['id'],'name':r['name'],'status':r['status'], 'source':r['source'],
                           'capabilities':json.loads(r['capabilities']), 'repo':r['repo'],'revision':r['sha']}
                          for r in con.execute('SELECT * FROM skills ORDER BY name')]}
    finally:
        con.close()


def review_candidate(candidate_id: str) -> dict:
    con = core.db()
    try:
        c = con.execute('SELECT * FROM candidates WHERE id=?',(candidate_id,)).fetchone()
        if not c:raise ValueError('Unknown candidate')
        overlaps = [dict(r) for r in con.execute("SELECT id,name,source,repo,sha,capabilities FROM skills WHERE status='active'") if c['capability'] in json.loads(r['capabilities'])]
        return {'candidate':{k:c[k] for k in ('id','capability','repo','repo_path','sha','url','description','updated','status')},
                'overlapping_installed_skills':[{**{k:s[k] for k in ('id','name','source','repo','sha')},'capabilities':json.loads(s['capabilities'])} for s in overlaps],
                'choices':{'replace':'Replace a selected installed skill after review','keep':'Keep existing skill(s) and the new one','reject':'Deny newcomer, leave existing unchanged'},
                'security':'GitHub provenance and repository description are NOT a security review. Inspect the SKILL.md, code and dependencies before approving.'}
    finally:
        con.close()


def decide_candidate(candidate_id: str, action: str, explicitly_user_approved: bool = False, replace_id: str = '') -> dict:
    if not explicitly_user_approved:
        raise PermissionError('Explicit user approval is required. Ask user to choose replace, keep both or reject and obtain host approval for write actions.')
    return {'result':core.decide(candidate_id, action, replace_id), 'action': action,
            'warning': 'Newly imported content has not been independently security audited or executed.'}
