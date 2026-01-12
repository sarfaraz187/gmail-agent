"""
Agent module for email classification and decision-making.

This module contains the core agent logic:
- EmailClassifier: Classifies emails as auto-respond or needs-decision
- DecisionType: Enum of possible decision outcomes
"""

from email_agent.agent.classifier import (
    DecisionResult,
    DecisionType,
    EmailClassifier,
    email_classifier,
)

__all__ = [
    "DecisionType",
    "DecisionResult",
    "EmailClassifier",
    "email_classifier",
]
