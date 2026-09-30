"""Asset inventory node."""
from app.agent.graph.state import AgentGraphState
from app.agent.readers.manifest import build_manifest, supported_files


def inventory_node(state: AgentGraphState) -> dict:
    manifest = build_manifest()
    files = supported_files(manifest)
    if not files:
        raise RuntimeError(
            "assets 目录没有可读取资料，请先放入 .xlsx/.docx/.csv/.md/.txt 文件"
        )
    return {"manifest": manifest}
