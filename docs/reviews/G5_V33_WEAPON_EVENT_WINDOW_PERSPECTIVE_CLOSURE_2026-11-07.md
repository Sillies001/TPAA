# TPAA v33 G5 Weapon Event / Window / Perspective 本地关闭报告

> 关闭状态：`G5=CLOSED_LOCAL_WITH_GATES`
> 日期：2026-11-07
> 范围：仅本地实现与验证；禁止推送、禁止生产部署、无发布声明。

## 1. 关闭结论

G5 的领域底座、受控后继权威、运行时能力激活、Canonical 读适配、三条 API、安全作用域、前端 client、DTO 单源生成、存储兼容和回滚门均已完成。所有 G5 `capability_status` 均为 `ACTIVE`，允许进入 G6；这不等于产品完成或发布就绪。

## 2. 已关闭的主要缺口

- 运行时不再通过 `authority_root` 目录名硬编码激活 G4/G5，而是验证锁哈希、受控工件与 approval；
- `api.route.097～099` 已真实注册，分别映射 detail、window、perspective，并保持既定 RAW/DERIVED 权限和 GUI permission；
- 非全局角色必须持有精确 `weapon_event:<id>`，或完整 batch/release/context 作用域；`*` 不可绕过；
- Canonical `world.world_relation` 子类型适配器提供精确读取，禁止 latest 回退和跨批次借数；无数据诚实返回 EMPTY；
- 跨批次 detector/identity 拒绝进入共享持久审计，且主体可区分；
- supersession 从“两版可查”提升为任意修订的线性链，检测多 current 分支时失败关闭；
- `CROSS_LAYER_DTO_CONTRACTS` 同时生成 Python TypedDict 和 TypeScript interface；
- CB-1.9.0 数据根可由 CB-1.10.0 在 DB 1.10.0 下无迁移复用，只有显式 lineage lock 被接受；
- 激活采用构造完成后再发布的原子门，失败不返回部分运行时。

## 3. 门禁结果

| 门禁 | 结果 |
|---|---|
| Ruff | PASS |
| Mypy | PASS，588 个源文件 |
| `adopt_g4_successor.py --check` | PASS |
| `adopt_g5_successor.py --check` | PASS |
| G4/G5 codegen `--check` | PASS，96/99 安全路由 |
| Python 回归 | PASS，329 项；其中 1 项 Windows 文件锁瞬态失败经独立重跑通过 |
| G5 定向测试 | PASS，69 项 |
| 前端 TypeScript typecheck | PASS |
| Vite 正式构建 | PASS |
| `g1_frontend_build.py` 资源一致性 | PASS |
| SQLite G4→G5 无迁移复用 | PASS，manifest 不变 |
| PostgreSQL schema lineage verifier | PASS，仅精确 allow-list |

两条警告来自 FastAPI TestClient 依赖的 Starlette/httpx 弃用提示，不是业务或安全失败。

## 4. 机器证据与后续边界

- 机器证据：`evidence/gui-g5-v33-closure.json`
- G5 权威：`baseline/CB-1.10.0/canonical/GUI_WEAPON_EVENT_AUTHORITY.json`
- 关闭工具：`tools/gui/g5_v33_close.py`
- 下一阶段：G6；`gui.overview`、`gui.batch.events`、`gui.replay` 仍按各自后续阶段保留。

当前工作树仍包含 G2～G5 的本地未提交修改；本次未执行 Git 提交、推送、生产部署或发布动作。
