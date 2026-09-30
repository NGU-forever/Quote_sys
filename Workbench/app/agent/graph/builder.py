"""Compile the Workbench LangGraph import state machine."""
from app.agent.graph.nodes.extractors import (
    extract_bindings_node,
    extract_packages_node,
    extract_products_node,
)
from app.agent.graph.nodes.inventory import inventory_node
from app.agent.graph.nodes.profiler import profiler_node
from app.agent.graph.nodes.quality import (
    apply_node,
    correction_node,
    fail_node,
    reconcile_node,
    report_node,
    should_continue_correction,
    validate_node,
)
from app.agent.graph.runtime import GraphRuntime
from app.agent.graph.state import AgentGraphState
from langgraph.graph import END, START, StateGraph


def build_import_graph(runtime: GraphRuntime, checkpointer):
    """Build and compile the directed import graph for one run."""
    graph = StateGraph(AgentGraphState)
    graph.add_node(
        "inventory_node",
        lambda state: (runtime.ensure_active(), inventory_node(state))[1],
    )
    graph.add_node(
        "profiler_node",
        lambda state: (runtime.ensure_active(), profiler_node(state))[1],
    )
    graph.add_node(
        "extract_products_node",
        lambda state: extract_products_node(state, runtime),
    )
    graph.add_node(
        "extract_packages_node",
        lambda state: extract_packages_node(state, runtime),
    )
    graph.add_node(
        "extract_bindings_node",
        lambda state: extract_bindings_node(state, runtime),
    )
    graph.add_node("reconcile_node", lambda state: reconcile_node(state, runtime))
    graph.add_node("validate_node", lambda state: validate_node(state, runtime))
    graph.add_node(
        "correction_node",
        lambda state: correction_node(state, runtime),
    )
    graph.add_node("fail_node", lambda state: fail_node(state, runtime))
    graph.add_node("apply_node", lambda state: apply_node(state, runtime))
    graph.add_node("report_node", lambda state: report_node(state, runtime))

    graph.add_edge(START, "inventory_node")
    graph.add_edge("inventory_node", "profiler_node")
    graph.add_edge("profiler_node", "extract_products_node")
    graph.add_edge("profiler_node", "extract_packages_node")
    graph.add_edge("profiler_node", "extract_bindings_node")
    graph.add_edge("extract_products_node", "reconcile_node")
    graph.add_edge("extract_packages_node", "reconcile_node")
    graph.add_edge("extract_bindings_node", "reconcile_node")
    graph.add_edge("reconcile_node", "validate_node")
    graph.add_conditional_edges(
        "validate_node",
        should_continue_correction,
        {
            "correction_node": "correction_node",
            "fail_node": "fail_node",
            "apply_node": "apply_node",
        },
    )
    graph.add_edge("correction_node", "validate_node")
    graph.add_edge("fail_node", "report_node")
    graph.add_edge("apply_node", "report_node")
    graph.add_edge("report_node", END)
    return graph.compile(checkpointer=checkpointer)
