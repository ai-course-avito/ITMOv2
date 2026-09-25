"""Run local, isolated OpenCode A/B sessions; never overwrite evidence."""
from pathlib import Path
import argparse, copy, datetime, hashlib, json, os, signal, statistics
import subprocess, tempfile, time, urllib.request
from transport import Relay

ROOT = Path(__file__).resolve().parent

def dump(path, value):
    with path.open('x') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')

def api(path, data=None):
    req = urllib.request.Request('http://127.0.0.1:11434'+path,
        data=None if data is None else json.dumps(data).encode(),
        headers={'Content-Type':'application/json'})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--stage',choices=['smoke','all','questions','bench'],default='all')
    p.add_argument('--timeout',type=int,default=600)
    args=p.parse_args()
    configs={v:json.loads((ROOT/'configs'/f'{v}.json').read_text()) for v in 'AB'}
    a,b=(copy.deepcopy(configs[v]) for v in 'AB')
    for c in (a,b): del c['agent']['local-guide']['prompt']
    assert a==b, 'Only prompt may differ'
    for v in 'AB':
        assert configs[v]['agent']['local-guide']['prompt']==(ROOT/'prompts'/f'{v}.txt').read_text()
    manifest=json.loads((ROOT/'source-manifest.json').read_text())
    def verify(directory):
        for f in manifest['files']:
            path=directory/Path(f['snapshot']).name
            assert hashlib.sha256(path.read_bytes()).hexdigest()==f['sha256'], str(path)
    verify(ROOT/'corpus')
    model=api('/api/show',{'model':'itmo-agent-local'})
    assert any(l.split()==['num_ctx','8192'] for l in model['parameters'].splitlines())
    dest=ROOT/'results'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    dest.mkdir(parents=True,exist_ok=False)
    dump(dest/'model.json',{k:model.get(k) for k in ('details','parameters','capabilities')})
    dump(dest/'versions.json', {name:subprocess.check_output(cmd,text=True).strip() for name,cmd in {
        'opencode':['opencode','--version'],'python':['python3','--version'],
        'macos':['sw_vers','-productVersion'],'ollama':['ollama','--version']}.items()})
    questions=json.loads((ROOT/'questions.json').read_text())
    plan=[(v,questions[0],f'warmup-{v}') for v in ('A' if args.stage=='smoke' else 'AB')]
    if args.stage in ('all','questions'):
        for i,q in enumerate(questions,1):
            plan.extend((v,q,f'{v}-question{i}') for v in ('AB' if i%2 else 'BA'))
    if args.stage in ('all','bench'):
        for i in range(1,4):
            plan.extend((v,questions[0],f'benchmark-{v}-{i}') for v in ('AB' if i%2 else 'BA'))
    rows=[];sessions=set()
    # Outside the source repo: no parent project config, AGENTS, gold, or reports.
    with tempfile.TemporaryDirectory(prefix='itmo-hw03-') as td, Relay() as relay:
        work=Path(td).resolve()
        for source in (ROOT/'corpus').iterdir():
            if source.is_file(): (work/source.name).write_bytes(source.read_bytes())
        dump(dest/'isolation.json',{'cwd':str(work),'files':sorted(p.name for p in work.iterdir()),
             'transport':'transparent loopback relay to http://127.0.0.1:11434/v1',
             'relay_changes_request_body':False})
        for index,(variant,question,stem) in enumerate(plan,1):
            config=copy.deepcopy(configs[variant])
            config['provider']['ollama']['options']['baseURL']=relay.url
            env={k:v for k,v in os.environ.items() if not (k.startswith('OPENCODE_') or k.endswith('_API_KEY'))}
            env.update(OPENCODE_CONFIG_CONTENT=json.dumps(config),PYTHONDONTWRITEBYTECODE='1',
                OPENCODE_DISABLE_CLAUDE_CODE='true',OPENCODE_DISABLE_PROJECT_CONFIG='true')
            user_prompt='Доступные материалы проекта в текущем каталоге: CASE.md и TRAINING_PR.diff.\n\n'+question
            cmd=['opencode','run','--pure','--dir',str(work),'--agent','local-guide',
                '--model','ollama/itmo-agent-local','--title',stem,'--format','json',user_prompt]
            dump(dest/f'{stem}.config.json',config)
            relay.stem=stem;before=len(relay.records)
            print(f'[{index}/{len(plan)}] START {stem}',flush=True)
            started=time.perf_counter()
            proc=subprocess.Popen(cmd,env=env,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
            timed_out=False
            try: stdout,stderr=proc.communicate(timeout=args.timeout)
            except subprocess.TimeoutExpired:
                timed_out=True;os.killpg(proc.pid,signal.SIGKILL);stdout,stderr=proc.communicate()
            elapsed=time.perf_counter()-started
            raw=[];invalid=0
            for line in stdout.decode(errors='replace').splitlines():
                try: raw.append(json.loads(line))
                except json.JSONDecodeError: invalid+=1
            texts=[e for e in raw if e.get('type')=='text' and e.get('part',{}).get('text','').strip()]
            tools=[e for e in raw if e.get('type')=='tool_use']
            final=texts[-1] if texts else None
            errors=[e for e in raw if e.get('type')=='error']
            kept=tools+([final] if final else [])+errors
            with (dest/f'{stem}.jsonl').open('x') as f:
                for e in kept: f.write(json.dumps(e,ensure_ascii=False)+'\n')
            with (dest/f'{stem}.stderr.log').open('xb') as f: f.write(stderr)
            ids={e['sessionID'] for e in raw if e.get('sessionID')}
            duplicate=bool(ids&sessions);sessions.update(ids)
            violations=[];reads=[]
            for e in tools:
                part=e['part'];state=part.get('state',{});inp=state.get('input',{})
                if part.get('tool') not in ('read','glob','grep'): violations.append('unexpected tool: '+str(part.get('tool')))
                for key in ('filePath','path'):
                    if inp.get(key):
                        target=Path(inp[key]);target=(work/target).resolve() if not target.is_absolute() else target.resolve()
                        if not target.is_relative_to(work): violations.append('outside corpus: '+str(target))
                if part.get('tool')=='read' and state.get('status')=='completed': reads.append(inp.get('filePath'))
            records=relay.records[before:]
            dump(dest/f'{stem}.requests.json',records)
            request_ok=bool(records) and all(r['parameters'].get('model')=='itmo-agent-local' and
                r['parameters'].get('temperature')==0.2 and
                r['parameters'].get('reasoning_effort')=='none' and
                (r['parameters'].get('max_tokens')==2048 or r['parameters'].get('max_completion_tokens')==2048) and
                not r['gold_marker_present'] for r in records)
            row={'stem':stem,'variant':variant,'question':question,'user_prompt':user_prompt,'wall_seconds':elapsed,'exit_code':proc.returncode,
                 'timed_out':timed_out,'invalid_lines':invalid,'sessionIDs':sorted(ids),'duplicate_session':duplicate,
                 'has_final_text':bool(final),'completed_reads':reads,'isolation_violations':violations,
                 'request_parameters_verified':request_ok,
                 'tools':[{'tool':e['part']['tool'],'status':e['part'].get('state',{}).get('status')} for e in tools]}
            row['valid_execution']=proc.returncode==0 and not timed_out and bool(final) and len(ids)==1 and not duplicate and invalid==0 and not violations and request_ok and not errors
            dump(dest/f'{stem}.run.json',row);rows.append(row)
            dump(dest/f'{stem}.ollama-ps.json',api('/api/ps'))
            verify(work);verify(ROOT/'corpus')
            print(f'END {stem} {elapsed:.2f}s text={bool(final)} reads={len(reads)} params={request_ok} valid={row["valid_execution"]}',flush=True)
            if not request_ok:
                print('STOP: inspect captured request parameters before further evaluation.',flush=True)
                break
    medians={}
    for v in 'AB':
        selected=[r for r in rows if r['stem'].startswith('benchmark-'+v+'-')]
        medians[v]=statistics.median(r['wall_seconds'] for r in selected) if len(selected)==3 and all(r['valid_execution'] for r in selected) else None
    dump(dest/'summary.json',{'runs':rows,'median_agent_wall_seconds_question1':medians,
        'assessment':'Execution checks are not factual grading. Review final answers against GOLD.md.'})
    print('Saved:',dest,'Medians:',medians,flush=True)
    if any(not r['valid_execution'] for r in rows): raise SystemExit(1)

if __name__=='__main__': main()
