"""XP-AcceptanceAI: reproducible API acceptance-test maintenance pilot.
Synthetic requirement changes on a standalone Conduit-inspired HTTP service.
No model calls are made by smoke(). Python 3.10+; standard library only for smoke.
"""
import argparse, copy, csv, json, os, time, threading, urllib.request, urllib.error
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from contextlib import contextmanager

CASES = {
 'C01': {'old':'Article list items include the full body.', 'new':'Article list items omit body; single-article responses still include body.', 'unchanged':'Article detail returns body; authenticated article authors can delete; unauthenticated comments are rejected; valid comments can be added.', 'faults':['list_body_leak','detail_body_missing','comment_auth_bypass']},
 'C02': {'old':'Any authenticated user can delete an article.', 'new':'Only the article author can delete it; other authenticated users receive 403.', 'unchanged':'Unauthenticated deletion is rejected; author deletion works; article list and detail include body; comments require authentication.', 'faults':['delete_any_user','delete_author_denied','comment_auth_bypass']},
 'C03': {'old':'Authenticated users can post comments with any nonempty body.', 'new':'Authenticated users can post comments with at least 3 characters; shorter comments receive 422.', 'unchanged':'A 3-character comment is accepted; comments require authentication; article detail and list include body; author deletion works.', 'faults':['comment_short_allowed','comment_boundary_wrong','detail_body_missing']},
}
API = '''Baseline business rules (the new requirement overrides the relevant rule): both article list and detail include body; any authenticated user may delete an article; anonymous deletion returns 401; successful deletion removes the article; only authenticated users may comment; empty comments are rejected, any nonempty string accepted; comment response echoes text and author. Fresh state per test: article slug hello, author alice, body Hello world. Tokens alice and bob; use auth field as token or omit for anonymous. GET /api/articles -> 200 {articles:[{slug,author,body?}]}; GET /api/articles/hello -> 200 {article:{slug,author,body}} or 404. DELETE /api/articles/hello -> 204, or 401 anonymous, 403 forbidden, 404 missing. POST /api/articles/hello/comments with JSON {comment:{body: string}} -> 201 {comment:{body,author}}, 401 anonymous, 422 invalid. Test DSL: {id, steps:[{method,path,auth?,json?,expect:{status, checks:[{path:[string or integer,...],op:"eq"|"absent"|"exists",value?}]}}]}. Checks navigate response JSON; status always required. No arbitrary code or external URLs. Each test has fresh seeded state; multiple steps in a test share state. IDs stable for existing tests.'''

def step(method,path,status,auth=None,body=None,checks=()):
 d={'method':method,'path':path,'expect':{'status':status,'checks':list(checks)}}
 if auth: d['auth']=auth
 if body is not None: d['json']={'comment':{'body':body}}
 return d

def chk(path,op,value=None):
 d={'path':path,'op':op}
 if op=='eq':d['value']=value
 return d

def test(id,*steps):return {'id':id,'steps':list(steps)}
P='/api/articles/hello'; L='/api/articles'; C=P+'/comments'
OLD=[test('T01',step('GET',L,200,checks=[chk(['articles',0,'body'],'eq','Hello world')])),
 test('T02',step('GET',P,200,checks=[chk(['article','body'],'eq','Hello world')])),
 test('T03',step('DELETE',P,204,'alice'),step('GET',P,404)),
 test('T04',step('DELETE',P,204,'bob'),step('GET',P,404)),
 test('T05',step('DELETE',P,401)),
 test('T06',step('POST',C,401,body='hello')),
 test('T07',step('POST',C,201,'bob','x',[chk(['comment','body'],'eq','x')])),
 test('T08',step('POST',C,201,'alice','hello',[chk(['comment','body'],'eq','hello')])),
 test('T09',step('POST',C,422,'alice',''))]
# Reference oracle is separately specified, never passed to model.
IMPACT={'C01':{'T01'},'C02':{'T04'},'C03':{'T07'}}

