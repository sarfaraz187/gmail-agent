"""
LangGraph state machine for email processing.

Defines the agent graph with nodes and conditional routing.
"""

import logging

from langgraph.graph import StateGraph, END

from email_agent.agent.classifier import DecisionType
from email_agent.agent.state import AgentState
from email_agent.agent.nodes import (
    classify_node,
    plan_node,
    execute_node,
    write_node,
    send_node,
    save_draft_node,
    notify_node,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================


def route_after_classify(state: AgentState) -> str:
    """
    Route based on classification result.

    All classifications now go through plan -> write to generate a draft.
    - AUTO_RESPOND: will eventually send automatically
    - NEEDS_*: will save draft for user review

    Args:
        state: Current agent state.

    Returns:
        Next node name: "plan"
    """
    classification = state.get("classification")

    if classification is None:
        logger.warning("No classification result, routing to plan anyway")
        return "plan"

    if classification.decision == DecisionType.AUTO_RESPOND:
        logger.info(
            f"Classification: AUTO_RESPOND ({classification.email_type.value}), "
            f"routing to plan"
        )
    else:
        logger.info(
            f"Classification: {classification.decision.value} "
            f"(will generate draft for review), routing to plan"
        )

    return "plan"


def route_after_plan(state: AgentState) -> str:
    """
    Route based on whether tools need execution.

    Has tools -> execute (run the tools first)
    No tools -> write (skip directly to draft generation)

    Args:
        state: Current agent state.

    Returns:
        Next node name: "execute" or "write"
    """
    tools_to_call = state.get("tools_to_call", [])

    if tools_to_call:
        logger.info(f"Plan has {len(tools_to_call)} tool(s), routing to execute")
        return "execute"
    else:
        logger.info("No tools needed, routing to write")
        return "write"


def route_after_write(state: AgentState) -> str:
    """
    Route based on classification after draft is generated.

    AUTO_RESPOND -> send (send automatically)
    NEEDS_* -> save_draft (save for user review)

    Args:
        state: Current agent state.

    Returns:
        Next node name: "send" or "save_draft"
    """
    classification = state.get("classification")

    if classification is None:
        logger.warning("No classification, routing to save_draft for safety")
        return "save_draft"

    if classification.decision == DecisionType.AUTO_RESPOND:
        logger.info("AUTO_RESPOND: routing to send")
        return "send"
    else:
        logger.info(
            f"{classification.decision.value}: routing to save_draft for user review"
        )
        return "save_draft"


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================


def build_graph() -> StateGraph:
    """
    Build the LangGraph state machine.

    Graph structure:
        CLASSIFY -> PLAN -> (has tools) -> EXECUTE -> WRITE -> (AUTO_RESPOND) -> SEND -> END
                        -> (no tools)  -> WRITE -> (NEEDS_*) -> SAVE_DRAFT -> NOTIFY -> END

    All emails now go through PLAN and WRITE to generate a draft.
    - AUTO_RESPOND: draft is sent automatically
    - NEEDS_*: draft is saved for user review, then marked as pending

    Returns:
        Compiled StateGraph.
    """
    # Create the graph builder
    builder = StateGraph(AgentState)

    # Add nodes
    builder.add_node("classify", classify_node)
    builder.add_node("plan", plan_node)
    builder.add_node("execute", execute_node)
    builder.add_node("write", write_node)
    builder.add_node("send", send_node)
    builder.add_node("save_draft", save_draft_node)
    builder.add_node("notify", notify_node)

    # Set entry point
    builder.set_entry_point("classify")

    # Add edge from classify to plan (all emails now go through planning)
    builder.add_edge("classify", "plan")

    # Add conditional edges after plan
    builder.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "execute": "execute",
            "write": "write",
        },
    )

    # Add edge from execute to write
    builder.add_edge("execute", "write")

    # Add conditional edges after write
    builder.add_conditional_edges(
        "write",
        route_after_write,
        {
            "send": "send",
            "save_draft": "save_draft",
        },
    )

    # Add linear edges for final steps
    builder.add_edge("send", END)
    builder.add_edge("save_draft", "notify")
    builder.add_edge("notify", END)

    # Compile the graph
    return builder.compile()


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

# Build the graph once at module load
graph = build_graph()


def invoke_graph(state: AgentState) -> AgentState:
    """
    Invoke the agent graph with the given state.

    This is a convenience wrapper around graph.invoke().

    Args:
        state: Initial agent state.

    Returns:
        Final agent state after processing.
    """
    logger.info(
        f"Invoking agent graph for message {state['message_id']}, "
        f"thread {state['thread_id']}"
    )

    try:
        final_state = graph.invoke(state)
        logger.info(f"Graph completed with outcome: {final_state.get('outcome')}")
        return final_state

    except Exception as e:
        logger.exception(f"Graph execution failed: {e}")
        raise
