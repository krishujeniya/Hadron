# backend/orchestrator/graph.py
#
# Assembles the LangGraph StateGraph from the node functions in nodes.py.
#
# WHAT IS A STATEGRAPH?
# A StateGraph is a directed graph where:
#   - NODES are async functions (defined in nodes.py)
#   - EDGES define execution order (which node runs after which)
#   - STATE (PRReviewState) is passed between nodes automatically
#
# OUR GRAPH SHAPE:
#
#   START
#     |
#     v
#   build_context          <- fetch PR diff from GitHub
#     |
#     v
#   fan_out_agents         <- run 4 agents in parallel (AGENTS_RUNNING)
#     |
#     v
#   aggregate_results      <- merge findings, decide verdict (AGGREGATING)
#     |
#     v
#   post_review            <- post to GitHub or HITL queue (POSTING)
#     |
#     v
#   END
#
# WHY LANGGRAPH AND NOT PLAIN ASYNCIO?
# We could write this as 4 async function calls in sequence. But LangGraph gives us:
#
#   1. CHECKPOINTING: after each node, LangGraph saves state to Redis.
#      If the server crashes mid-review, resume() reloads from the last checkpoint
#      and continues from there — not from the beginning.
#      (From distributed-systems wiki: "combine checkpointing with message logging.")
#
#   2. STATE MANAGEMENT: LangGraph merges partial state updates automatically.
#      Each node only returns what it changed — no need to copy the full state.
#
#   3. OBSERVABILITY HOOKS: LangGraph emits events before and after each node.
#      Phase 10 (Observability) will attach OpenTelemetry spans to these events
#      without changing the node functions at all.
#
#   4. CONDITIONAL EDGES: we can add branching logic later
#      (e.g. skip post_review and go straight to HITL if needed)
#      without rewriting the nodes.
#
# THE CHECKPOINTER:
# LangGraph's RedisSaver stores one checkpoint per node completion.
# The key format is: "checkpoint:{workflow_id}:{node_name}"
# resume() fetches the latest checkpoint and starts from the next node.

import logging

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from backend.orchestrator.checkpointer import DurableCheckpointSaver
from backend.orchestrator.nodes import (
    aggregate_results,
    build_context,
    fan_out_agents,
    post_review,
)
from backend.orchestrator.state import PRReviewState

logger = logging.getLogger(__name__)

# Shared checkpointer instance (DurableCheckpointSaver with Redis persistence)
# Retains workflow checkpoints keyed by thread_id (workflow_id)
_default_checkpointer: BaseCheckpointSaver = DurableCheckpointSaver()


def get_checkpointer() -> BaseCheckpointSaver:
    """Returns the active workflow checkpointer."""
    return _default_checkpointer


def build_review_graph(checkpointer: BaseCheckpointSaver | None = None):
    """
    Constructs and compiles the PR review StateGraph.

    RETURNS a compiled LangGraph graph — a callable object.
    To run a review: await graph.ainvoke(initial_state, config={"configurable": {"thread_id": workflow_id}})

    CHECKPOINTER:
    Compiled with a checkpointer so that checkpoints are automatically saved
    after each node completion. Enables state inspection via get_state()
    and resume() capabilities on interrupted executions.
    """
    # Step 1: Create a StateGraph that uses PRReviewState as its state schema.
    # LangGraph reads the TypedDict annotations to know what fields exist.
    workflow = StateGraph(PRReviewState)

    # Step 2: Register each node function with a name.
    # The name is used in edges, checkpoints, and log messages.
    workflow.add_node("build_context", build_context)
    workflow.add_node("fan_out_agents", fan_out_agents)
    workflow.add_node("aggregate_results", aggregate_results)
    workflow.add_node("post_review", post_review)

    # Step 3: Wire the edges (execution order).
    # START -> build_context: the graph always starts here
    workflow.add_edge(START, "build_context")

    # build_context -> fan_out_agents: always runs after context is ready
    workflow.add_edge("build_context", "fan_out_agents")

    # fan_out_agents -> aggregate_results: always runs after all agents finish
    workflow.add_edge("fan_out_agents", "aggregate_results")

    # aggregate_results -> post_review: always runs (post_review handles HITL internally)
    workflow.add_edge("aggregate_results", "post_review")

    # post_review -> END: the graph is done
    workflow.add_edge("post_review", END)

    # Step 4: Set the entry point explicitly.
    workflow.set_entry_point("build_context")

    # Step 5: Compile the graph with checkpointer.
    cp = checkpointer if checkpointer is not None else _default_checkpointer
    compiled = workflow.compile(checkpointer=cp)

    logger.info(
        "PR review graph compiled successfully with %s. Nodes: %s",
        type(cp).__name__,
        list(workflow.nodes),
    )

    return compiled


# Module-level compiled graph instance.
# Built once with checkpointer attached.
review_graph = build_review_graph()
# The compiled graph is stateless — it does not hold any per-review data.
# Per-review state lives in the checkpointer (keyed by workflow_id/thread_id).
# So we can safely share one compiled graph across all concurrent reviews.
#
# CONCURRENCY:
# LangGraph compiled graphs are safe to use concurrently.
# Each .ainvoke() call gets its own state isolated by thread_id (= workflow_id).
review_graph = build_review_graph()