def reference(case):
 s=copy.deepcopy(OLD)
 if case=='C01':s[0]=test('T01',step('GET',L,200,checks=[chk(['articles',0,'body'],'absent'),chk(['articles',0,'slug'],'eq','hello')]))
 if case=='C02':s[3]=test('T04',step('DELETE',P,403,'bob'),step('GET',P,200,checks=[chk(['article','slug'],'eq','hello')]))
 if case=='C03':
  s[6]=test('T07',step('POST',C,422,'bob','x'))
  s.append(test('T10',step('POST',C,201,'bob','abc',[chk(['comment','body'],'eq','abc')])))
  s.append(test('T11',step('POST',C,422,'bob','ab')))
 return s

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):self.handle_api()
 def do_DELETE(self):self.handle_api()
 def do_POST(self):self.handle_api()
 def reply(self,status,payload=None):
  b=json.dumps(payload or {}).encode() if status!=204 else b''
  self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
 def handle_api(self):
  s=self.server; case=s.case; new=s.new; fault=s.fault; auth=self.headers.get('Authorization','').removeprefix('Token ')
  auth=auth if auth in ('alice','bob') else None
  article={'slug':'hello','author':'alice','body':'Hello world'}
  if self.command=='GET' and self.path==L:
   if new and case=='C01' and fault!='list_body_leak':article.pop('body')
   return self.reply(200,{'articles':[article] if s.exists else []})
  if self.path not in (P,C) or not s.exists:return self.reply(404)
  if self.command=='GET' and self.path==P:
   if fault=='detail_body_missing':article.pop('body')
   return self.reply(200,{'article':article})
  if self.command=='DELETE' and self.path==P:
   if not auth:return self.reply(401)
   if new and case=='C02' and auth!='alice' and fault!='delete_any_user':return self.reply(403)
   if fault=='delete_author_denied' and auth=='alice':return self.reply(403)
   s.exists=False;return self.reply(204)
  if self.command=='POST' and self.path==C:
   if not auth and fault!='comment_auth_bypass':return self.reply(401)
   try:body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))['comment']['body']
   except Exception:return self.reply(422)
   minimum=3 if new and case=='C03' else 1
   if fault=='comment_short_allowed':minimum=1
   if fault=='comment_boundary_wrong':minimum=4
   if not isinstance(body,str) or len(body)<minimum:return self.reply(422)
   return self.reply(201,{'comment':{'body':body,'author':auth or 'anonymous'}})
  return self.reply(404)

@contextmanager
def server(case,new=True,fault=None):
 s=ThreadingHTTPServer(('127.0.0.1',0),Handler);s.case=case;s.new=new;s.fault=fault;s.exists=True
 t=threading.Thread(target=s.serve_forever,kwargs={'poll_interval':0.01},daemon=True);t.start()
 try:yield s
 finally:s.shutdown();s.server_close();t.join()

def validate(suite):
 if not isinstance(suite,list) or not 1<=len(suite)<=30:raise ValueError('suite must contain 1-30 tests')
 ids=set()
 for t in suite:
  if not isinstance(t,dict) or not isinstance(t.get('id'),str) or not t['id'] or t['id'] in ids:raise ValueError('unique test IDs required')
  ids.add(t['id'])
  if not isinstance(t.get('steps'),list) or not 1<=len(t['steps'])<=8:raise ValueError('1-8 steps required')
  for x in t['steps']:
   if x.get('method') not in ('GET','POST','DELETE') or x.get('path') not in (P,L,C):raise ValueError('invalid method/path')
   if x.get('auth') not in (None,'alice','bob'):raise ValueError('invalid auth')
   e=x.get('expect',{});status=e.get('status')
   if type(status)!=int or not 100<=status<=599:raise ValueError('expected status required')
   if not isinstance(e.get('checks',[]),list):raise ValueError('checks must be list')
   for c in e.get('checks',[]):
    if not isinstance(c.get('path'),list) or not c['path'] or any(type(k) not in (str,int) for k in c['path']) or c.get('op') not in ('eq','exists','absent') or (c.get('op')=='eq' and 'value' not in c):raise ValueError('invalid check')
 return suite

