#!/usr/bin/env python3
"""Install local Skill Orchestrator into Codex personal plugin marketplace.
Run explicitly from extracted distribution; never runs automatically.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from urllib.parse import urlsplit
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parent
PACKAGE=ROOT if (ROOT/'plugin.json').is_file() else ROOT/'plugin'/'skill-orchestrator'
START='<!-- skill-orchestrator policy v1 BEGIN -->'
END='<!-- skill-orchestrator policy v1 END -->'
POLICY='''<!-- skill-orchestrator policy v1 BEGIN -->
# Mandatory Skill Orchestrator Policy
On every task, follow the task-specific instructions injected by the installed skill-orchestrator UserPromptSubmit hook. Activate each relevant approved skill with the supplied CLI command; read and perform its SKILL.md independently. For complex work coordinate a bundle of specialized workflows, verify results, and record completion or a truthful blocked status for every activated skill. Do not confuse registry selection with skill execution. If an applicable skill is missing or a new candidate appears, ask approval: replace old skill, keep both, or reject the newcomer; never download/install/replace a skill without explicit user approval. The GitHub update/alternative check is cached seven days per capability, but applicable installed skills must be used on every turn. Do not claim successful execution when hooks/tools are unavailable. The hook is a local-Codex feature and does not by itself change ChatGPT web behavior.
<!-- skill-orchestrator policy v1 END -->'''

def write_json(path,obj):
 path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')

def install(home,dry_run=False,global_policy=True,mcp_url="",on_conflict='ask'):
 home=Path(home).expanduser().resolve()
 plugin_dir=home/'.codex'/'plugins'/'skill-orchestrator'
 marketplace=home/'.agents'/'plugins'/'marketplace.json'
 policy_path=home/'.codex'/'AGENTS.md'
 print('Source:',PACKAGE,'\nPlugin destination:',plugin_dir,'\nMarketplace:',marketplace)
 if global_policy:print('Global instructions:',policy_path)
 if mcp_url:
  address=urlsplit(mcp_url)
  if address.scheme!='https' or not address.netloc or address.username or address.password or address.fragment or not address.path.endswith('/mcp'):
   raise ValueError('MCP URL must be a clean https://.../mcp endpoint. Never put credentials in the URL.')
  print('Remote MCP endpoint:',mcp_url)
 if on_conflict not in ('ask','replace','keep-both','deny'):
  raise ValueError('Invalid on-conflict option')
 already_present=plugin_dir.exists()
 if already_present and on_conflict=='ask' and not dry_run:
  if not sys.stdin.isatty():
   raise RuntimeError('Existing installation detected. Specify --on-conflict replace, keep-both, or deny explicitly.')
  while True:
   selection=input('Existing Skill Orchestrator found. [r]eplace / [k]eep both / [d]eny? ').strip().lower()
   if selection in ('r','replace','k','keep','keep-both','d','deny'):
    on_conflict={'r':'replace','k':'keep-both','keep':'keep-both','d':'deny'}.get(selection,selection)
    break
 if already_present and on_conflict=='deny':
  print('Existing plugin preserved; new version rejected. No changes made.');return
 entry_name='skill-orchestrator'
 if already_present and on_conflict=='keep-both':
  entry_name='skill-orchestrator-alt-' + datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')
  plugin_dir=home/'.codex'/'plugins'/entry_name
 if dry_run:
  print('Dry run: no files changed. Existing plugin:',already_present,'collision decision:',on_conflict)
  return
 if not PACKAGE.is_dir():raise RuntimeError('Distribution plugin directory missing')
 if already_present and on_conflict=='replace':
  backup=plugin_dir.parent/('skill-orchestrator.backup-'+datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S'))
  shutil.move(str(plugin_dir),str(backup))
  print('Previous plugin backed up:',backup)
 shutil.copytree(PACKAGE,plugin_dir)
 if entry_name!='skill-orchestrator':
  for manifest in (plugin_dir/'plugin.json',plugin_dir/'.codex-plugin'/'plugin.json'):
   if manifest.is_file():
    data=json.loads(manifest.read_text(encoding='utf-8'))
    data['name']=entry_name
    write_json(manifest,data)

 if mcp_url:
  write_json(plugin_dir/'mcp.json', {'$schema':'https://agent-plugins.org/schemas/1.0.0/mcp.schema.json',
   'mcpServers':{'skill-orchestrator':{'type':'streamable-http','url':mcp_url}}})
 # Absolute interpreter and hook file paths work for Windows desktop installations.
 # This is a local installation: user must review/trust plugin hooks in Codex UI.
 def command_for(name):
  args=[str(Path(sys.executable).resolve()),str((plugin_dir/'hooks'/name).resolve())]
  return subprocess.list2cmdline(args) if os.name=='nt' else ' '.join(__import__('shlex').quote(x) for x in args)
 hooks={'hooks':{'UserPromptSubmit':[{'hooks':[{'type':'command','command':command_for('prompt.py'),'statusMessage':'Selecting task skills'}]}],
 'Stop':[{'hooks':[{'type':'command','command':command_for('stop.py'),'statusMessage':'Verifying task skill records'}]}]}}
 write_json(plugin_dir/'hooks'/'hooks.json',hooks)
 if marketplace.exists():
  try: catalog=json.loads(marketplace.read_text(encoding='utf-8'))
  except json.JSONDecodeError as e:raise RuntimeError('Marketplace JSON invalid, refusing to overwrite') from e
 else:catalog={'name':'personal','interface':{'displayName':'Personal Plugins'},'plugins':[]}
 if not isinstance(catalog.get('plugins'),list):raise RuntimeError('Malformed marketplace; refusing to overwrite')
 entry={'name':entry_name,'source':{'source':'local','path':'./.codex/plugins/'+entry_name},'policy':{'installation':'AVAILABLE','authentication':'ON_INSTALL'},'category':'Productivity'}
 catalog['plugins']=[x for x in catalog['plugins'] if x.get('name')!=entry_name]+[entry]
 write_json(marketplace,catalog)
 if global_policy:
  old=policy_path.read_text(encoding='utf-8') if policy_path.exists() else ''
  if START in old and END in old:
   old=old[:old.index(START)]+old[old.index(END)+len(END):]
  policy_path.parent.mkdir(parents=True,exist_ok=True)
  policy_path.write_text(old.rstrip()+'\n\n'+POLICY+'\n',encoding='utf-8')
 print('\nInstalled local plugin files and marketplace registration. Restart Codex desktop, install from Personal Plugins, and explicitly review/trust the hooks. Then test with:')
 print(subprocess.list2cmdline([sys.executable,str(plugin_dir/'scripts'/'orchestrator.py'),'simulate','Build an Android APK']))
 print('ChatGPT: independently connect the running, authenticated HTTPS MCP endpoint in Plugins, then enable/invoke it in Work. This local installer cannot configure your ChatGPT account.')
 print('Important: hooks are host/trust-dependent. Activation tracking is not independent proof of actual work.')

if __name__=='__main__':
 p=argparse.ArgumentParser()
 p.add_argument('--home',help='User home directory (defaults to the current user)')
 p.add_argument('--dry-run',action='store_true')
 p.add_argument('--no-global-policy',action='store_true')
 p.add_argument('--on-conflict',choices=['ask','replace','keep-both','deny'],default='ask',help='Never silently replace existing plugin')
 p.add_argument('--mcp-url',default='',help='Optional authenticated HTTPS /mcp endpoint to link into portable plugin')
 a=p.parse_args();install(Path(a.home) if a.home else Path.home(),a.dry_run,not a.no_global_policy,a.mcp_url,a.on_conflict)
