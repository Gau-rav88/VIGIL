from __future__ import annotations

from typing import Any

from langgraph.graph import END, StateGraph

from orchestrator.models import CaseState
from orchestrator.nodes import (
    OrchestratorDeps,
    align_node,
    assess_node,
    attribute_node,
    await_review_node,
    draft_node,
    enrich_node,
    open_case_node,
    publish_node,
    sign_node,
    validate_node,
)
from orchestrator.routes import (
    after_align,
    after_assess,
    after_enrich,
    after_open,
    after_review,
    after_sign,
    after_validate,
)


def build_graph(deps: OrchestratorDeps, checkpointer: Any = None) -> Any:
    """
    Compiles the authoritative LangGraph StateGraph(CaseState)
    orchestrating forensic case lifecycle from anomaly trigger to published signed dossier.
    """
    g: Any = StateGraph(CaseState)

    # 1. Register Nodes
    g.add_node("open_case", open_case_node(deps))
    g.add_node("enrich", enrich_node(deps))
    g.add_node("align", align_node(deps))
    g.add_node("attribute", attribute_node(deps))
    g.add_node("assess", assess_node(deps))
    g.add_node("draft", draft_node(deps))
    g.add_node("validate", validate_node(deps))
    g.add_node("sign", sign_node(deps))
    g.add_node("await_review", await_review_node(deps))
    g.add_node("publish", publish_node(deps))

    # 2. Set Entrypoint
    g.set_entry_point("open_case")

    # 3. Register Conditional and Direct Edges
    g.add_conditional_edges("open_case", after_open, {"enrich": "enrich", "merged": END})
    g.add_conditional_edges("enrich", after_enrich, {"align": "align", "failed": END})
    g.add_conditional_edges("align", after_align, {"attribute": "attribute", "watchlist": END})
    g.add_edge("attribute", "assess")
    g.add_conditional_edges("assess", after_assess, {"attribute": "attribute", "draft": "draft", "close": END})
    g.add_edge("draft", "validate")
    g.add_conditional_edges("validate", after_validate, {"draft": "draft", "sign": "sign"})
    g.add_conditional_edges("sign", after_sign, {"await_review": "await_review", "failed": END})
    g.add_conditional_edges(
        "await_review",
        after_review,
        {"publish": "publish", "rejected": END, "rework_attr": "attribute", "rework_draft": "draft"},
    )
    g.add_edge("publish", END)

    return g.compile(checkpointer=checkpointer)