def run_suite(suite,case,new=True,fault=None):
 validate(suite); failures=[]; passed=0
 with server(case,new,fault) as s:
  for t in suite:
   s.exists=True
   for i,x in enumerate(t['steps']):
    req=urllib.request.Request(f'http://127.0.0.1:{s.server_port}'+x['path'],method=x['method'],data=json.dumps(x['json']).encode() if 'json'in x else None,headers={'Content-Type':'application/json',**({'Authorization':'Token '+x['auth']} if x.get('auth') else {})})
    try:
     try:r=urllib.request.urlopen(req,timeout=3)
     except urllib.error.HTTPError as e:r=e
     with r:status=r.code;b=r.read();data=json.loads(b) if b else {}
     exp=x['expect']; problems=[]
     if status!=exp['status']:problems.append(f'status expected {exp["status"]}, got {status}')
     for c in exp.get('checks',[]):
      v=data;exists=True
      try:
       for k in c['path']:v=v[k]
      except (KeyError,IndexError,TypeError):exists=False
      if not ((c['op']=='absent' and not exists) or (c['op']=='exists' and exists) or (c['op']=='eq' and exists and v==c['value'])):problems.append(f'check {c} failed (actual={v if exists else "MISSING"})')
     if problems:failures.append({'id':t['id'],'step':i,'errors':problems});break
    except Exception as e:raise RuntimeError(f'Infrastructure/runner error in {t["id"]}: {e}') from e
   else:passed+=1
 return {'passed':passed,'total':len(suite),'failures':failures,'pass':not failures}

def evaluate(suite,case):
 correct=run_suite(suite,case); faults=CASES[case]['faults']; killed=[]
 # Invalid suites receive zero credit; never count a preexisting failure as a fault detection.
 if correct['pass']:
  for f in faults:
   if not run_suite(suite,case,fault=f)['pass']:killed.append(f)
 new_faults=set(faults[:2] if case=='C03' else faults[:1]); regression_faults=set(faults)-new_faults
 old={t['id']:t for t in OLD}; actual={t['id']:t for t in suite}; changed={k for k,v in old.items() if actual.get(k)!=v}; expected=IMPACT[case]
 return {'correct_pass':correct['pass'],'passed_tests':correct['passed'],'total_tests':len(suite),'killed':killed,'new_faults_killed':len(new_faults.intersection(killed)),'new_faults_total':len(new_faults),'regression_faults_killed':len(regression_faults.intersection(killed)),'regression_faults_total':len(regression_faults),'changed_existing':len(changed),'unnecessary_changes':len(changed-expected),'added_tests':len(set(actual)-set(old)),'failures':correct['failures']}

def smoke(out):
 rows=[]
 for case in CASES:
  before=run_suite(OLD,case,new=False);assert before['pass'],before
  stale=run_suite(OLD,case);assert not stale['pass'],stale
  ref=reference(case);e=evaluate(ref,case);assert e['correct_pass'] and len(e['killed'])==3,e
  rows.append({'case':case,'old_on_old':before['passed'],'old_on_new':stale['passed'],'reference_on_new':e['passed_tests'],'reference_total':e['total_tests'],'reference_faults_killed':len(e['killed']),'faults':e['killed']})
 Path(out).mkdir(parents=True,exist_ok=True);Path(out,'smoke.json').write_text(json.dumps(rows,indent=2));print(json.dumps(rows,indent=2));return rows

# Actual LLM experiment. Model receives public requirements and API contract only,
# not reference tests, impact labels, fault names or mutant execution results.
def model_call(client,model,prompt,logs):
 start=time.perf_counter();r=client.chat.completions.create(model=model,messages=[{'role':'system','content':'You maintain executable API acceptance tests. Return a JSON object only, no Markdown.'},{'role':'user','content':prompt}],response_format={'type':'json_object'})
 raw=r.choices[0].message.content;u=r.usage
 logs.append({'prompt':prompt,'raw':raw,'seconds':time.perf_counter()-start,'tokens':getattr(u,'total_tokens',None),'model':r.model});return json.loads(raw)

