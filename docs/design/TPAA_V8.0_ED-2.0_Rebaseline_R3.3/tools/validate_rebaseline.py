#!/usr/bin/env python3
from pathlib import Path
import json,re,hashlib,sys
from collections import Counter
root=Path(__file__).resolve().parents[1]; can=root/'canonical'; res=[]
def ck(i,ok,detail=''): res.append((i,bool(ok),detail))
def load(n): return json.loads((can/n).read_text(encoding='utf-8'))
cat=load('P1_METRIC_CATALOG.json'); ms=cat['metrics']; mat=load('METRIC_INPUT_AUTHORITY_MATRIX.json')
core=load('CORE_LOGICAL_MODEL.json'); stage=load('STAGE_REGISTRY.json'); dto=load('CROSS_LAYER_DTO_CONTRACTS.json')
auth=load('SCHEMA_AUTHORITY_REGISTRY.json'); rules=load('CORE_RULES.json'); tax=load('TRAINING_EVALUATION_TAXONOMY.json')
world=load('WORLD_CAPABILITY_REGISTRY.json'); ext=load('EXTENSION_CONTRACT_REGISTRY.json'); mfam=load('EXTENSION_METRIC_FAMILY_REGISTRY.json')
pcap=load('CAPABILITY_PHASE_REGISTRY.json'); prov=load('SOURCE_PROVENANCE.json'); plat=load('PLATFORM_COMPATIBILITY_REGISTRY.json')
term=load('TERMINOLOGY_REGISTRY.json'); mile=load('DEVELOPMENT_MILESTONE_REGISTRY.json'); ws=load('ENGINEERING_WORKSTREAM_REGISTRY.json')
rulemap={r['id']:r for r in rules['rules']}
# Authority
au=auth.get('authorities',[]); domains=[a['domain'] for a in au]; arts=[a['artifact'] for a in au]
ck('V-AUTH-001',len(au)==15 and len(domains)==len(set(domains)) and len(arts)==len(set(arts)) and all((can/a).is_file() for a in arts),f'domains={len(domains)} artifacts={len(arts)}')
# P1 executable invariants
ck('V-METRIC-001',len(ms)==116,str(len(ms)))
ck('V-METRIC-002',len({m['metric_code'] for m in ms})==116)
ck('V-METRIC-003',len({(m['semantic_id'],m['semantic_version']) for m in ms})==116)
c=Counter(m['delivery_milestone'] for m in ms); ck('V-METRIC-004',c=={'M3':84,'M2':32},str(c))
b=Counter(m['delivery_batch'] for m in ms); ck('V-METRIC-005',b=={'P1_REMAINDER_84':84,'P1_FOUNDATION_32':32},str(b))
c=Counter(m['value_kind'] for m in ms); ck('V-METRIC-006',c=={'NUMERIC':107,'STRUCTURED':9},str(c))
trend=[m for m in ms if m['p1_longitudinal_trend_eligibility']]; ck('V-METRIC-007',len(trend)==104,str(len(trend)))
ck('V-INPUT-001',len(mat['bindings'])==661,str(len(mat['bindings'])))
pairs=Counter((m['metric_code'],f) for m in ms for f in m['input_fields']); binds=Counter((x['metric_code'],x['input_field']) for x in mat['bindings'])
ck('V-INPUT-002',pairs==binds,f'catalog={sum(pairs.values())} matrix={sum(binds.values())}')
# Stage
expected={'BASIC_FLIGHT_V1','WVR_ENGAGEMENT_V1','BVR_KILL_CHAIN_V1','STRIKE_MISSION_V1'}
ck('V-STAGE-001',set(stage['profiles'])==expected,str(sorted(stage['profiles'])))
ck('V-STAGE-002','Stage is exclusively training/Episode process vocabulary' in stage['governance']['authority'])
strike_expected=['MISSION_SETUP','ROUTE_TASK_EXECUTION','TARGET_INFORMATION_AVAILABLE','TARGET_ASSOCIATION','DESIGNATION_TRACK','TRAINING_ATTACK_EVENT','RANGE_SIM_ADJUDICATION','POST_EVENT_TASK_TRANSITION','RECOVERY']
strike=stage['profiles']['STRIKE_MISSION_V1']['ordered_stages']; ck('V-STAGE-003',strike==strike_expected,str(strike))
# Context DTO
ck('V-CTX-001','context.evaluation_context' in core['tables'])
ctx={x['name']:x for x in core['tables']['context.evaluation_context']['fields']}; ck('V-CTX-002',ctx['scenario_id']['nullable'] and ctx['scenario_version']['nullable'] and ctx['assessment_profile_id']['nullable'])
ev={x['field']:x for x in dto['contracts']['EvaluationContextDTO']['fields']}; ck('V-DTO-001',set(ev)==set(ctx),f'dto={len(ev)} db={len(ctx)}')
ck('V-DTO-002',len(dto['contracts']['ContextArtifactRefDTO']['fields'])==8)
mcfields={x['field'] for x in dto['contracts']['MetricCatalogEntryDTO']['fields']}
ck('V-DTO-003',{'delivery_milestone','delivery_batch','p1_longitudinal_trend_eligibility'}<=mcfields and not {'implementation_phase','phase1e_trend_eligibility'}&mcfields,str(sorted(mcfields)))
ck('V-TYPE-001',len(cat['structured_output_schema_registry'])==9)
ck('V-LONG-001',set(m['subject_type'] for m in trend)<={'AIRCRAFT','MISSION_SYSTEM_INSTANCE'})
ck('V-LONG-002',all(not m['p1_longitudinal_trend_eligibility'] for m in ms if m['value_kind']=='STRUCTURED'))
ck('V-REPLAY-001','registry.analysis_release' in core['tables'])
# Documents
ov=(root/'03_TPAA_V8.0_总体方案.md').read_text(encoding='utf8'); method=(root/'03A_整体训练效果评估方案_TPAA_V8.0.md').read_text(encoding='utf8'); vis=(root/'05G_可视化_GUI设计分册.md').read_text(encoding='utf8')
ck('V-DOC-001','CREATE TABLE' not in ov and 'FIELD_CONTRACT' not in ov)
prof=sorted(p for p in root.glob('05[A-J]_*.md')); bad=[]
for p in prof:
 t=p.read_text(encoding='utf8')
 if '**定义权声明：**' not in t or 'CREATE TABLE' in t or 'FIELD_CONTRACT' in t: bad.append(p.name)
