# W9 同一候选正式发布门禁手册

## 1. 读取机器决定

调用 `GET /runtime/final-qualification`。本地候选必须返回：

- `schema=TPAA_W9_FINAL_QUALIFICATION_STATUS_V1`
- `stage_status=CLOSED_LOCAL_WITH_RELEASE_GATES`
- `decision=NO_GO`
- `qualification=LOCAL_CANDIDATE_NOT_FORMALLY_QUALIFIED`
- `formal_release_allowed=false`
- `formal_release_claimed=false`

未配置 W9 状态时端点返回 HTTP 503 和 `W9_FINAL_QUALIFICATION_NOT_CONFIGURED`。禁止在 API、GUI、部署脚本或人工记录中覆盖该决定。

## 2. 生成本地候选清单

先在干净 tracked worktree 的 exact HEAD 上构建 Windows/Linux × Desktop/Service 四个开发包，再调用：

```text
python tools/qualification/w9_local_candidate.py \
  --dist <four-package-directory> \
  --expected-revision <40-char-head-sha> \
  --baseline-lock baseline/CB-1.5.0/BASELINE_LOCK.json \
  --dependency-lock uv.lock \
  --evidence <CATEGORY>=<evidence-path> ... \
  --output evidence/local/w9/local-candidate-manifest.json
```

必须按 `W9_EVIDENCE_CATEGORIES` 的固定顺序提供十个 `--evidence`。清单会复核 summary schema、开发资格标记、profile、source revision、包大小和实际 SHA-256，并计算包含基线锁、依赖锁和四包哈希的聚合候选身份。

该命令输出始终为本地 `NO_GO` 清单；它证明本地证据的候选一致性，不签发正式资格。

## 3. 正式证据装载规则

正式批准记录必须逐类提供：`category`、`state=ACCEPTED`、非空 `reason_code`、与聚合候选完全相同的 `candidate_identity_sha256`、批准证据的 `evidence_sha256`。使用 `build_w9_final_qualification_status(...)` 装载，由机器计算最终决定。

除十类证据全接受外，还必须满足：

1. 未豁免 BLOCKER 为 0；
2. 未豁免 HIGH 为 0；
3. protected main 的 exact SHA 就是 source revision；
4. Hosted CI 对该 exact SHA 全部成功；
5. 独立发布批准完成；
6. 批准签名存在并验证通过。

只要任一条件不成立，机器决定必须为 `NO_GO`。

## 4. 不可复用的证据

- 不得把历史 PRCB 1.0.1 的 protected-main 或 Hosted CI 结论迁移到当前候选。
- 不得把开发包的 SBOM 当作组织签名或正式 provenance。
- 不得把 Docker/Moto/本地主机结果当作四个批准目标环境验收。
- 不得把自动视觉回归当作真实角色任务签字。
- 不得把未完整裁决的问题数量填成零；未知必须保持 `null` 或门禁未接受。

## 5. 发布前最终核对

确认十类证据中的 candidate identity 完全一致；重新计算所有证据 SHA-256；确认签名主体、用途和信任链；从 protected main exact SHA 重跑 Hosted CI；复核未豁免 BLOCKER/HIGH；由与实现人员相互独立的批准方确认最终清单。只有机器端点返回 `FORMALLY_QUALIFIED / GO / formal_release_allowed=true` 后，才可进入另行授权的发布流程。该状态本身不执行推送或生产部署。