def experiment(out,model,repeats=1,repairs=2,client=None):
 # Only client configuration changed for publication; experiment logic is unchanged.
 if client is None:
  from openai import OpenAI
  key=os.environ.get('GEMINI_API_KEY')
  if not key:raise RuntimeError('Set GEMINI_API_KEY before running the LLM experiment.')
  client=OpenAI(api_key=key,base_url='https://generativelanguage.googleapis.com/v1beta/openai/',max_retries=0,timeout=120)
 out=Path(out);out.mkdir(parents=True,exist_ok=True);rows=[]
 for case,c in CASES.items():
  public={k:v for k,v in c.items() if k!='faults'}; common=API+'\nRequirements: '+json.dumps(public)+'\nReturn JSON {"tests": [...]} using DSL. Preserve stable IDs for existing tests; use new IDs for additions. Do not weaken checks.'
  for rep in range(repeats):
   for method in ('A','B','C','D'):
    logs=[];start=time.perf_counter();selected=None;row={'case':case,'repeat':rep+1,'method':method,'model':model};suite=None
    try:
     if method=='D':
      p=common+'\nExisting tests: '+json.dumps(OLD)+'\nFirst return JSON {"update_ids":[...],"reasons":{...}} identifying existing tests that need edits, not merely related tests. New tests can be added later.'
      plan=model_call(client,model,p,logs);selected=set(plan['update_ids']);assert selected<=set(t['id'] for t in OLD),'unknown IDs'
      allowed=[t for t in OLD if t['id'] in selected];locked=[t for t in OLD if t['id'] not in selected];base=common+'\nEditable tests: '+json.dumps(allowed)+'\nProtected tests (read-only): '+json.dumps(locked)+'\nReturn only updated editable tests (all selected IDs) and any added tests, never protected IDs.'
      def merge(data):
       changed=data['tests'];
       if changed:validate(changed)
       elif changed!=[]:raise ValueError('tests must be list')
       ids={t['id'] for t in changed};assert selected<=ids and not ids.intersection(t['id'] for t in locked),'protected or missing IDs';return validate(locked+changed)
      # An empty patch is legal; evaluation detects missed changes.
     else:
      base=common+ ('\nRegenerate entire suite from requirements, without old tests.' if method=='A' else '\nExisting tests: '+json.dumps(OLD)+'\nUpdate complete suite directly; preserve unaffected behavior.')
      def merge(data):return validate(data['tests'])
     for attempt in range((repairs if method in ('C','D') else 0)+1):
      try:
       data=model_call(client,model,base,logs);suite=merge(data)
       if method not in ('C','D'):break
       result=run_suite(suite,case)
       if result['pass']:break
       base+='\nPrevious output: '+json.dumps(data)+'\nCorrect-version failures: '+json.dumps(result['failures'])+'\nRepair only legitimate issues; follow original constraints.'
      except (ValueError,KeyError,TypeError,AssertionError) as e:
       suite=None;base+='\nInvalid previous output: '+str(e)+'\nReturn valid JSON in required schema.'
     if suite is None:raise ValueError('No valid test suite')
     row.update(evaluate(suite,case));row['status']='evaluated'
     if method=='A':
      for k in ('changed_existing','unnecessary_changes','added_tests'):row[k]=None  # IDs not comparable for fresh regeneration
     if selected is not None:
      tp=len(selected&IMPACT[case]);row.update(impact_precision=tp/len(selected) if selected else 0,impact_recall=tp/len(IMPACT[case]))
    except Exception as e:row.update(status='error',error=str(e),correct_pass=False,new_faults_killed=0,regression_faults_killed=0)
    row.update(seconds=time.perf_counter()-start,tokens=sum(l['tokens'] or 0 for l in logs),calls=len(logs));rows.append(row)
    (out/f'{case}_{method}_{rep+1}.json').write_text(json.dumps({'metrics':row,'suite':suite,'calls':logs},indent=2));print(case,method,rep+1,row['status'])
    (out/'results.json').write_text(json.dumps(rows,indent=2))
 fields=sorted(set().union(*(r.keys() for r in rows)))
 with (out/'results.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
 return rows

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['smoke','llm']);p.add_argument('--out',default='results');p.add_argument('--model',default=os.getenv('XP_MODEL','gemini-3.5-flash-lite'));p.add_argument('--repeats',type=int,default=1);p.add_argument('--repairs',type=int,default=2);a=p.parse_args();smoke(a.out) if a.mode=='smoke' else experiment(a.out,a.model,a.repeats,a.repairs)
