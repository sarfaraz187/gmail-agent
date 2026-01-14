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
    notify_node,
)

logger = logging.getLogger(__name__)


# =============================================================================
# ROUTING FUNCTIONS
# =============================================================================


def route_after_classify(state: AgentState) -> str:
    """
    Route based on classification result.

    AUTO_RESPOND -> plan (continue to tool planning)
    Everything else -> notify (mark as pending)

    Args:
        state: Current agent state.

    Returns:
        Next node name: "plan" or "notify"
    """
    classification = state.get("classification")

    if classification is None:
        logger.warning("No classification result, routing to notify")
        return "notify"

    if classification.decision == DecisionType.AUTO_RESPOND:
        logger.info(
            f"Classification: AUTO_RESPOND ({classification.email_type.value}), "
            f"routing to plan"
        )
        return "plan"
    else:
        logger.info(
            f"Classification: {classification.decision.value}, "
            f"routing to notify"
        )
        return "notify"


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


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================


def build_graph() -> StateGraph:
    """
    Build the LangGraph state machine.

    Graph structure:
        CLASSIFY -> (AUTO_RESPOND) -> PLAN -> (has tools) -> EXECUTE -> WRITE -> SEND -> END
                                           -> (no tools)  -> WRITE -> SEND -> END
                 -> (NEEDS_INPUT)  -> NOTIFY -> END

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
    builder.add_node("notify", notify_node)

    # Set entry point
    builder.set_entry_point("classify")

    # Add conditional edges after classify
    builder.add_conditional_edges(
        "classify",
        route_after_classify,
        {
            "plan": "plan",
            "notify": "notify",
        },
    )

    # Add conditional edges after plan
    builder.add_conditional_edges(
        "plan",
        route_after_plan,
        {
            "execute": "execute",
            "write": "write",
        },
    )

    # Add linear edges
    builder.add_edge("execute", "write")
    builder.add_edge("write", "send")
    builder.add_edge("send", END)
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