ck('V-DOC-002',len(prof)==10 and not bad,f'volumes={len(prof)} bad={bad}')
expected_vols={'05A_数据_Canonical_Context_Episode设计分册.md','05B_World_Stage_Event_Relation设计分册.md','05C_MetricEngine_116指标设计分册.md','05D_Observation_Assessment_Longitudinal设计分册.md','05E_Storage_Release_Replay设计分册.md','05F_Application_API_DTO设计分册.md','05G_可视化_GUI设计分册.md','05H_部署_性能_安全_治理设计分册.md','05I_训练效果_Human_Team_Mission_Joint设计分册.md','05J_Capability_Attribution_DigitalTwin_ModelProfile设计分册.md'}
ck('V-DOC-003',{p.name for p in prof}==expected_vols)
controlled=[root/'02_Core_Baseline_CB-1.4.0.md',root/'03_TPAA_V8.0_总体方案.md',root/'03A_整体训练效果评估方案_TPAA_V8.0.md',root/'04_ED-2.0_工程设计公共基线.md',*prof]
badmark=[]; badlegacy=[]
for p in controlled:
 t=p.read_text(encoding='utf8')
 if re.search(r'<!--\s*CURRENT_LOGICAL_SCHEMA|^#{1,6}.*CURRENT_LOGICAL_SCHEMA\s*$',t,re.M): badmark.append(p.name)
 if 'ED-1.5.12' in t or 'TPAA V7.2' in t: badlegacy.append(p.name)
