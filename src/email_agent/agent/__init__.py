"""
Agent module for email classification and LangGraph state machine.

This module contains:
- EmailClassifier: Classifies emails as auto-respond or needs-decision
- DecisionType/DecisionResult: Classification types and results
- AgentState: TypedDict for graph state
- graph: Compiled LangGraph state machine
- Node functions for each processing step
"""

from email_agent.agent.classifier import (
    DecisionResult,
    DecisionType,
    EmailClassifier,
    EmailType,
    email_classifier,
)
from email_agent.agent.state import AgentState, create_initial_state
from email_agent.agent.graph import graph, invoke_graph
from email_agent.agent.nodes import (
    classify_node,
    plan_node,
    execute_node,
    write_node,
    send_node,
    notify_node,
)

__all__ = [
    # Classifier
    "DecisionType",
    "DecisionResult",
    "EmailType",
    "EmailClassifier",
    "email_classifier",
    # State
    "AgentState",
    "create_initial_state",
    # Graph
    "graph",
    "invoke_graph",
    # Nodes
    "classify_node",
    "plan_node",
    "execute_node",
    "write_node",
    "send_node",
    "notify_node",
]
