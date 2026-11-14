"""Held-out synthetic requirement changes. No model calls in smoke().
The development pilot's C01-C03 are excluded. Six methods, paired C2/D2.
"""
import copy, csv, json, time, random, os, tempfile
from pathlib import Path
from contextlib import contextmanager
from http.server import ThreadingHTTPServer
import threading
import pilot as p
import coverage_v2 as review
P,L,C=p.P,p.L,p.C
step,chk,test=p.step,p.chk,p.test

def get(id,path,keys,value=None,op='eq',status=200):
 return test(id,step('GET',path,status,checks=[chk(keys,op,value)] if keys else []))
def post(id,body,status=201,auth='alice',checks=None):
 return test(id,step('POST',C,status,auth,body,checks if checks is not None else ([chk(['comment','body'],'eq',body)] if status==201 else [])))
def delete(id,auth,status,after=404,checks=()):
 return test(id,step('DELETE',P,status,auth,checks=checks),step('GET',P,after))
OLD=[get('T01',L,['articles',0,'body'],'Hello world'),get('T02',P,['article','body'],'Hello world'),delete('T03','alice',204),delete('T04','bob',204),test('T05',step('DELETE',P,401)),post('T06','hello',401,None),post('T07','x',auth='bob'),post('T08','hello'),post('T09','',422),get('T10',L,['articles',0,'author'],'alice'),get('T11',P,['article','author'],'alice'),post('T12','123456789'),post('T13','   '),post('T14','  hi  '),post('T15','hello',checks=[chk(['comment','author'],'eq','alice')]),post('T16','hello',auth='bob',checks=[chk(['comment','author'],'eq','bob')]),get('T17',P,['article','slug'],'hello'),get('T18',L,['articles',0,'slug'],'hello')]
# Public requirements only; fault and impact annotations are not model inputs.
SPECS=[
 ('F01','Article lists include author.','Article lists omit author; article detail still includes author.','T10'),
 ('F02','Article detail has no title field.','Article detail includes title equal to "Hello"; existing fields remain.',''),
 ('F03','Fetching a deleted article returns 404.','Fetching a deleted article returns 410; successful deletion still returns 204.','T03 T04'),
 ('F04','Anonymous deletion returns 401.','Anonymous deletion returns 403 and must leave the article intact.','T05'),
 ('F05','Anonymous comments return 401.','Anonymous comments with nonempty bodies are accepted (201), with author "guest"; empty bodies are rejected (422).','T06'),
 ('F06','Both authenticated users may comment.','Only alice may comment; bob receives 403 even for a valid body. Anonymous comments remain 401.','T07 T16'),
 ('F07','Any nonempty comment length is accepted.','Comment bodies must have 1 to 8 characters inclusive; longer bodies return 422.','T12'),
 ('F08','Whitespace-only nonempty comments are accepted.','Whitespace-only comments are rejected (422); other nonempty comments retain their original text.','T13'),
 ('F09','Comment response echoes the input body exactly.','Trim leading and trailing whitespace before storing and returning a comment; reject the result if empty (422).','T13 T14'),
 ('F10','Comment response contains body and author.','Successful comment response additionally includes length equal to the number of characters in the body.',''),
 ('F11','Empty comments return 422.','Empty string comments are accepted (201); missing or non-string body still returns 422.','T09'),
 ('F12','Successful deletion returns 204 with no body.','Successful deletion returns 200 and JSON {"deleted":true}; article is removed.','T03 T04'),
]
CASES={c:{'old':old,'new':new,'unchanged':'All baseline rules and response fields remain except the explicitly changed behavior.','faults':['rule_omitted','rule_incorrect','regression_detail_body']} for c,old,new,ids in SPECS}
IMPACT={c:set(ids.split()) for c,old,new,ids in SPECS}
API=p.API+''' Additional baseline details: list/detail include slug, author and body; no title field in detail; comment response has body and author, no length. Missing/non-string comment body -> 422 (after authorization); whitespace is not trimmed and whitespace-only strings are accepted. Deletion removes article; GET detail then returns 404. Baseline DELETE for both alice and bob is 204; anonymous 401. The new requirement overrides only affected rules. JSON booleans are true/false. To test missing/non-string comment body, set json explicitly in the DSL. All listed baseline rules are active unless overridden.''' 