ck('V-AUTH-002',not badmark,str(badmark)); ck('V-LEGACY-001',not badlegacy,str(badlegacy))
# Taxonomy and extension
ck('V-TAX-001',set(tax['training_types'])=={'BASIC_FLIGHT','WVR','BVR','STRIKE'})
ck('V-TAX-002',set(tax['assessment_scopes'])=={'INDIVIDUAL','TEAM','PACKAGE','JOINT_LVC'} and len(tax['assessment_output_layers'])==3 and len(tax['competency_domains'])==10)
ck('V-WORLD-001',set(world['capabilities'])=={'BASIC_CORE','WVR_CORE','WVR_INFO','WVR_FULL','BVR_PROCESS','BVR_FULL','STRIKE_CORE','STRIKE_INFO','STRIKE_FULL'})
ck('V-EXT-001',set(ext['p_capability_contracts'])=={'P2','P3','P4','P5','P6'})
ck('V-EXT-002',mfam.get('status')=='SEMANTIC_FAMILY_RESERVATION_NOT_EXECUTABLE_METRIC_CATALOG' and len(mfam.get('families',{}))>=15)
status={x['p_code']:x['baseline_status'] for x in pcap['capability_phases']}; ck('V-PCAP-001',status.get('P1')=='CURRENT_BASELINE' and all(status.get(p)=='DESIGN_CONTRACT_FROZEN' for p in ['P2','P3','P4','P5','P6']),str(status))
# Knowledge fidelity
need=['## 17. Basic Flight','## 18. WVR','## 19. BVR','## 20. 空对面/Strike','## 22. Team / Package / Joint-LVC','## 26. P2/P3 Aircraft Capability Intelligence','## 28. Course / Unit','## 36. P / M / WS / Stage 项目语言治理']
ck('V-KNOW-001',all(x in ov for x in need),str([x for x in need if x not in ov]))
gap=(root/'01A_R39全量知识承接差距与R2扩充报告.md').read_text(encoding='utf8'); nums=[int(x) for x in re.findall(r'^\|\s*(\d+)\s*\|',gap,re.M)]
coverage=load('R39_KNOWLEDGE_COVERAGE.json'); cent=coverage['entries']; ck('V-KNOW-002',nums==list(range(1,61)) and len(cent)==60 and coverage.get('unresolved_count')==0,f'rows={len(nums)} entries={len(cent)}')
method_need=['五个问题','结果不等于能力','安全是门槛','数据缺失不等于能力为零','C + TPAA-M','六类输入数据','通用指标数学模板','评分与资格判定','基本飞行训练评估方案','WVR 训练评估方案','BVR 训练评估方案','空对面攻击训练评估方案','多机评价中的归因原则','训练事件链与证据图','长期训练评价','教员评价与算法评价融合','复盘报告结构','自动选择复盘片段','评估体系验证','Aircraft Capability Intelligence']
ck('V-METHOD-001',len(method.encode())>100000 and all(x in method for x in method_need),f'bytes={len(method.encode())}')
forbid=['CREATE TABLE','FIELD_CONTRACT','EvaluationContextDTO:','MetricDetailDTO:','CURRENT_LOGICAL_SCHEMA','ED-1.5.12','TPAA V7.2']
ck('V-METHOD-002',not any(x in method for x in forbid),str([x for x in forbid if x in method]))
fid=load('KNOWLEDGE_FIDELITY_MATRIX.json'); fent=fid['entries']; dom=Counter(e['domain'] for e in fent)
ck('V-FIDELITY-001',len(fent)>=500 and fid.get('unresolved_count')==0 and dom['METHOD']>=180 and dom['VISUALIZATION']>=280 and all(e.get('fidelity_status') not in {'L0_MISSING','L1_REFERENCED_ONLY'} for e in fent),f'entries={len(fent)} domains={dict(dom)}')
# Safety/semantic separation
safe={'CR-016','CR-017','CR-018','CR-019','CR-020','CR-021','CR-022','CR-023','CR-024','CR-025','CR-026','CR-029','CR-030','CR-031'}
ck('V-SAFE-002',safe<=set(rulemap))
ck('V-SCOPE-001','Team/mission results are not copied to individual actors' in rulemap['CR-017']['rule'])
ck('V-INST-001','preserves the original automatic product' in rulemap['CR-019']['rule'] and 'override_rule' in tax['instructor_review'])
ck('V-COHORT-001','comparison key' in rulemap['CR-021']['rule'] and 'retrospective revision' in rulemap['CR-022']['rule'] and 'knowledge_time_rule' in ext)
ck('V-PLUGIN-001','plugins may not bypass' in rulemap['CR-026']['rule'] and len(tax['training_plugin_contract'])>=6)
# Visualization
ck('V-VIS-001',all(f'P{i:02d}' in vis for i in range(1,14)) and all(x in vis for x in ['Audio/Video/Transcript','Debrief Playlist','Positive Event','Strike','COUNTERFACTUAL']))
vneed=['可视化的核心任务','总分不是视觉中心','Mission Header','Master Timeline','3D / 2D 飞行轨迹视图','Source Coverage Matrix','WVR 复盘可视化','Truth--Track Matching Matrix','Cue--Response 可视化','BVR Team Shared Picture','空对面训练可视化','Evidence Panel','Root-cause Candidate 可视化','自动生成 Debrief Playlist','Positive Event 可视化','联合/LVC可视化扩展','推荐页面清单','不同用户角色的默认视图','可视化验收标准']
ck('V-VIS-002',len(vis.encode())>90000 and all(x in vis for x in vneed),f'bytes={len(vis.encode())}')
ck('V-VIS-003',not any(x in vis for x in ['EvaluationContextDTO:','MetricDetailDTO:','CapabilityObservationDTO:','ED-1.5.12','TPAA V7.2']))
# Provenance
ck('V-PROV-001',len(prov.get('semantic_sources_reviewed',[]))==4 and prov.get('metric_authority_migration',{}).get('current_artifact')=='P1_METRIC_CATALOG.json' and prov.get('input_authority_migration',{}).get('current_artifact')=='METRIC_INPUT_AUTHORITY_MATRIX.json')
# Platform
profiles=plat.get('certification_profiles',{}); eq=plat.get('logical_equivalence_contract',{})
ck('V-PLATFORM-001',set(plat.get('mandatory_os_families',[]))=={'WINDOWS','LINUX'} and {'WINDOWS_DESKTOP_X64','LINUX_DESKTOP_X64','WINDOWS_SERVICE_X64','LINUX_SERVICE_X64'}<=set(profiles))
ck('V-PLATFORM-002',{'CR-027','CR-028'}<=set(rulemap))
ck('V-PLATFORM-003',len(eq.get('exact_equivalence',[]))>=5 and 'numeric_equivalence' in eq)
eng=(root/'04_ED-2.0_工程设计公共基线.md').read_text(encoding='utf8'); dep=(root/'05H_部署_性能_安全_治理设计分册.md').read_text(encoding='utf8')
ck('V-PLATFORM-004','## 35. Windows/Linux 跨平台运行与可移植性' in ov and '## 32. 跨平台工程公共合同' in eng and '## 38. 双平台 CI、打包与发布' in dep)
ck('V-PLATFORM-005',all(x in str(plat) for x in ['WINDOWS_DESKTOP_X64','LINUX_DESKTOP_X64','WINDOWS_SERVICE_X64','LINUX_SERVICE_X64']))
trace=load('TRACEABILITY_MATRIX.json'); prow=[x for x in trace['items'] if x.get('requirement')=='Windows/Linux cross-platform portability and logical equivalence']; ck('V-PLATFORM-006',len(prow)==1)
# Terminology governance
ns=term['namespaces']; ck('V-TERM-001',set(ns)=={'P','M','WS','Stage'} and ns['P']['codes']==[f'P{i}' for i in range(1,7)] and ns['M']['codes']==[f'M{i}' for i in range(10)])
ck('V-TERM-002',{'CR-029','CR-030'}<=set(rulemap) and 'Stage is never a project milestone' in ns['Stage']['meaning'])
# no current ambiguous patterns in controlled human docs except explicit terminology prohibition/migration lines
bad=[]; patterns=[r'Phase\s*[1-9]',r'Phase-[1-9]',r'P1[BCDEFG]\b',r'\bimplementation_phase\b',r'\bphase1e_trend_eligibility\b',r'第一阶段|第二阶段|第三阶段|第四阶段|第五阶段|第六阶段|第七阶段|第八阶段|第九阶段']
for p in controlled:
 for n,line in enumerate(p.read_text(encoding='utf8').splitlines(),1):
  if any(re.search(q,line) for q in patterns):
   if not any(k in line for k in ['旧','历史','禁止','迁移','退出','legacy','Legacy']): bad.append(f'{p.name}:{n}:{line[:80]}')
