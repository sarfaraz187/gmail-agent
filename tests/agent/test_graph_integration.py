"""Integration tests for the LangGraph agent."""

import json
import pytest
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from email_agent.agent import graph, invoke_graph, create_initial_state
from email_agent.agent.classifier import DecisionType, DecisionResult, EmailType


@dataclass
class MockEmailData:
    """Mock EmailData for testing."""
    message_id: str = "msg123"
    thread_id: str = "thread123"
    subject: str = "Test Subject"
    from_email: str = "sender@example.com"
    from_name: str = "Sender"
    to_email: str = "user@example.com"
    date: str = "2025-01-11"
    body: str = "Test email body"
    snippet: str = "Test snippet"
    labels: list = None
    rfc_message_id: str = "<message-123@example.com>"
    in_reply_to: str = None
    references: str = None

    def __post_init__(self):
        if self.labels is None:
            self.labels = []


class TestGraphIntegration:
    """Integration tests for the complete graph flow."""

    @pytest.fixture
    def mock_all_dependencies(self):
        """Mock all external dependencies for graph execution."""
        with patch("email_agent.agent.nodes.classify.email_classifier") as mock_classifier, \
             patch("email_agent.agent.nodes.plan.ChatOpenAI") as mock_llm, \
             patch("email_agent.agent.nodes.plan.tool_registry") as mock_tool_registry, \
             patch("email_agent.agent.nodes.plan.settings") as mock_plan_settings, \
             patch("email_agent.agent.nodes.execute.tool_registry") as mock_exec_registry, \
             patch("email_agent.agent.nodes.write.draft_generator") as mock_draft, \
             patch("email_agent.agent.nodes.write.email_formatter") as mock_formatter, \
             patch("email_agent.agent.nodes.write.get_user_config") as mock_user_config, \
             patch("email_agent.agent.nodes.send.gmail_client") as mock_gmail, \
             patch("email_agent.agent.nodes.send.label_manager") as mock_send_labels, \
             patch("email_agent.agent.nodes.notify.label_manager") as mock_notify_labels, \
             patch("email_agent.services.style_learner.style_learner") as mock_learner:

            # Setup plan settings
            mock_plan_settings.openai_model = "gpt-4o"
            mock_plan_settings.openai_api_key = "test-key"

            # Setup tool registry
            mock_tool_registry.list_tools.return_value = [
                {"name": "calendar_check", "description": "Check calendar"},
                {"name": "search_emails", "description": "Search emails"},
            ]
            mock_tool_registry.__contains__ = lambda self, x: x in ["calendar_check", "search_emails"]
            mock_exec_registry.__contains__ = mock_tool_registry.__contains__

            # Setup user config
            config = MagicMock()
            config.email = "user@example.com"
            config.signature_html = "<br>Best regards"
            mock_user_config.return_value = config

            yield {
                "classifier": mock_classifier,
                "llm": mock_llm,
                "tool_registry": mock_tool_registry,
                "exec_registry": mock_exec_registry,
                "draft_generator": mock_draft,
                "email_formatter": mock_formatter,
                "user_config": mock_user_config,
                "gmail_client": mock_gmail,
                "send_label_manager": mock_send_labels,
                "notify_label_manager": mock_notify_labels,
                "style_learner": mock_learner,
            }

    def test_auto_respond_without_tools(self, mock_all_dependencies):
        """Test AUTO_RESPOND flow without any tools needed."""
        mocks = mock_all_dependencies

        # Setup: Email classified as AUTO_RESPOND
        classification = DecisionResult(
            decision=DecisionType.AUTO_RESPOND,
            email_type=EmailType.SIMPLE_ACKNOWLEDGMENT,
            confidence=0.95,
            reason="Simple acknowledgment email"
        )
        mocks["classifier"].classify.return_value = classification
        mocks["classifier"].detect_language.return_value = "en"

        # LLM returns no tools needed
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "reasoning": "Simple email, no tools needed",
            "tools": []
        })
        mocks["llm"].return_value.invoke.return_value = mock_response

        # Draft generation
        mocks["draft_generator"].generate_draft.return_value = (
            "Thank you for your email!",
            "casual",
            0.85
        )
        mocks["email_formatter"].format_email.return_value = (
            "<p>Thank you for your email!</p>",
            "Thank you for your email!"
        )

        # Create initial state
        latest = MockEmailData(
            subject="Thanks!",
            body="Thanks for the update!"
        )
        state = create_initial_state(
            message_id="msg123",
            thread_id="thread123",
            thread_emails=[latest],
            latest_email=latest,
        )

        # Execute graph
        final_state = invoke_graph(state)

        # Verify outcome
        assert final_state["outcome"] == "sent"
        assert final_state["classification"] == classification
        assert final_state["tools_to_call"] == []
        assert final_state["draft_body"] == "Thank you for your email!"

        # Verify send was called
        mocks["gmail_client"].send_reply.assert_called_once()
        mocks["send_label_manager"].transition_to_done.assert_called_once_with("msg123")

    def test_auto_respond_with_calendar_tool(self, mock_all_dependencies):
        """Test AUTO_RESPOND flow with calendar tool execution."""
        mocks = mock_all_dependencies

        # Setup: Email classified as AUTO_RESPOND
        classification = DecisionResult(
            decision=DecisionType.AUTO_RESPOND,
            email_type=EmailType.SCHEDULING_REQUEST,
            confidence=0.9,
            reason="Meeting scheduling request"
        )
        mocks["classifier"].classify.return_value = classification
        mocks["classifier"].detect_language.return_value = "en"

        # LLM returns calendar tool
        mock_response = MagicMock()
        mock_response.content = json.dumps({
            "reasoning": "Need to check calendar availability",
            "tools": [{"name": "calendar_check", "args": {"start_date": "tomorrow"}}]
        })
        mocks["llm"].return_value.invoke.return_value = mock_response

        # Tool execution
        from email_agent.tools.base import ToolResult
        mocks["exec_registry"].invoke.return_value = ToolResult.ok({
            "summary": "Available: 10am, 2pm, 4pm"
        })

        # Draft generation
        mocks["draft_generator"].generate_draft.return_value = (
            "I'm available at 10am, 2pm, or 4pm tomorrow.",
            "formal",
            0.9
        )
        mocks["email_formatter"].format_email.return_value = (
            "<p>I'm available at 10am, 2pm, or 4pm tomorrow.</p>",
            "I'm available at 10am, 2pm, or 4pm tomorrow."
        )

        # Create initial state
        latest = MockEmailData(
            subject="Meeting tomorrow?",
            body="Can we meet tomorrow?"
        )
        state = create_initial_state(
            message_id="msg123",
            thread_id="thread123",
            thread_emails=[latest],
            latest_email=latest,
        )

        # Execute graph
        final_state = invoke_graph(state)

        # Verify outcome
        assert final_state["outcome"] == "sent"
        assert len(final_state["tools_to_call"]) == 1
        assert final_state["tools_to_call"][0]["name"] == "calendar_check"
        assert "calendar_check" in final_state["tool_results"]
        assert final_state["tool_results"]["calendar_check"].success

        # Verify tool was executed
        mocks["exec_registry"].invoke.assert_called_once_with(
            "calendar_check",
            start_date="tomorrow"
        )

    def test_needs_choice_routes_to_notify(self, mock_all_dependencies):
        """Test that NEEDS_CHOICE routes to notify node."""
        mocks = mock_all_dependencies

        # Setup: Email classified as NEEDS_CHOICE
        classification = DecisionResult(
            decision=DecisionType.NEEDS_CHOICE,
            email_type=EmailType.UNKNOWN,
            confidence=0.85,
            reason="Email presents multiple options requiring user choice"
        )
        mocks["classifier"].classify.return_value = classification
        mocks["classifier"].detect_language.return_value = "en"

        # Create initial state
        latest = MockEmailData(
            subject="Budget decision",
            body="Should we go with option A ($50k) or option B ($75k)?"
        )
        state = create_initial_state(
            message_id="msg123",
            thread_id="thread123",
            thread_emails=[latest],
            latest_email=latest,
        )

        # Execute graph
        final_state = invoke_graph(state)

        # Verify outcome
        assert final_state["outcome"] == "pending"
        assert final_state["classification"].decision == DecisionType.NEEDS_CHOICE

        # Verify notify was called
        mocks["notify_label_manager"].transition_to_pending.assert_called_once_with("msg123")

        # Verify send was NOT called
        mocks["gmail_client"].send_reply.assert_not_called()

    def test_needs_approval_routes_to_notify(self, mock_all_dependencies):
        """Test that NEEDS_APPROVAL routes to notify node."""
        mocks = mock_all_dependencies

        # Setup: Email classified as NEEDS_APPROVAL
        classification = DecisionResult(
            decision=DecisionType.NEEDS_APPROVAL,
            email_type=EmailType.INFO_REQUEST,
            confidence=0.9,
            reason="Contract requires human approval"
        )
        mocks["classifier"].classify.return_value = classification
        mocks["classifier"].detect_language.return_value = "en"

        # Create initial state
        latest = MockEmailData(
            subject="Contract for $100,000",
            body="Please confirm the contract for $100,000."
        )
        state = create_initial_state(
            message_id="msg123",
            thread_id="thread123",
            thread_emails=[latest],
            latest_email=latest,
        )

        # Execute graph
        final_state = invoke_graph(state)

        # Verify outcome
        assert final_state["outcome"] == "pending"
        mocks["notify_label_manager"].transition_to_pending.assert_called_once()

    def test_send_failure_marks_pending(self, mock_all_dependencies):
        """Test that send failure marks email as pending."""
        mocks = mock_all_dependencies

        # Setup: Email classified as AUTO_RESPOND
        classification = DecisionResult(
            decision=DecisionType.AUTO_RESPOND,
            email_type=EmailType.SIMPLE_ACKNOWLEDGMENT,
            confidence=0.95,
            reason="Simple email"
        )
        mocks["classifier"].classify.return_value = classification
        mocks["classifier"].detect_language.return_value = "en"

        # LLM returns no tools
        mock_response = MagicMock()
        mock_response.content = json.dumps({"reasoning": "No tools", "tools": []})
        mocks["llm"].return_value.invoke.return_value = mock_response

        # Draft generation
        mocks["draft_generator"].generate_draft.return_value = ("Thanks!", "casual", 0.8)
        mocks["email_formatter"].format_email.return_value = ("<p>Thanks!</p>", "Thanks!")

        # Send fails
        mocks["gmail_client"].send_reply.side_effect = Exception("SMTP error")

        # Create initial state
        latest = MockEmailData()
        state = create_initial_state(
            message_id="msg123",
            thread_id="thread123",
            thread_emails=[latest],
            latest_email=latest,
        )

        # Execute graph
        final_state = invoke_graph(state)

        # Verify error handling
        assert final_state["outcome"] == "error"
        assert "SMTP error" in final_state["error_message"]

        # Verify pending label was set
        mocks["send_label_manager"].transition_to_pending.assert_called_once_with("msg123")


class TestGraphRouting:
    """Test graph routing logic."""

    def test_graph_has_expected_nodes(self):
        """Verify graph contains all expected nodes."""
        nodes = list(graph.nodes.keys())
        expected = ["classify", "plan", "execute", "write", "send", "notify", "__start__"]
        for node in expected:
            assert node in nodes, f"Missing node: {node}"

    def test_create_initial_state_has_defaults(self):
        """Test that create_initial_state sets proper defaults."""
        latest = MockEmailData()
        state = create_initial_state(
            message_id="msg123",
            thread_id="thread123",
            thread_emails=[latest],
            latest_email=latest,
        )

        assert state["message_id"] == "msg123"
        assert state["thread_id"] == "thread123"
        assert state["classification"] is None
        assert state["detected_language"] == "en"
        assert state["tools_to_call"] == []
        assert state["tool_results"] == {}
        assert state["outcome"] == ""
        assert state["error_message"] is None
