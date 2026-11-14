"""Pilot V2: paired, additive requirement-coverage review of archived V1 D suites.
Model self-reports coverage; independent fault evaluation is never model feedback.
"""
import copy, csv, json, time
from pathlib import Path
from pilot import API, CASES, validate, run_suite, evaluate, model_call

RULES = '''Review the executable suite against the public requirement change and retained behavior.
Derive test obligations from the requirements: include positive/negative outcomes, exact boundaries and adjacent values when relevant, authorization roles, and relevant state/response checks. Do not assume that passing tests are complete. Inspect actual inputs and expected assertions, not only test names.
Keep every existing test unchanged. Add only necessary tests with fresh IDs beginning V2_. Use the DSL and executable endpoints. Never copy an existing ID. Do not use external code. If no additions are necessary, return an empty tests array.
Return one JSON object with keys obligations and tests. Each obligation has id, description, status (covered or missing), test_ids (array of IDs in the final suite), and evidence (short explanation citing actual inputs/assertions). For a missing obligation use an empty test_ids list. Include both already covered and newly covered obligations. tests contains additions only. Avoid duplicates and irrelevant checks.'''

def prompt_for(case, suite):
    public = {k:v for k,v in CASES[case].items() if k != 'faults'}
    return API + '\nPublic requirements: ' + json.dumps(public) + '\nExisting immutable tests: ' + json.dumps(suite) + '\n' + RULES

def merge_review(original, data):
    if not isinstance(data, dict): raise ValueError('Expected JSON object')
    additions=data.get('tests')
    if not isinstance(additions,list): raise ValueError('tests must be list')
    if additions: validate(additions)
    if any(not t['id'].startswith('V2_') for t in additions): raise ValueError('New IDs must begin V2_')
    merged=validate(copy.deepcopy(original)+copy.deepcopy(additions))
    obs=data.get('obligations')
    if not isinstance(obs,list) or not obs: raise ValueError('Nonempty obligations required')
    ids={t['id'] for t in merged}; oids=set(); missing=[]
    for o in obs:
        if not isinstance(o,dict) or not all(isinstance(o.get(k),str) and o[k].strip() for k in ('id','description','evidence')): raise ValueError('Invalid obligation')
        if o['id'] in oids: raise ValueError('Duplicate obligation ID')
        oids.add(o['id']); links=o.get('test_ids')
        if not isinstance(links,list) or any(not isinstance(k,str) or k not in ids for k in links): raise ValueError('Invalid obligation test IDs')
        if o.get('status')=='covered' and links: pass
        elif o.get('status')=='missing' and not links: missing.append(o['description'])
        else: raise ValueError('Invalid obligation coverage status')
    return merged, missing

def review_case(case, original, ask, max_repairs=2):
    original=copy.deepcopy(validate(original))
    if not run_suite(original,case)['pass']: raise ValueError('Archived V1 suite must pass correct version')
    prompt=prompt_for(case,original); feedback=''; attempts=[]; best=copy.deepcopy(original); accepted=[]; state='incomplete'
    for i in range(max_repairs+1):
        try:
            data=ask(prompt+feedback)
            candidate, missing=merge_review(original,data)
            result=run_suite(candidate,case)
            if not result['pass']:
                feedback='\nCorrect-version failures: '+json.dumps(result['failures'])+'\nPrevious response: '+json.dumps(data)+'\nRevise additions only; original remains immutable.'
                attempts.append({'attempt':i+1,'status':'execution_failed','failures':result['failures']}); continue
            best=candidate; accepted=data['obligations']
            attempts.append({'attempt':i+1,'status':'valid','reported_missing':missing})
            if not missing: state='model_reported_complete'; break
            feedback='\nPrevious response: '+json.dumps(data)+'\nReported missing obligations: '+json.dumps(missing)+'\nReturn a complete revised review and additions only.'
        except (ValueError,TypeError,KeyError,AttributeError,AssertionError) as exc:
            attempts.append({'attempt':i+1,'status':'invalid','error':str(exc)})
            feedback='\nInvalid response: '+str(exc)+'\nReturn valid JSON following the schema.'
        except Exception as exc:
            # Provider errors do not erase the already validated suite or earlier results.
            attempts.append({'attempt':i+1,'status':'provider_or_runner_error','error_type':type(exc).__name__}); state='provider_or_runner_error'; break
    assert best[:len(original)]==original
    return best, accepted, state, attempts

def paired_experiment(archive, client, model, out='llm_results_v2', max_repairs=2):
    out=Path(out);out.mkdir(parents=True,exist_ok=True); rows=[]
    for case, saved in archive.items():
        if saved['metrics']['model']!=model: raise ValueError('Model differs from archived V1; run a fresh paired baseline for fair comparison')
        original=saved['suite']; before=evaluate(original,case); logs=[]; start=time.perf_counter()
        suite, obligations, status, attempts=review_case(case,original,lambda p:model_call(client,model,p,logs),max_repairs)
        after=evaluate(suite,case); extra_seconds=time.perf_counter()-start
        extra_tokens=sum(x['tokens'] or 0 for x in logs); old=saved['metrics']
        for version, metrics in [('V1',before),('V2',after)]:
            is_v2=version=='V2'
            row={'case':case,'version':version,'model':model,'correct_pass':metrics['correct_pass'],'tests':metrics['total_tests'],'new_faults_killed':metrics['new_faults_killed'],'new_faults_total':metrics['new_faults_total'],'regression_faults_killed':metrics['regression_faults_killed'],'regression_faults_total':metrics['regression_faults_total'],'unnecessary_changes':metrics['unnecessary_changes'],'added_tests':metrics['added_tests'],'review_status':status if is_v2 else 'archived','seconds':old['seconds']+(extra_seconds if is_v2 else 0),'tokens':old['tokens']+(extra_tokens if is_v2 else 0),'calls':old['calls']+(len(logs) if is_v2 else 0),'review_seconds':extra_seconds if is_v2 else 0,'review_tokens':extra_tokens if is_v2 else 0,'review_calls':len(logs) if is_v2 else 0}
            rows.append(row)
        (out/f'{case}_V2.json').write_text(json.dumps({'case':case,'model':model,'v1_metrics':old,'v1_suite':original,'v2_suite':suite,'v2_metrics':after,'review_status':status,'obligations':obligations,'attempts':attempts,'calls':logs},indent=2))
        (out/'results.json').write_text(json.dumps(rows,indent=2))
        with (out/'results.csv').open('w',newline='') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
        print(case,'V2',status,'| new faults',before['new_faults_killed'],'->',after['new_faults_killed'],'| tests',len(original),'->',len(suite),flush=True)
    return rows
