"""
Email formatting service using Jinja2 templates.

Converts plain text email bodies to properly formatted HTML emails
with signature support.
"""

import logging
import re

from jinja2 import Environment, BaseLoader

logger = logging.getLogger(__name__)


# HTML email template
EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #333333;">
  <div>
    {{ body_html | safe }}
    {% if signature_html %}
    <div>
      {{ signature_html | safe }}
    </div>
    {% endif %}
  </div>
</body>
</html>
""".strip()


class EmailFormatter:
    """Formats email content as HTML using Jinja2 templates."""

    def __init__(self) -> None:
        """Initialize the Jinja2 environment."""
        self.env = Environment(loader=BaseLoader(), autoescape=False)
        self.template = self.env.from_string(EMAIL_TEMPLATE)

    def text_to_html(self, text: str) -> str:
        """
        Convert plain text to HTML with proper paragraph formatting.

        Handles:
        - Paragraphs (double newlines become <p> tags)
        - Line breaks (single newlines become <br>)
        - Basic escaping of HTML special characters

        Args:
            text: Plain text content.

        Returns:
            HTML formatted content.
        """
        if not text:
            return ""

        # Escape HTML special characters
        text = self._escape_html(text)

        # Normalize line endings
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Split into paragraphs (double newline)
        paragraphs = re.split(r"\n\n+", text.strip())

        html_paragraphs = []
        for para in paragraphs:
            # Convert single newlines to <br>
            para_html = para.strip().replace("\n", "<br>\n")
            if para_html:
                html_paragraphs.append(f'<p style="margin: 0 0 1em 0;">{para_html}</p>')

        return "\n".join(html_paragraphs)

    def _escape_html(self, text: str) -> str:
        """
        Escape HTML special characters.

        Args:
            text: Raw text.

        Returns:
            HTML-escaped text.
        """
        return (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
        )

    def format_email(
        self,
        body: str,
        signature_html: str = "",
    ) -> tuple[str, str]:
        """
        Format an email body as HTML with signature.

        Args:
            body: Plain text email body.
            signature_html: HTML signature to append.

        Returns:
            Tuple of (html_content, plain_text_content).
        """
        # Convert body to HTML
        body_html = self.text_to_html(body)

        # Render the full HTML email
        html_content = self.template.render(
            body_html=body_html,
            signature_html=signature_html,
        )

        # Generate plain text version (body + signature as plain text)
        plain_text = body
        if signature_html:
            # Strip HTML tags for plain text signature
            plain_signature = re.sub(r"<[^>]+>", "", signature_html)
            plain_signature = plain_signature.replace("&nbsp;", " ").strip()
            if plain_signature:
                plain_text = f"{body}\n\n--\n{plain_signature}"

        return html_content, plain_text


# Singleton instance
email_formatter = EmailFormatter()
