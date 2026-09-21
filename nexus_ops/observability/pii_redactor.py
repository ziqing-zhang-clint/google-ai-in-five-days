"""PII (Personally Identifiable Information) Redaction for Storage and Logging.

Protects sensitive customer and financial data before persistence or log emission:
- Email addresses
- Credit card / PAN numbers
- Phone numbers
- Social Security Numbers (SSN)
- Auth tokens and API keys
"""

import re
from typing import Any, Dict, List, Union


class PIIRedactor:
    """Enterprise PII Sanitization Engine."""

    # Regex patterns for sensitive customer identifiers
    EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
    CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,16}\b")
    PHONE_PATTERN = re.compile(r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b")
    SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
    TOKEN_PATTERN = re.compile(r"(?i)\b(bearer\s+|token[:=]\s*|key[:=]\s*|secret[:=]\s*)[a-zA-Z0-9_\-\.]{8,}\b")

    def redact(self, text: str) -> str:
        """Sanitizes PII from arbitrary text strings."""
        if not text or not isinstance(text, str):
            return text

        redacted = self.EMAIL_PATTERN.sub("[REDACTED_EMAIL]", text)
        redacted = self.CARD_PATTERN.sub("[REDACTED_CARD]", redacted)
        redacted = self.PHONE_PATTERN.sub("[REDACTED_PHONE]", redacted)
        redacted = self.SSN_PATTERN.sub("[REDACTED_SSN]", redacted)
        redacted = self.TOKEN_PATTERN.sub(r"\1[REDACTED_TOKEN]", redacted)
        return redacted

    def redact_data(self, data: Any) -> Any:
        """Recursively sanitizes dictionary, list, or primitive values."""
        if isinstance(data, str):
            return self.redact(data)
        elif isinstance(data, dict):
            return {k: self.redact_data(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self.redact_data(item) for item in data]
        return data


pii_redactor = PIIRedactor()
