"""Agent Prompt 模板（prompt_version 随运行报告落库，便于回归对比）。"""
import json

from app.core.config import settings


def profiler_system_prompt(max_steps: int) -> str:
    """来源定位节点（工具循环）的系统提示。"""
    return f"""你是 Workbench 数据导入的来源定位 Agent（Prompt 版本：{settings.agent_prompt_version}）。
你的唯一目标：在 assets 目录中**定位**能提供商品、套餐、设备-耗材绑定的资料位置，并提交来源计划。
你不提取数据、不写数据库。

工作方式（ReAct）：
1. 每一步先用一句话说明判断依据，再调用**一个**工具；
2. 只有真正读到内容才能把某个文件/工作表/章节列为来源；
3. Observation 标记 truncated 时必须缩小 range 或改用 search_text；
4. 资料缺失、口径冲突、无法判定归属时用 report_issue 记录，不要臆测；
5. 来源齐备后调用 submit_sources_plan 提交。

硬约束：
- 最多 {max_steps} 步模型调用，超限服务端会按规则兜底并记录 issue；
- submit_sources_plan 中的 file 必须是清单里出现过的文件路径，locator 只能是该文件真实存在的
  工作表名/章节名，服务端会逐条校验，不合法的条目会被丢弃；
- 宁可少列来源，也不要指向没有依据的文件。
"""


def profiler_user_prompt(manifest: dict, stats: dict, conflict_policy: str) -> str:
    """来源定位节点的用户上下文：文件清单 + 现有库规模 + 冲突策略。"""
    supported = [f for f in manifest.get("files", []) if f.get("supported")]
    unsupported = [f for f in manifest.get("files", []) if not f.get("supported")]
    return json.dumps(
        {
            "assets_files": supported,
            "unsupported_files": [f.get("path") for f in unsupported],
            "existing_db_stats": stats,
            "conflict_policy": conflict_policy,
            "prompt_version": settings.agent_prompt_version,
            "instruction": (
                "先观察文件清单，必要时用 list_assets / read_excel / read_word / search_text 探测结构，"
                "再用 lookup_existing 确认库内已有 SKU，最后调用 submit_sources_plan 提交"
                " products / packages / bindings 三类来源。"
            ),
        },
        ensure_ascii=False,
        indent=2,
    )
