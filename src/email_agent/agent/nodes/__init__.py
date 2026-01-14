"""
Agent nodes for LangGraph state machine.

Each node is a function that takes AgentState and returns updated AgentState.
"""

from email_agent.agent.nodes.classify import classify_node
from email_agent.agent.nodes.plan import plan_node
from email_agent.agent.nodes.execute import execute_node
from email_agent.agent.nodes.write import write_node
from email_agent.agent.nodes.send import send_node
from email_agent.agent.nodes.notify import notify_node

__all__ = [
    "classify_node",
    "plan_node",
    "execute_node",
    "write_node",
    "send_node",
    "notify_node",
]
