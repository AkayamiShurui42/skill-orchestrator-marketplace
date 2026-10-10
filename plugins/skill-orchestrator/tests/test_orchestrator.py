import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BASE=Path(__file__).resolve().parents[1]
PLUGIN=BASE/'plugin'/'skill-orchestrator' if (BASE/'plugin'/'skill-orchestrator').is_dir() else BASE
MODULE=PLUGIN/'scripts'/'orchestrator.py'
spec=importlib.util.spec_from_file_location('skill_orchestrator', MODULE)
o=importlib.util.module_from_spec(spec);spec.loader.exec_module(o)

class TestOrchestration(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name);self.old=(o.STATE,o.DEFAULT_HOME)
  o.STATE=self.root/'state';o.DEFAULT_HOME=self.root/'home'
  self.addCleanup(self.restore)
 def restore(self):o.STATE,o.DEFAULT_HOME=self.old
 def write_skill(self,name,description):
  p=o.DEFAULT_HOME/'skills'/name/'SKILL.md';p.parent.mkdir(parents=True,exist_ok=True)
  p.write_text(f'---\nname: {name}\ndescription: {description}\n---\nFollow actual workflow.\n',encoding='utf-8');return p
 def test_apk_bundle(self):
  caps,bundle=o.classify('Build an APK in Kotlin')
  self.assertEqual(bundle,'android-apk-team')
  self.assertTrue(set(o.BUNDLES[bundle])<=set(caps))
 def test_registry_and_activation_each_turn(self):
  self.write_skill('android-builder','Android APK Gradle builder')
  with patch.object(o,'search_github',return_value='cached'):
   for tid in ('t1','t2'):
    response=o.prompt_hook({'prompt':'Build APK','turn_id':tid})
    self.assertIn('ACTIVATE',response['hookSpecificOutput']['additionalContext'])
  con=o.db();row=con.execute("SELECT id FROM skills WHERE name='android-builder'").fetchone();sid=row['id']
  self.assertIn('Follow actual workflow',o.activate('t1',sid))
  self.assertEqual(o.stop_hook({'turn_id':'t1'})['decision'],'block')
  self.assertEqual(o.finish('t1',sid,'completed','Built code','Tests passed'),f'{sid}: completed recorded (self-reported, not independently verified)')
  # Activating one turn does not activate the next.
  self.assertIn('block',o.stop_hook({'turn_id':'t2'})['decision'])
 def test_seven_day_cache(self):
  con=o.db();n=o.now()
  con.execute('INSERT INTO discovery VALUES(?,?,?)',('programming',n,'verified'));con.commit()
  self.assertEqual(o.search_github(con,'programming'),'cached')
  con.execute('UPDATE discovery SET last_success=?',(n-o.WEEK-1,));con.commit()
  with patch.object(o,'gh_get',side_effect=OSError('offline')):
   result=o.search_github(con,'programming')
  self.assertIn('unavailable',result)
  self.assertEqual(con.execute('SELECT last_success FROM discovery').fetchone()['last_success'],n-o.WEEK-1)
 def test_decisions_reject_no_auto_install(self):
  con=o.db();con.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?)",('gh-abc','programming','owner/repo','my/SKILL.md','sha','https://github.com/owner/repo','','2026','pending',o.now()));con.commit()
  out=o.decide('gh-abc','reject')
  self.assertIn('Rejected',out)
  self.assertFalse((o.STATE/'managed').exists())

 def test_keep_both_and_replace(self):
  con=o.db()
  # An installed local skill stays active after keep-both.
  path=self.write_skill('build-helper','Android APK building')
  o.scan(con)
  old=con.execute("SELECT id FROM skills WHERE name='build-helper'").fetchone()['id']
  def seed(cid,sha):
   con.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?)",(cid,'android','owner/repo','skills/build/SKILL.md',sha,'https://github.com/owner/repo','','2026','pending',o.now()));con.commit()
  def mock_download(c,staging):
   staging.mkdir(parents=True,exist_ok=True)
   (staging/'SKILL.md').write_text('---\nname: newcomer\ndescription: Android APK coding\n---\nThis skill is newly imported.\n')
  with patch.object(o,'download_skill',side_effect=mock_download):
   seed('gh-v1','commit1')
   self.assertIn('Both skills',o.decide('gh-v1','keep'))
   self.assertEqual(con.execute('SELECT status FROM skills WHERE id=?',(old,)).fetchone()['status'],'active')
   seed('gh-v2','commit2')
   self.assertIn('inactive',o.decide('gh-v2','replace',old))
   self.assertEqual(con.execute('SELECT status FROM skills WHERE id=?',(old,)).fetchone()['status'],'replaced')
   # New versions live in distinct directories; the old newly approved version was not deleted.
   self.assertEqual(len(list((o.STATE/'managed').glob('*/SKILL.md'))),2)
 def test_managed_skill_update_check(self):
  con=o.db()
  skill={'id':'s1','name':'test','repo':'owner/repo','repo_path':'skills/test/SKILL.md','sha':'oldsha','capabilities':json.dumps(['android'])}
  def mock_git(url,timeout=4):
   return {'default_branch':'main','updated_at':'2026-10-01'} if url=='repos/owner/repo' else {'sha':'newsha'}
  with patch.object(o,'gh_get',side_effect=mock_git) as gh:
   result=o.check_skill_updates(con,[skill]);self.assertIn('newer commit',result[0])
   self.assertTrue(con.execute('SELECT 1 FROM candidates WHERE sha=?',('newsha',)).fetchone())
   o.check_skill_updates(con,[skill]);self.assertEqual(gh.call_count,2)

 def test_stop_no_infinite_loop(self):
  self.write_skill('debugger','debugging bug logcat crashes')
  with patch.object(o,'search_github',return_value='cached'):o.prompt_hook({'prompt':'Debug the crash','turn_id':'p'})
  self.assertEqual(o.stop_hook({'turn_id':'p'})['decision'],'block')
  self.assertIn('incomplete',o.stop_hook({'turn_id':'p'})['systemMessage'])

if __name__=='__main__':unittest.main()
