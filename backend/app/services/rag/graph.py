# graph.py
#
# Compiles the LangGraph RAG graph from the node functions in nodes.py.
# This is the only file that imports from langgraph directly.
# Everything else in the RAG pipeline is pure Python functions.
#
# GRAPH STRUCTURE:
#
#   START
#     |
#   retrieve          ← embeds query, searches pgvector
#     |
#   generate          ← reranks top 50 to 8, calls Gemini, builds citations
#     |
#   critic_node       ← checks staleness, version, contradictions
#     |
#   should_retry?     ← conditional edge, reads state.confidence
#    / \
# retry  finalize
#   |       |
# increment_retry   END
#   |
# (back to retrieve, max 2 loops)
#
# WHY A COMPILED GRAPH:
# LangGraph's compile() returns an object that handles state passing between
# nodes automatically. You call ainvoke(initial_state) once and the graph
# handles the loop, the conditional branching, and the state merging.
# Without this, you would write that orchestration logic by hand.

from langgraph.graph import StateGraph, END

from app.models.graph_state import GraphState
from app.services.rag.nodes import (
    retrieve,
    generate,
    critic_node,
    should_retry,
    increment_retry,
    finalize,
)

import structlog

log = structlog.get_logger(__name__)


def build_graph():
    """
    Builds and compiles the RAG graph.

    Returns a CompiledGraph that can be called with ainvoke(state).
    Called once at module load and cached as the module level
    singleton below.

    Node registration order does not matter. Edge registration order
    defines the actual execution sequence.
    """
    graph = StateGraph(GraphState)

    # Register every node with a string name. The name is what conditional
    # edges use to route between nodes and what appears in LangGraph traces.
    graph.add_node("retrieve",       retrieve)
    graph.add_node("generate",       generate)
    graph.add_node("critic_node",    critic_node)
    graph.add_node("increment_retry", increment_retry)
    graph.add_node("finalize",       finalize)

    # Entry point, the first node that runs when ainvoke is called.
    graph.set_entry_point("retrieve")

    # Linear edges, these always fire unconditionally.
    graph.add_edge("retrieve",    "generate")
    graph.add_edge("generate",    "critic_node")

    # Conditional edge from the critic. should_retry() reads state.confidence
    # and state.retry_count and returns either "retrieve" or "finalize"
    # as a string. LangGraph routes to whichever node that string names.
    graph.add_conditional_edges(
        "critic_node",
        should_retry,
        {
            "retrieve": "increment_retry",
            "finalize": "finalize",
        },
    )

    # increment_retry bumps the counter then loops back to retrieve.
    # This is a separate node rather than logic inside critic_node so the
    # retry count update is visible as its own step in LangGraph traces,
    # making debugging loops much easier.
    graph.add_edge("increment_retry", "retrieve")

    # finalize is the terminal node. END is a LangGraph sentinel that tells
    # the graph execution is complete and ainvoke should return the state.
    graph.add_edge("finalize", END)

    compiled = graph.compile()
    log.info("rag_graph_compiled")
    return compiled


# Module level singleton. Compiled once when this module is first imported.
# Every chat request calls rag_graph.ainvoke(state) on this same object.
# LangGraph compiled graphs are stateless between invocations, the state
# dict is created fresh per request via initial_state() in graph_state.py,
# so sharing one compiled graph across all requests is safe.
rag_graph = build_graph()