class Handler(p.Handler):
 def handle_api(self):
  s=self.server; c=s.case if s.new and s.fault!='rule_omitted' else ''; wrong=s.fault=='rule_incorrect'; a=self.headers.get('Authorization','').removeprefix('Token '); a=a if a in ('alice','bob') else None
  article={'slug':'hello','author':'alice','body':'Hello world'}
  if self.command=='GET' and self.path==L:
   if c=='F01':
    if wrong:article['author']='guest'
    else:article.pop('author')
   return self.reply(200,{'articles':[article] if s.exists else []})
  if self.path not in (P,C) or not s.exists:
   return self.reply((409 if wrong else 410) if c=='F03' and self.command=='GET' and self.path==P else 404)
  if self.command=='GET' and self.path==P:
   if c=='F02':article['title']='Wrong' if wrong else 'Hello'
   if s.fault=='regression_detail_body':article.pop('body')
   return self.reply(200,{'article':article})
  if self.command=='DELETE' and self.path==P:
   if not a:
    if c=='F04' and wrong:s.exists=False
    return self.reply(403 if c=='F04' else 401)
   s.exists=False
   if c=='F12':return self.reply(200,{'deleted':not wrong})
   return self.reply(204)
  if self.command=='POST' and self.path==C:
   if not a and c!='F05':return self.reply(401)
   if a=='bob' and c=='F06':return self.reply(401 if wrong else 403)
   try:body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))['comment']['body']
   except Exception:return self.reply(422)
   if not isinstance(body,str):return self.reply(422)
   if c=='F09':body=body.lstrip() if wrong else body.strip()
   if not body and c!='F11':return self.reply(422)
   if c=='F11' and wrong and not body:return self.reply(201,{'comment':{'body':'empty','author':a}})
   if c=='F07' and len(body)>(7 if wrong else 8):return self.reply(422)
   if c=='F08' and not body.strip():
    if not wrong or len(body)==1:return self.reply(422)
   result={'body':body,'author':a or ('anonymous' if wrong else 'guest')}
   if c=='F10':result['length']=len(body)+(1 if wrong else 0)
   return self.reply(201,{'comment':result})
  return self.reply(404)

@contextmanager
def server(case,new=True,fault=None):
 s=ThreadingHTTPServer(('127.0.0.1',0),Handler);s.case=case;s.new=new;s.fault=fault;s.exists=True
 t=threading.Thread(target=s.serve_forever,kwargs={'poll_interval':.01},daemon=True);t.start()
 try:yield s
 finally:s.shutdown();s.server_close();t.join()

def reference(case):
 s=copy.deepcopy(OLD); changes={}; adds=[]
 if case=='F01':changes['T10']=get('T10',L,['articles',0,'author'],op='absent')
 if case=='F02':adds=[get('R01',P,['article','title'],'Hello')]
 if case=='F03':changes={x:delete(x,a,204,410) for x,a in [('T03','alice'),('T04','bob')]}
 if case=='F04':changes['T05']=delete('T05',None,403,200)
 if case=='F05':changes['T06']=post('T06','hello',201,None,[chk(['comment','author'],'eq','guest'),chk(['comment','body'],'eq','hello')]);adds=[post('R01','',422,None)]
 if case=='F06':changes={'T07':post('T07','x',403,'bob'),'T16':post('T16','hello',403,'bob')}
 if case=='F07':changes['T12']=post('T12','123456789',422);adds=[post('R01','12345678')]
 if case=='F08':changes['T13']=post('T13','   ',422);adds=[post('R01',' ',422)]
 if case=='F09':changes={'T13':post('T13','   ',422),'T14':post('T14','  hi  ',201,checks=[chk(['comment','body'],'eq','hi')])}
 if case=='F10':adds=[post('R01','hello',checks=[chk(['comment','length'],'eq',5)])]
 if case=='F11':changes['T09']=post('T09','')
 if case=='F12':changes={x:delete(x,a,200,checks=[chk(['deleted'],'eq',True)]) for x,a in [('T03','alice'),('T04','bob')]}
 return [changes.get(x['id'],x) for x in s]+adds

