# Aegis 项目工作区

本目录存放 HHZ 超声医疗报价平台的 Aegis 治理文档：需求/架构基线、规格、ADR、实现计划等。

## 结构

```
docs/aegis/
├── README.md               # 本文件
├── INDEX.md                # 所有文档的索引
├── BASELINE-GOVERNANCE.md  # 基线治理章程（本项目"宪法"，永不自动更新）
├── baseline/               # 基线快照（证据，非权威）
├── specs/                  # 规格文档（需求/设计落地处）
├── adr/                    # 架构决策记录（可选）
└── work/                   # 会话级草稿（不提升为正式文档时放这里）
```

## 使用约定

- 规格只进 `specs/`，计划只进 `plans/`，草稿进 `work/`。
- 基线治理以 `BASELINE-GOVERNANCE.md` 为准；`baseline/` 下的是证据快照。
- 每次新增/更新正式文档后，同步更新 `INDEX.md`。