ck('V-TERM-003',not bad,str(bad[:8]))
# method/visual Stage normalization: no generic Phase tokens
ck('V-TERM-004',not re.search(r'\b[Pp]hase\b',method) and not re.search(r'\b[Pp]hase\b',vis))
# milestones
mil=[x['code'] for x in mile['milestones']]; ck('V-MILESTONE-001',mil==[f'M{i}' for i in range(10)],str(mil))
ws_codes={x['code'] for x in ws['workstreams']}; refs={w for m in mile['milestones'] for w in m['required_workstreams']}
ck('V-WS-001',len(ws_codes)>=15 and len(ws_codes)==len(ws['workstreams']) and refs<=ws_codes,f'workstreams={len(ws_codes)} missing={sorted(refs-ws_codes)}')
legacy=term['legacy_mappings']; ck('V-LEGACYMAP-001',set(legacy)=={'1A','1B','1C','1D','1E','1F','1G'} and legacy['1C']['current']=='M2' and legacy['1D']['current']=='M3' and legacy['1E']['current']=='M4')
# current catalog has no legacy progress fields; no old authority files
ck('V-LEGACYMAP-002',all('implementation_phase' not in m and 'phase1e_trend_eligibility' not in m and m['delivery_milestone'] in {'M2','M3'} for m in ms) and not (can/'PHASE_LIFECYCLE.json').exists() and not (can/'PHASE1_METRIC_CATALOG.json').exists())
# Traceability terminology rows
reqs={x['requirement'] for x in trace['items']}; ck('V-TERM-TRACE-001',{'P/M/WS/Stage terminology separation','M0-M9 development milestone roadmap','WS engineering workstream registry','Legacy 1A-1G and 1C/1D/1E progress labels retired'}<=reqs)
# Metric family applicability and design-intent guide
app=cat.get('family_applicability_contracts',{})
ck('V-METRIC-APP-001',app.get('P1-SNS-*',{}).get('allowed_system_types')==['RADAR'] and set(app.get('P1-PSV-*',{}).get('allowed_system_types',[]))=={'IRST','EO'} and set(app.get('P1-ESM-*',{}).get('allowed_system_types',[]))=={'RWR','ESM'} and app.get('P1-DL-*',{}).get('allowed_system_types')==['DATALINK'] and app.get('P1-FUS-*',{}).get('allowed_system_types')==['FUSION'] and 'CR-031' in rulemap)
guidep=root/'05C1_116指标设计意图_适用边界_区别联系与计算方法说明.md'; guide=guidep.read_text(encoding='utf8') if guidep.exists() else ''
guide_codes=re.findall(r'^####\s+(P1-[A-Z]+-\d{3})\s+—',guide,re.M)
ck('V-METRIC-DESIGN-001',guidep.is_file() and len(guide.encode())>200000 and len(guide_codes)==116 and len(set(guide_codes))==116 and set(guide_codes)=={m['metric_code'] for m in ms} and '不是第二套可执行公式权威' in guide,f'bytes={len(guide.encode())} headings={len(guide_codes)}')
# Baseline lock
lockp=can/'BASELINE_LOCK.json'
if lockp.exists():
 lock=json.loads(lockp.read_text(encoding='utf8')); badh=[]
 for r in lock.get('artifacts',[]):
  p=can/r['file']; h=hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else ''
  if not p.is_file() or h!=r['sha256'] or p.stat().st_size!=r['bytes']: badh.append(r['file'])
 ck('V-HASH-001',lock.get('baseline',{}).get('core')=='CB-1.4.0' and lock.get('baseline',{}).get('rebaseline')=='R3.3_METRIC_DESIGN_GUIDE' and len(lock.get('artifacts',[]))==21 and not badh,str(badh))
else: ck('V-HASH-001',False,'lock missing')
# Review gate catalog parity
review=load('REVIEW_GATES.json'); catalog=[g['id'] for g in review['gates']]; exercised=[i for i,_,_ in res]
if catalog!=exercised:
 print('FATAL REVIEW_GATES mismatch'); print('catalog=',catalog); print('exercised=',exercised); sys.exit(4)
for i,ok,d in res: print(('PASS' if ok else 'FAIL'),i,d)
print(f'SUMMARY {sum(x[1] for x in res)}/{len(res)} PASS')
sys.exit(0 if all(x[1] for x in res) else 2)