# Reuse unchanged DSL and execution logic. Bind the expanded independent benchmark.
p.server=server;p.CASES=CASES;p.API=API;p.OLD=OLD;p.IMPACT=IMPACT
review.CASES=CASES;review.API=API

def evaluate(suite,case):
 correct=p.run_suite(suite,case); killed=[]
 if correct['pass']:
  for f in CASES[case]['faults']:
   if not p.run_suite(suite,case,fault=f)['pass']:killed.append(f)
 old={t['id']:t for t in OLD};actual={t['id']:t for t in suite};changed={k for k,v in old.items() if actual.get(k)!=v}
 return dict(correct_pass=correct['pass'],passed_tests=correct['passed'],total_tests=len(suite),killed=killed,new_faults_killed=len(set(killed)&{'rule_omitted','rule_incorrect'}),new_faults_total=2,regression_faults_killed=int('regression_detail_body' in killed),regression_faults_total=1,changed_existing=len(changed),unnecessary_changes=len(changed-IMPACT[case]),added_tests=len(set(actual)-set(old)),failures=correct['failures'])
review.evaluate=evaluate

def smoke():
 rows=[]
 for case in CASES:
  old=p.run_suite(OLD,case,new=False); stale=p.run_suite(OLD,case); e=evaluate(reference(case),case)
  assert old['pass'] and e['correct_pass'] and len(e['killed'])==3,(case,old,e)
  assert {x['id'] for x in stale['failures']}==IMPACT[case],(case,stale)
  rows.append(dict(case=case,old_tests=old['passed'],stale_passed=stale['passed'],reference_tests=e['total_tests'],reference_passed=e['passed_tests'],faults_killed=len(e['killed'])))
 return rows

METHODS=('A','B','C','D','C2','D2')
MODEL='gemini-3.5-flash-lite'

def base_run(case,method,ask,max_repairs=2):
 public={k:v for k,v in CASES[case].items() if k!='faults'}
 common=API+'\nRequirements: '+json.dumps(public)+'\nReturn JSON {"tests": [...]} using DSL. Preserve stable IDs for existing tests; use new IDs for additions. Do not weaken checks.'
 selected=None;suite=None
 if method=='D':
  try:
   plan=ask(common+'\nExisting tests: '+json.dumps(OLD)+'\nFirst return JSON {"update_ids":[...],"reasons":{...}} identifying existing tests that need edits, not merely related tests. New tests can be added later.')
   ids=plan['update_ids'];assert isinstance(ids,list) and all(isinstance(x,str) for x in ids),'invalid impact IDs'
   selected=set(ids);assert selected<={t['id'] for t in OLD},'unknown IDs'
  except (ValueError,KeyError,TypeError,AssertionError,AttributeError):return None,None
  allowed=[t for t in OLD if t['id'] in selected];locked=[t for t in OLD if t['id'] not in selected]
  base=common+'\nEditable tests: '+json.dumps(allowed)+'\nProtected tests (read-only): '+json.dumps(locked)+'\nReturn only updated editable tests (all selected IDs) and any added tests, never protected IDs.'
  def merge(data):
   changed=data['tests'];assert isinstance(changed,list)
   if changed:p.validate(changed)
   ids={t['id'] for t in changed};assert selected<=ids and not ids.intersection(t['id'] for t in locked),'protected or missing IDs'
   return p.validate(locked+changed)
 else:
  base=common+ ('\nRegenerate entire suite from requirements, without old tests.' if method=='A' else '\nExisting tests: '+json.dumps(OLD)+'\nUpdate complete suite directly; preserve unaffected behavior.')
  def merge(data):return p.validate(data['tests'])
 for _ in range(1+(max_repairs if method in ('C','D') else 0)):
  try:
   data=ask(base);suite=merge(data)
   if method not in ('C','D'):break
   result=p.run_suite(suite,case)
   if result['pass']:break
   base+='\nPrevious output: '+json.dumps(data)+'\nCorrect-version failures: '+json.dumps(result['failures'])+'\nRepair only legitimate issues; follow original constraints.'
  except (ValueError,KeyError,TypeError,AssertionError,AttributeError) as e:
   suite=None;base+='\nInvalid previous output: '+str(e)+'\nReturn valid JSON in required schema.'
 return suite,selected

