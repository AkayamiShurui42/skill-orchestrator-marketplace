#!/usr/bin/env python3
"""Skill Orchestrator: standard-library-only task/skill registry for Codex hooks.
No Github content is ever installed or executed without a user decision.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import sys
import urllib.error
import urllib.parse
import urllib.request

WEEK = 7 * 86400
MAX_CONTEXT = 12500
DEFAULT_HOME = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
STATE = Path(os.environ.get('SKILL_ORCHESTRATOR_DATA', str(DEFAULT_HOME / 'skill-orchestrator')))
PLUGIN = Path(__file__).resolve().parents[1]
CAPS = {
 'planning': ['plan','requirements','roadmap','architecture','design specification'],
 'android': ['android','apk','kotlin','jetpack','gradle','shizuku','adb'],
 'ui-design': ['ui','ux','interface','compose','material design','visual','layout','design'],
 'programming': ['code','program','implement','script','developer','repository','refactor','fix'],
 'debugging': ['debug','crash','trace','bug','error','failure','logcat','diagnos'],
 'testing': ['test','qa','validate','unit test','integration test'],
 'building': ['build','compile','package','release','apk','gradle','deploy'],
 'review': ['review','audit','security','quality','inspect'],
 'finalization': ['deliver','release','sign','finalize','ship','publish','apk'],
 'maintenance': ['update','maintain','upgrade','dependency','compatibility','monitor'],
 'legal-research': ['law','legal','statute','regulation','case law','legislation'],
 'research': ['research','study','find','search','investigat','compare','analyze','evidence'],
 'documents': ['pdf','docx','document','report','write','word'],
 'data-analysis': ['data','csv','spreadsheet','excel','statistics','analytics'],
 'medical-research': ['medical','heart','clinical','diagnos','patient','health','study'],
 'video': ['video','frame','transcript','mp4'],
}
BUNDLES = {
 'android-apk-team': ['planning','android','ui-design','programming','debugging','testing','building','review','finalization','maintenance'],
 'legal-audit-team': ['legal-research','research','review','documents'],
 'research-team': ['research','review','documents'],
}
QUERIES = {
 'android':'android kotlin gradle agent skills SKILL.md',
 'ui-design':'ui ux design agent skills SKILL.md',
 'legal-research':'legal research agent skills SKILL.md',
 'medical-research':'clinical research agent skills SKILL.md',
}

def now(): return int(dt.datetime.now(dt.timezone.utc).timestamp())
def db():
 STATE.mkdir(parents=True,exist_ok=True)
 con=sqlite3.connect(str(STATE/'registry.sqlite3'),timeout=10)
 con.row_factory=sqlite3.Row
 con.execute('PRAGMA journal_mode=WAL')
 con.executescript('''
 CREATE TABLE IF NOT EXISTS skills(id TEXT PRIMARY KEY,name TEXT,path TEXT,source TEXT,repo TEXT,repo_path TEXT,sha TEXT,status TEXT NOT NULL, capabilities TEXT NOT NULL,last_scan INTEGER NOT NULL);
 CREATE TABLE IF NOT EXISTS discovery(capability TEXT PRIMARY KEY,last_success INTEGER NOT NULL,notes TEXT);
 CREATE TABLE IF NOT EXISTS skill_updates(skill_id TEXT PRIMARY KEY,last_success INTEGER NOT NULL,notes TEXT);
 CREATE TABLE IF NOT EXISTS discovery_attempts(capability TEXT PRIMARY KEY,last_failure INTEGER,notes TEXT);
 CREATE TABLE IF NOT EXISTS candidates(id TEXT PRIMARY KEY,capability TEXT,repo TEXT,repo_path TEXT,sha TEXT,url TEXT,description TEXT,updated TEXT,status TEXT DEFAULT 'pending', discovered INTEGER);
 CREATE TABLE IF NOT EXISTS turns(id TEXT PRIMARY KEY,started INTEGER,caps TEXT,required TEXT,bundle TEXT,prompt_hash TEXT,stop_retries INTEGER DEFAULT 0);
 CREATE TABLE IF NOT EXISTS execution(turn_id TEXT,skill_id TEXT,activated INTEGER,completed INTEGER,evidence TEXT,verification TEXT,status TEXT,PRIMARY KEY(turn_id,skill_id));
 ''')
 return con

def sha10(s): return hashlib.sha256(s.encode('utf-8')).hexdigest()[:12]
def words(s): return (s or '').lower()
def classify(prompt):
 p=words(prompt)
 cats=[c for c,terms in CAPS.items() if any(re.search(r'(?<!\w)'+re.escape(t),p) for t in terms)]
 bundle=''
 if re.search(r'\b(apk|android app|build (an?|the) app|create (an?|the) app)\b',p):
  bundle='android-apk-team'; cats=list(dict.fromkeys(cats+BUNDLES[bundle]))
 elif 'law' in cats or 'legal-research' in cats: bundle='legal-audit-team'
 if 'legal-research' in cats:
  cats=list(dict.fromkeys(cats+BUNDLES['legal-audit-team']))
 if not cats: cats=['research'] if '?' in p or len(p)>35 else ['planning']
 return cats,bundle

def metadata(path):
 try: content=path.read_text(encoding='utf-8',errors='replace')[:10000]
 except OSError: return '',''
 match=re.match(r'\A---\s*\n(.*?)\n---',content,re.S)
 head=match.group(1) if match else ''
 def get(k):
  m=re.search(r'^'+re.escape(k)+r':\s*["\']?(.*?)["\']?\s*$',head,re.M)
  return (m.group(1).strip('"\' ') if m else '')
 return get('name') or path.parent.name,get('description') or content[:550]

def skill_dirs(project=None):
 directories=[DEFAULT_HOME/'skills',Path.home()/'.agents'/'skills',PLUGIN/'skills',STATE/'managed']
 for root in (Path.home()/'plugins',DEFAULT_HOME/'plugins'):
  if root.is_dir():directories.extend(x/'skills' for x in root.iterdir() if x.is_dir())
 if project:
  cwd=Path(project).resolve()
  for parent in (cwd,*cwd.parents):
   directories.extend((parent/'.agents'/'skills',parent/'.codex'/'skills'))
 extra=os.environ.get('SKILL_ORCHESTRATOR_SKILL_DIRS','')
 directories.extend(Path(x) for x in extra.split(os.pathsep) if x)
 return [d for d in directories if d.exists()]

def scan(con,project=None):
 discovered=set()
 for base in skill_dirs(project):
  # Don't follow symlink skill files; never trust arbitrary directory trees as instructions without approval.
  try: paths=list(base.rglob('SKILL.md'))[:3000]
  except OSError: continue
  for file in paths:
   if file.is_symlink(): continue
   name,desc=metadata(file)
   ident='local-'+sha10(str(file.resolve()))
   discovered.add(ident)
   old=con.execute('SELECT status,repo,repo_path,sha,source,capabilities FROM skills WHERE id=?',(ident,)).fetchone()
   if old and old['status'] in ('replaced','disabled'): continue
   cats=[cap for cap,terms in CAPS.items() if any(re.search(r'(?<!\w)'+re.escape(t),words(name+' '+desc)) for t in terms)]
   if old and old['capabilities']:
    cats=list(dict.fromkeys(cats+json.loads(old['capabilities'])))
   source='managed' if STATE/'managed' in file.parents else 'local'
   con.execute('''INSERT INTO skills(id,name,path,source,repo,repo_path,sha,status,capabilities,last_scan)
    VALUES(?,?,?,?,?,?,?,\'active\',?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,path=excluded.path,
    capabilities=excluded.capabilities,last_scan=excluded.last_scan,status='active' WHERE skills.status IN ('active','missing')''',
    (ident,name,str(file),source,old['repo'] if old else '',old['repo_path'] if old else '',old['sha'] if old else '',json.dumps(cats),now()))
 # Preserve missing skill history but disable it to avoid claiming activation.
 con.execute('UPDATE skills SET status=\'missing\' WHERE status=\'active\' AND last_scan<?',(now()-180,))
 con.commit()
 return discovered

def matching_skills(con,cats):
 rows=con.execute("SELECT * FROM skills WHERE status='active' ORDER BY name").fetchall()
 return [dict(row) for row in rows if set(json.loads(row['capabilities'])) & set(cats)]

def gh_get(endpoint,timeout=5):
 url='https://api.github.com/'+endpoint.lstrip('/')
 token=os.environ.get('GITHUB_TOKEN','')
 headers={'User-Agent':'Codex-Skill-Orchestrator/0.1','Accept':'application/vnd.github+json'}
 if token: headers['Authorization']='Bearer '+token
 req=urllib.request.Request(url,headers=headers)
 with urllib.request.urlopen(req,timeout=timeout) as r: return json.load(r)

def search_github(con,cap):
 # 7-day TTL is recorded only for a successful GitHub query and processing pass.
 cached=con.execute('SELECT last_success FROM discovery WHERE capability=?',(cap,)).fetchone()
 if cached and now()-cached['last_success']<WEEK: return 'cached'
 failure=con.execute('SELECT last_failure FROM discovery_attempts WHERE capability=?',(cap,)).fetchone()
 if failure and failure['last_failure'] and now()-failure['last_failure']<3600:return 'temporary GitHub error; retry after one hour'
 query=QUERIES.get(cap,f'{cap.replace("-"," ")} agent skills SKILL.md')
 try:
  data=gh_get('search/repositories?'+urllib.parse.urlencode({'q':query,'sort':'updated','per_page':8}),4)
  count=0
  for item in data.get('items',[])[:5]:
   repo=item['full_name']; branch=item.get('default_branch') or 'main'
   tree=gh_get('repos/'+repo+'/git/trees/'+urllib.parse.quote(branch,safe='')+'?recursive=1',4)
   paths=[t['path'] for t in tree.get('tree',[]) if t.get('type')=='blob' and t.get('path','').endswith('/SKILL.md')]
   if not paths: continue
   # A repo may host many skills, prefer paths related to the capability.
   paths.sort(key=lambda x:(cap.replace('-',' ') not in words(x.replace('-',' ')),len(x)))
   path=paths[0]
   commit=gh_get('repos/'+repo+'/commits/'+urllib.parse.quote(branch,safe=''),4)['sha']
   cid='gh-'+sha10(repo+':'+path+':'+commit)
   url='https://github.com/'+repo+'/blob/'+commit+'/'+urllib.parse.quote(path)
   desc=(item.get('description') or '')[:450]
   con.execute('''INSERT OR IGNORE INTO candidates(id,capability,repo,repo_path,sha,url,description,updated,status,discovered)
   VALUES(?,?,?,?,?,?,?,?,\'pending\',?)''',(cid,cap,repo,path,commit,url,desc,item.get('updated_at',''),now()))
   count+=1
   if count>=3:break
  con.execute('INSERT INTO discovery VALUES(?,?,?) ON CONFLICT(capability) DO UPDATE SET last_success=excluded.last_success,notes=excluded.notes',(cap,now(),f'{count} verified SKILL.md candidates'))
  con.commit()
  return f'{count} candidates'
 except (OSError,KeyError,ValueError,urllib.error.HTTPError,urllib.error.URLError) as exc:
  con.execute('INSERT INTO discovery_attempts VALUES(?,?,?) ON CONFLICT(capability) DO UPDATE SET last_failure=excluded.last_failure,notes=excluded.notes',(cap,now(),str(exc)[:300]));con.commit()
  return 'GitHub unavailable: '+str(exc)[:100]


def check_skill_updates(con,skills):
    """Check each GitHub-sourced approved skill no more than once per seven days."""
    messages=[]
    for s in skills:
        if not s.get('repo') or not s.get('repo_path') or not s.get('sha'):
            continue  # Unknown upstream: cannot safely claim a source update check.
        cached=con.execute('SELECT last_success FROM skill_updates WHERE skill_id=?',(s['id'],)).fetchone()
        if cached and now()-cached['last_success']<WEEK:
            messages.append(s['name']+': cached')
            continue
        try:
            repo_info=gh_get('repos/'+s['repo'],4)
            branch=repo_info.get('default_branch') or 'main'
            commit=gh_get('repos/'+s['repo']+'/commits/'+urllib.parse.quote(branch,safe=''),4)['sha']
            if commit != s['sha']:
                cid='gh-'+sha10(s['repo']+':'+s['repo_path']+':'+commit)
                url='https://github.com/'+s['repo']+'/blob/'+commit+'/'+urllib.parse.quote(s['repo_path'])
                con.execute("INSERT OR IGNORE INTO candidates(id,capability,repo,repo_path,sha,url,description,updated,status,discovered) VALUES(?,?,?,?,?,?,?,?, 'pending', ?)",(cid,json.loads(s['capabilities'])[0],s['repo'],s['repo_path'],commit,url,'Update available for installed '+s['name'],repo_info.get('updated_at',''),now()))
                messages.append(s['name']+': newer commit available (approval required)')
            else:messages.append(s['name']+': up to date')
            con.execute('INSERT INTO skill_updates VALUES(?,?,?) ON CONFLICT(skill_id) DO UPDATE SET last_success=excluded.last_success,notes=excluded.notes',(s['id'],now(),messages[-1]))
            con.commit()
        except (OSError,KeyError,ValueError,urllib.error.HTTPError,urllib.error.URLError):
            messages.append(s['name']+': update check unavailable; last successful check unchanged')
    return messages

def safe_text(s): return s.replace('`',"'").replace('\r',' ')[:250]

def prompt_hook(payload):
 con=db(); scan(con,payload.get('cwd'))
 prompt=payload.get('prompt','')
 turn=str(payload.get('turn_id') or 'local-'+sha10(prompt+str(now())))
 cats,bundle=classify(prompt)
 required=matching_skills(con,cats)
 skill_checks=check_skill_updates(con,required)
 existing={s['id'] for s in required}
 con.execute('INSERT OR REPLACE INTO turns(id,started,caps,required,bundle,prompt_hash,stop_retries) VALUES(?,?,?,?,?,?,0)',(turn,now(),json.dumps(cats),json.dumps(sorted(existing)),bundle,sha10(prompt)))
 con.commit()
 # Search missing and stale capabilities, never interfere with applying existing installed skills.
 found=[]
 for cat in cats:
  result=search_github(con,cat)
  found.append(f'{cat}: {result}')
 pending=con.execute("SELECT * FROM candidates WHERE status='pending' AND capability IN ("+','.join('?'*len(cats))+") ORDER BY discovered DESC LIMIT 10",cats).fetchall()
 script=str(Path(__file__).resolve())
 instruction=['SKILL ORCHESTRATOR: this turn has deterministic pre-task checks.','Task ID: '+turn,
  'Relevant capability areas: '+', '.join(cats),
  'Team bundle: '+(bundle or 'none'),
  'GitHub 7-day discovery outcomes: '+', '.join(found),
  'Approved GitHub skills weekly checks: '+(', '.join(skill_checks) if skill_checks else 'none with known GitHub source'),
  'Required skills must be ACTIVATED separately; activation must call the CLI shown below and then apply the SKILL.md instructions in the task. Never count registry selection alone as execution.']
 if required:
  for s in required:
   instruction.append(f"ACTIVATE {s['id']} ({safe_text(s['name'])}): {json.dumps([sys.executable,script,'activate','--turn',turn,'--id',s['id']])}. Use the shell tool to run this command and read the returned skill instructions, then do that skill's work. When used, run {json.dumps([sys.executable,script,'complete','--turn',turn,'--id',s['id'],'--summary','<actual work>','--verification','<checks performed>'])}. If blocked, use command 'block' with a reason.")
 else: instruction.append('No approved matching skill found. Continue the task using available tools, state the gap, and offer any pending GitHub candidates for explicit approval.')
 if pending:
  instruction.append('DISCOVERED ALTERNATIVES. Do not install without user approval. For each relevant candidate compare with existing skills, and ASK: (1) replace current (2) keep both (3) reject newcomer. For a missing capability ask permission to add it (keep) or reject.')
  for c in pending[:8]:instruction.append(f"CANDIDATE {c['id']} [{c['capability']}] {c['url']} - {safe_text(c['description'])}")
  instruction.append('After explicit user choice invoke decide CLI: '+json.dumps([sys.executable,script,'decide','--id','<candidate-id>','--action','keep|replace|reject','--replace-id','<existing-skill-id-if-replacing>'])+'. If no decision, keep current approved skills unchanged.')
 instruction.append('Do not mark a skill completed merely for reading it. Continue with actual work, record evidence, and accurately disclose blocked stages. If task is maintenance-related, update review is only performed on user task or an explicitly scheduled job.')
 con.close()
 content='\n'.join(instruction)
 return {'hookSpecificOutput':{'hookEventName':'UserPromptSubmit','additionalContext':content[:MAX_CONTEXT]}}

def stop_hook(payload):
 con=db(); turn=str(payload.get('turn_id',''))
 row=con.execute('SELECT * FROM turns WHERE id=?',(turn,)).fetchone()
 if not row: return {}
 required=json.loads(row['required']); missing=[]
 for sid in required:
  ex=con.execute('SELECT status FROM execution WHERE turn_id=? AND skill_id=?',(turn,sid)).fetchone()
  if not ex or ex['status'] not in ('completed','blocked'):missing.append(sid)
 # One continuation request, then fail openly, not an infinite loop.
 if missing and row['stop_retries']<1 and not payload.get('stop_hook_active',False):
  con.execute('UPDATE turns SET stop_retries=stop_retries+1 WHERE id=?',(turn,));con.commit()
  return {'decision':'block','reason':'Skill activation/execution audit incomplete for '+', '.join(missing)+'. Activate and perform each skill workflow; record complete or blocked with evidence. If tools are unavailable, report the limitation, and do not claim success.'}
 if missing:
  return {'systemMessage':'Skill audit incomplete: '+', '.join(missing)+'. Do not claim that all mandatory skills executed.'}
 return {}

def activate(turn,sid):
 con=db()
 row=con.execute("SELECT * FROM skills WHERE id=? AND status='active'",(sid,)).fetchone()
 task=con.execute('SELECT required FROM turns WHERE id=?',(turn,)).fetchone()
 if not row or not task or sid not in json.loads(task['required']): raise ValueError('Not an approved, required skill for this turn')
 file=Path(row['path']); content=file.read_text(encoding='utf-8')
 con.execute('INSERT INTO execution(turn_id,skill_id,activated,completed,evidence,verification,status) VALUES(?,?,?,?,?,?,?) ON CONFLICT(turn_id,skill_id) DO UPDATE SET activated=excluded.activated,status=excluded.status',(turn,sid,now(),None,'','','activated'))
 con.commit();return f'ACTIVATED {row["name"]}\nPATH: {file}\nSKILL INSTRUCTIONS (apply them now):\n'+content

def finish(turn,sid,status,summary,verification):
 if not summary.strip():raise ValueError('Provide nonempty evidence/reason')
 if status=='completed' and not verification.strip():raise ValueError('Provide verification results or "not verifiable"')
 con=db(); prior=con.execute('SELECT activated FROM execution WHERE turn_id=? AND skill_id=?',(turn,sid)).fetchone()
 if not prior:raise ValueError('Skill must first be activated for this turn')
 con.execute('UPDATE execution SET status=?,completed=?,evidence=?,verification=? WHERE turn_id=? AND skill_id=?',(status,now(),summary[:1000],verification[:1000],turn,sid)); con.commit()
 return f'{sid}: {status} recorded (self-reported, not independently verified)'

def download_skill(c,staging):
 # Never run, import or follow any downloaded instructions here. Pin the exact commit.
 repo,relative,commit=c['repo'],c['repo_path'],c['sha']
 prefix=relative[:-len('SKILL.md')]
 tree=gh_get('repos/'+repo+'/git/trees/'+commit+'?recursive=1',10)
 files=[x for x in tree.get('tree',[]) if x.get('type')=='blob' and x['path'].startswith(prefix)]
 if not files or len(files)>150 or sum(x.get('size',0) for x in files)>2_000_000:raise ValueError('Skill exceeds safe import limits (150 files/2 MB)')
 stage=staging
 stage.mkdir(parents=True,exist_ok=True)
 for x in files:
  rel=PurePosixPath(x['path'][len(prefix):]); parts=rel.parts
  if not parts or any(p in ('..','') for p in parts):raise ValueError('Unsafe path')
  if x['path'].endswith('/') or (stage.joinpath(*parts)).is_symlink():raise ValueError('Unsafe path type')
  # Bundle text resources; don't fetch potentially huge binary assets.
  if Path(parts[-1]).suffix.lower() not in ('.md','.txt','.py','.sh','.js','.json','.toml','.yaml','.yml','.xml','.gradle','.kt','.java','.csv','.sql','.html','.css','.ps1') and parts[-1]!='SKILL.md':continue
  url='https://raw.githubusercontent.com/'+repo+'/'+commit+'/'+urllib.parse.quote(x['path'],safe='/')
  req=urllib.request.Request(url,headers={'User-Agent':'Skill-Orchestrator/0.1'})
  with urllib.request.urlopen(req,timeout=10) as r: body=r.read(250001)
  if len(body)>250000:raise ValueError('Oversized source')
  destination=stage.joinpath(*parts);destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(body)
 if not (stage/'SKILL.md').exists():raise ValueError('Missing SKILL.md after import')
 return stage

def decide(cid,action,replace_id=''):
 if action not in ('keep','replace','reject'):raise ValueError('Choose keep, replace, reject')
 con=db(); c=con.execute('SELECT * FROM candidates WHERE id=?',(cid,)).fetchone()
 if not c:raise ValueError('Candidate not found')
 if c['status']!='pending':raise ValueError('Already decided: '+c['status'])
 if action=='replace':
  existing=con.execute("SELECT * FROM skills WHERE id=? AND status='active'",(replace_id,)).fetchone()
  if not existing:raise ValueError('Must supply active --replace-id')
 if action=='reject':
  con.execute('UPDATE candidates SET status=\'rejected\' WHERE id=?',(cid,));con.commit()
  return 'Rejected '+cid+'; existing skills untouched.'
 target=STATE/'managed'/('skill-'+sha10(c['repo']+'/'+c['repo_path']+c['sha']))
 stage=STATE/'staging'/cid
 try:
  if stage.exists():shutil.rmtree(stage)
  download_skill(c,stage)
  if target.exists():
   backup=STATE/'backup'/(target.name+'-'+str(now()));backup.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(target),str(backup))
  target.parent.mkdir(parents=True,exist_ok=True);shutil.move(str(stage),str(target))
  name,desc=metadata(target/'SKILL.md'); sid='local-'+sha10(str((target/'SKILL.md').resolve()))
  con.execute('''INSERT INTO skills(id,name,path,source,repo,repo_path,sha,status,capabilities,last_scan) VALUES(?,?,?,?,?,?,?,\'active\',?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,repo=excluded.repo,repo_path=excluded.repo_path,sha=excluded.sha,status=\'active\',capabilities=excluded.capabilities,last_scan=excluded.last_scan,status='active' WHERE skills.status IN ('active','missing')''',(sid,name,str(target/'SKILL.md'),'managed',c['repo'],c['repo_path'],c['sha'],json.dumps([c['capability']]),now()))
  if action=='replace':con.execute("UPDATE skills SET status='replaced' WHERE id=?",(replace_id,))
  con.execute('UPDATE candidates SET status=? WHERE id=?',('accepted-'+action,cid));con.commit()
  return f'Installed read-only skill files as {sid}, pinned {c["sha"][:12]}. '+('Old skill is inactive in orchestrator registry, files preserved for rollback.' if action=='replace' else 'Both skills remain enabled.')+' Review downloaded instructions and scripts before executing any code.'
 except Exception:
  if stage.exists():shutil.rmtree(stage)
  raise

def status():
 con=db(); scan(con)
 return json.dumps({'skills':[dict(r) for r in con.execute('SELECT * FROM skills ORDER BY name')], 'executions':[dict(r) for r in con.execute('SELECT * FROM execution ORDER BY activated DESC LIMIT 40')], 'candidates':[dict(r) for r in con.execute('SELECT * FROM candidates ORDER BY discovered DESC LIMIT 30')], 'turns':[dict(r) for r in con.execute('SELECT * FROM turns ORDER BY started DESC LIMIT 10')]},indent=2)

def main():
 a=argparse.ArgumentParser()
 sub=a.add_subparsers(dest='cmd',required=True)
 for k in ('hook-prompt','hook-stop','status'):sub.add_parser(k)
 for k in ('activate','complete','block'):
  p=sub.add_parser(k);p.add_argument('--turn',required=True);p.add_argument('--id',required=True)
  if k!='activate':p.add_argument('--summary',required=True);p.add_argument('--verification',default='')
 p=sub.add_parser('decide');p.add_argument('--id',required=True);p.add_argument('--action',choices=['keep','replace','reject'],required=True);p.add_argument('--replace-id',default='')
 p=sub.add_parser('simulate');p.add_argument('prompt');p.add_argument('--turn',default='test-turn')
 args=a.parse_args()
 try:
  if args.cmd=='hook-prompt': print(json.dumps(prompt_hook(json.load(sys.stdin))))
  elif args.cmd=='hook-stop':print(json.dumps(stop_hook(json.load(sys.stdin))))
  elif args.cmd=='activate':print(activate(args.turn,args.id))
  elif args.cmd in ('complete','block'):print(finish(args.turn,args.id,'completed' if args.cmd=='complete' else 'blocked',args.summary,args.verification))
  elif args.cmd=='decide':print(decide(args.id,args.action,args.replace_id))
  elif args.cmd=='status':print(status())
  elif args.cmd=='simulate':print(json.dumps(prompt_hook({'turn_id':args.turn,'prompt':args.prompt}),indent=2))
 except Exception as e:
  if args.cmd.startswith('hook-'):
   print(json.dumps({'hookSpecificOutput':{'hookEventName':'UserPromptSubmit','additionalContext':'Skill orchestrator preflight failed; disclose failure rather than claiming skills were activated: '+str(e)[:250]}} if args.cmd=='hook-prompt' else {'systemMessage':'Skill orchestrator stop audit failed: '+str(e)[:250]}))
  else:print(str(e),file=sys.stderr);sys.exit(1)
if __name__=='__main__':main()