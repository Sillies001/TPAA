#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys
from collections import Counter
root=Path(__file__).resolve().parents[1]; can=root/'canonical'; checks=[]
def ck(n,o,d=''): checks.append((n,bool(o),d))
def load(n): return json.loads((can/n).read_text(encoding='utf8'))
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
cat=load('P1_METRIC_CATALOG.json'); ms=cat['metrics']; mat=load('METRIC_INPUT_AUTHORITY_MATRIX.json')
c=Counter(m['delivery_milestone'] for m in ms); vk=Counter(m['value_kind'] for m in ms)
ck('IA-01-P1-INVARIANTS',len(ms)==116 and c=={'M3':84,'M2':32} and vk=={'NUMERIC':107,'STRUCTURED':9} and sum(m['p1_longitudinal_trend_eligibility'] for m in ms)==104,f'{c} {vk}')
pairs=Counter((m['metric_code'],f) for m in ms for f in m['input_fields']); binds=Counter((b['metric_code'],b['input_field']) for b in mat['bindings']); ck('IA-02-INPUT-PARITY',len(mat['bindings'])==661 and pairs==binds)
core=load('CORE_LOGICAL_MODEL.json'); dto=load('CROSS_LAYER_DTO_CONTRACTS.json'); ctx={x['name']:x for x in core['tables']['context.evaluation_context']['fields']}; ev={x['field']:x for x in dto['contracts']['EvaluationContextDTO']['fields']}; ck('IA-03-CONTEXT-DTO',set(ctx)==set(ev) and ctx['scenario_id']['nullable'])
auth=load('SCHEMA_AUTHORITY_REGISTRY.json'); aa=auth['authorities']; ck('IA-04-AUTHORITY',len(aa)==15 and len({a['domain'] for a in aa})==15 and all((can/a['artifact']).is_file() for a in aa))
vols=sorted(p for p in root.glob('05[A-J]_*.md')); ck('IA-05-DOC-SEPARATION',len(vols)==10 and all('**定义权声明：**' in p.read_text(encoding='utf8') for p in vols))
tax=load('TRAINING_EVALUATION_TAXONOMY.json'); st=load('STAGE_REGISTRY.json'); ext=load('EXTENSION_CONTRACT_REGISTRY.json'); pc=load('CAPABILITY_PHASE_REGISTRY.json'); status={x['p_code']:x['baseline_status'] for x in pc['capability_phases']}; ck('IA-06-FULL-SCALE-CONTRACTS',len(st['profiles'])==4 and set(ext['p_capability_contracts'])=={'P2','P3','P4','P5','P6'} and status['P1']=='CURRENT_BASELINE')
cov=load('R39_KNOWLEDGE_COVERAGE.json'); ck('IA-07-R39-KNOWLEDGE-COVERAGE',len(cov['entries'])==60 and cov['unresolved_count']==0)
con=root/'09_ED-2.0_合订本_只读审阅版.md'; parts=['02_Core_Baseline_CB-1.4.0.md','03_TPAA_V8.0_总体方案.md','03A_整体训练效果评估方案_TPAA_V8.0.md','04_ED-2.0_工程设计公共基线.md',*[x for p in vols for x in ([p.name,'05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md'] if p.name.startswith('05C_') else [p.name])]]
ct=con.read_text(encoding='utf8') if con.exists() else ''; ck('IA-08-CONSOLIDATED-READONLY',len(parts)==15 and '本文件只是连续阅读投影，不拥有定义权' in ct and all(ct.count(f'BEGIN READ-ONLY PROJECTION: {n}')==1 for n in parts))
lock=load('BASELINE_LOCK.json'); bad=[]
for a in lock['artifacts']:
 p=can/a['file'];
 if not p.exists() or sha(p)!=a['sha256'] or p.stat().st_size!=a['bytes']: bad.append(a['file'])
ck('IA-09-BASELINE-LOCK',lock['baseline']['core']=='CB-1.4.0' and lock['baseline']['rebaseline']=='R3.3_METRIC_DESIGN_GUIDE' and len(lock['artifacts'])==21 and not bad,str(bad))
g=load('REVIEW_GATES.json')['gates']; ck('IA-10-REVIEW-GATE-SET',len(g)==65 and len({x['id'] for x in g})==65)
over=(root/'03_TPAA_V8.0_总体方案.md').read_text(encoding='utf8'); ck('IA-11-OVERALL-EXPANSION','## 36. P / M / WS / Stage 项目语言治理' in over and all(x in over for x in ['## 17. Basic Flight','## 18. WVR','## 19. BVR','## 20. 空对面/Strike']))
method=(root/'03A_整体训练效果评估方案_TPAA_V8.0.md').read_text(encoding='utf8'); ck('IA-12-METHOD-FIDELITY',len(method.encode())>100000 and '基本飞行训练评估方案' in method and not re.search(r'\b[Pp]hase\b',method))
vis=(root/'05G_可视化_GUI设计分册.md').read_text(encoding='utf8'); ck('IA-13-VIS-FIDELITY',len(vis.encode())>90000 and 'Master Timeline' in vis and not re.search(r'\b[Pp]hase\b',vis))
fid=load('KNOWLEDGE_FIDELITY_MATRIX.json'); ck('IA-14-FIDELITY-MATRIX',len(fid['entries'])>=500 and fid['unresolved_count']==0)
manifest=root/'PACKAGE_MANIFEST.sha256'; bad=[]; listed=set()
if manifest.exists():
 for line in manifest.read_text(encoding='utf8').splitlines():
  if not line.strip(): continue
  h,rel=line.split('  ',1); listed.add(rel); p=root/rel
  if not p.is_file() or sha(p)!=h: bad.append(rel)
 actual={p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name!='PACKAGE_MANIFEST.sha256' and '__pycache__' not in p.parts}
 extra=actual-listed; miss=listed-actual