def atomic(path,data):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(data,indent=2));tmp.replace(path)
def collect(out):
 return [json.loads(f.read_text())['metrics'] for f in sorted(Path(out).glob('F*_*.json'))]
def export(out):
 out=Path(out);rows=collect(out)
 if rows:
  with (out/'results.csv').open('w',newline='') as f:
   w=csv.DictWriter(f,fieldnames=sorted(set().union(*(r.keys() for r in rows))));w.writeheader();w.writerows(rows)
  atomic(out/'results.json',rows)
 return rows

def run_batch(client,out,case_ids,repeats=(1,),model=MODEL,max_repairs=2):
 """Checkpoint each completed trial; abort on provider error; rerun resumes missing trials.
 C2/D2 share the exact base suites; invalid base earns zero, not a fresh retry.
 """
 assert model==MODEL,'fixed model required';out=Path(out);out.mkdir(parents=True,exist_ok=True)
 manifest=dict(model=model,max_repairs=max_repairs,methods=list(METHODS),benchmark='XP-final-synthetic-v1')
 mf=out/'manifest.json'
 if mf.exists():assert json.loads(mf.read_text())==manifest,'different configuration'
 else:atomic(mf,manifest)
 for rep in repeats:
  for case in case_ids:
   assert case in CASES
   order=list(('A','B','C','D'));random.Random(f'XP:{case}:{rep}').shuffle(order)
   for method in order+['C2','D2']:
    dest=out/f'{case}_{method}_{rep}.json'
    if dest.exists():continue
    logs=[];start=time.perf_counter();selected=None;obligations=[];attempts=[];status='evaluated';parent=None
    def ask(prompt):return p.model_call(client,model,prompt,logs)
    try:
     if method in ('C2','D2'):
      parent=json.loads((out/f'{case}_{method[0]}_{rep}.json').read_text());suite=parent['suite'];selected=parent['selected']
      if not parent['metrics']['correct_pass']:status='invalid_base'
      else:
       suite,obligations,status,attempts=review.review_case(case,suite,ask,max_repairs)
       if status=='provider_or_runner_error':raise RuntimeError('Coverage review interrupted by provider or runner; resume this trial.')
     else:suite,selected=base_run(case,method,ask,max_repairs)
    except Exception as e:
     # Keep provider failures out of scientific scores. Preserve partial calls for diagnosis.
     atomic(out/'interrupted.json',dict(case=case,method=method,repeat=rep,error_type=type(e).__name__,calls=logs));export(out);raise
    elapsed=time.perf_counter()-start;tokens=sum(x['tokens'] or 0 for x in logs);calls=len(logs)
    metrics=evaluate(suite,case) if suite is not None else dict(correct_pass=False,total_tests=0,new_faults_killed=0,new_faults_total=2,regression_faults_killed=0,regression_faults_total=1,changed_existing=None,unnecessary_changes=None,added_tests=None)
    if method=='A':
     for k in ('changed_existing','unnecessary_changes','added_tests'):metrics[k]=None
    if selected is not None:
     sel=set(selected);tp=len(sel&IMPACT[case]);metrics.update(impact_precision=tp/len(sel) if sel else (1.0 if not IMPACT[case] else 0.0),impact_recall=tp/len(IMPACT[case]) if IMPACT[case] else 1.0)
    if suite is None:status='invalid_output'
    metrics.update(case=case,repeat=rep,method=method,model=model,status=status,seconds=elapsed+(parent['metrics']['seconds'] if parent else 0),tokens=tokens+(parent['metrics']['tokens'] if parent else 0),calls=calls+(parent['metrics']['calls'] if parent else 0),review_seconds=elapsed if parent else 0,review_tokens=tokens if parent else 0,review_calls=calls if parent else 0)
    atomic(dest,dict(metrics=metrics,suite=suite,selected=sorted(selected) if selected is not None else None,obligations=obligations,attempts=attempts,calls=logs));export(out);print(case,rep,method,status,flush=True)
 return export(out)
