import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
PLUGIN=BASE/'plugin'/'skill-orchestrator' if (BASE/'plugin'/'skill-orchestrator').is_dir() else BASE
SERVER=PLUGIN/'server'
sys.path.insert(0, str(SERVER))
import api
core=api.core

class CrossHostAPI(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.old=(core.STATE,core.DEFAULT_HOME)
  core.STATE=Path(self.tmp.name)/'state';core.DEFAULT_HOME=Path(self.tmp.name)/'home'
  self.addCleanup(self.restore)
  skill=core.DEFAULT_HOME/'skills'/'android-developer'/'SKILL.md'
  skill.parent.mkdir(parents=True)
  skill.write_text('---\nname: android-developer\ndescription: Android APK Kotlin programming debugging\n---\nAlways test the build.\n')
 def restore(self):core.STATE,core.DEFAULT_HOME=self.old
 def test_android_multi_skill_sequence(self):
  with patch.object(core,'search_github',return_value='cached'),patch.object(core,'check_skill_updates',return_value=[]):
   first=api.prepare_task('Build an Android APK')
   second=api.prepare_task('Build an Android APK')
  self.assertNotEqual(first['task_id'],second['task_id'])
  self.assertEqual(first['bundle'],'android-apk-team')
  self.assertIn('maintenance',first['capabilities'])
  self.assertTrue(first['required_skills'])
  sid=next(s['id'] for s in first['required_skills'] if s['name']=='android-developer')
  self.assertFalse(api.audit_task(first['task_id'])['all_reported'])
  self.assertIn('Always test the build',api.activate_skill(first['task_id'],sid)['instructions'])
  self.assertFalse(api.audit_task(first['task_id'])['all_reported'])
  api.report_skill_result(first['task_id'],sid,'completed','Implemented Kotlin logic','Tests passed')
  for other in (s for s in first['required_skills'] if s['id']!=sid):
   api.activate_skill(first['task_id'],other['id'])
   api.report_skill_result(first['task_id'],other['id'],'completed','Applied specified workflow','Checks passed')
  self.assertTrue(api.audit_task(first['task_id'])['all_successful'])
  self.assertFalse(api.audit_task(second['task_id'])['all_reported'])
 def test_candidate_approval(self):
  con=core.db()
  con.execute('INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?)',('gh-test','android','user/repo','build/SKILL.md','abc','https://github.com/user/repo','','2026','pending',core.now()))
  con.commit();con.close()
  candidate=api.review_candidate('gh-test')
  self.assertIn('replace',candidate['choices'])
  with self.assertRaises(PermissionError):api.decide_candidate('gh-test','keep')
  self.assertEqual(api.review_candidate('gh-test')['candidate']['status'],'pending')
  self.assertIn('Rejected',api.decide_candidate('gh-test','reject',True)['result'])
 def test_invalid_inputs(self):
  with self.assertRaises(ValueError):api.prepare_task('')
  with self.assertRaises(ValueError):api.prepare_task('hi',task_id='../whoops')
  with self.assertRaises(ValueError):api.audit_task('missing')
 def test_tool_adapter_registration_without_sdk(self):
  # MCP SDK itself is an optional pip dependency; validate registration shape offline.
  class FakeMCP:
   def __init__(self,**kw):self.tools={}
   def tool(self):
    def add(f):self.tools[f.__name__]=f;return f
    return add
   def run(self,**kw):pass
  fake=types.ModuleType('mcp');server_pkg=types.ModuleType('mcp.server');fast=types.ModuleType('mcp.server.fastmcp');fast.FastMCP=FakeMCP
  with patch.dict(sys.modules,{'mcp':fake,'mcp.server':server_pkg,'mcp.server.fastmcp':fast}):
   spec=importlib.util.spec_from_file_location('orchestrator_mcp_test',SERVER/'mcp_server.py')
   mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
   expected={'prepare_task','activate_skill','report_skill_result','audit_task','list_skills','review_candidate','decide_candidate'}
   self.assertEqual(set(mod.mcp.tools),expected)

if __name__=='__main__':unittest.main()