else: bad=['missing'];extra=set();miss=set()
ck('IA-15-PACKAGE-MANIFEST',not bad and not extra and not miss,f'files={len(listed)} bad={bad} extra={len(extra)} miss={len(miss)}')
plat=load('PLATFORM_COMPATIBILITY_REGISTRY.json'); ck('IA-16-PLATFORM-AUTHORITY',set(plat['mandatory_os_families'])=={'WINDOWS','LINUX'} and len(plat['certification_profiles'])>=4)
eng=(root/'04_ED-2.0_工程设计公共基线.md').read_text(encoding='utf8'); dep=(root/'05H_部署_性能_安全_治理设计分册.md').read_text(encoding='utf8'); ck('IA-17-PLATFORM-DOC-CONTRACT','## 35. Windows/Linux 跨平台运行与可移植性' in over and '## 32. 跨平台工程公共合同' in eng and '## 38. 双平台 CI、打包与发布' in dep)
trace=load('TRACEABILITY_MATRIX.json'); ck('IA-18-PLATFORM-CLOSURE',any(x.get('requirement')=='Windows/Linux cross-platform portability and logical equivalence' for x in trace['items']))
term=load('TERMINOLOGY_REGISTRY.json'); ck('IA-19-TERMINOLOGY-NAMESPACE',set(term['namespaces'])=={'P','M','WS','Stage'} and term['namespaces']['P']['codes']==[f'P{i}' for i in range(1,7)])
mile=load('DEVELOPMENT_MILESTONE_REGISTRY.json'); ws=load('ENGINEERING_WORKSTREAM_REGISTRY.json'); codes=[x['code'] for x in mile['milestones']]; wsc={x['code'] for x in ws['workstreams']}; refs={w for x in mile['milestones'] for w in x['required_workstreams']}; ck('IA-20-MILESTONE-WORKSTREAM',codes==[f'M{i}' for i in range(10)] and refs<=wsc and len(wsc)>=15)
ck('IA-21-LEGACY-RETIREMENT',not (can/'PHASE_LIFECYCLE.json').exists() and not (can/'PHASE1_METRIC_CATALOG.json').exists() and all('implementation_phase' not in m and 'phase1e_trend_eligibility' not in m for m in ms))
req={x['requirement'] for x in trace['items']}; ck('IA-22-TERMINOLOGY-CLOSURE',{'P/M/WS/Stage terminology separation','M0-M9 development milestone roadmap','WS engineering workstream registry','Legacy 1A-1G and 1C/1D/1E progress labels retired'}<=req)
app=cat.get('family_applicability_contracts',{}); ck('IA-23-METRIC-FAMILY-APPLICABILITY',app.get('P1-SNS-*',{}).get('allowed_system_types')==['RADAR'] and set(app.get('P1-PSV-*',{}).get('allowed_system_types',[]))=={'IRST','EO'} and set(app.get('P1-ESM-*',{}).get('allowed_system_types',[]))=={'RWR','ESM'} and app.get('P1-DL-*',{}).get('allowed_system_types')==['DATALINK'] and app.get('P1-FUS-*',{}).get('allowed_system_types')==['FUSION'])
guide=root/'05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md'; gt=guide.read_text(encoding='utf8') if guide.exists() else ''; gc=re.findall(r'^####\s+(P1-[A-Z]+-\d{3})\s+—',gt,re.M); ck('IA-24-METRIC-DESIGN-GUIDE',len(gt.encode())>200000 and len(gc)==116 and set(gc)=={m['metric_code'] for m in ms} and 'P1-SNS-*' in gt and 'RADAR' in gt)
for n,o,d in checks: print(('PASS' if o else 'FAIL'),n,d)
print(f'SUMMARY {sum(x[1] for x in checks)}/{len(checks)} PASS')
sys.exit(0 if all(x[1] for x in checks) else 3)
