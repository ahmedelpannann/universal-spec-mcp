"""Privacy filter to redact sensitive information from specification documents."""

import re
from typing import Pattern


class PrivacyFilter:
    """Filters and redacts sensitive information from text before writing to specs."""
    
    def __init__(self):
        """Initialize the privacy filter with patterns for sensitive data."""
        self.patterns: list[tuple[Pattern, str]] = [
            # AWS Access Keys (AKIA...)
            (re.compile(r'AKIA[0-9A-Z]{16}'), '[REDACTED_AWS_KEY]'),
            
            # AWS Secret Keys (40 characters base64) - must be standalone
            (re.compile(r'\b[A-Za-z0-9/+]{40}\b'), '[REDACTED_AWS_SECRET]'),
            
            # GitHub Personal Access Tokens (ghp_, gho_, ghu_, ghs_, ghr_)
            (re.compile(r'gh[pousr]_[A-Za-z0-9]{36,}'), '[REDACTED_GITHUB_TOKEN]'),
            
            # Anthropic API Keys (sk-ant-...)
            # IMPORTANT: Check Anthropic pattern BEFORE generic OpenAI pattern
            (re.compile(r'sk-ant-[a-zA-Z0-9\-_]{95,}'), '[REDACTED_ANTHROPIC_KEY]'),
            
            # OpenAI API Keys (sk-...) - typically 48-51 characters after sk-
            (re.compile(r'sk-[a-zA-Z0-9]{48,51}'), '[REDACTED_OPENAI_KEY]'),
            
            # Generic API Keys
            (re.compile(r'api[_-]?key["\s:=]+["\']?([a-zA-Z0-9_\-]{32,})["\']?', re.IGNORECASE), 
             r'api_key="[REDACTED_API_KEY]"'),
            
            # Database Connection Strings
            (re.compile(r'(postgres|mysql|mongodb)://[^:]+:[^@]+@[^\s]+', re.IGNORECASE), 
             r'\1://[REDACTED_USER]:[REDACTED_PASSWORD]@[REDACTED_HOST]'),
            
            # Private Keys (PEM format)
            (re.compile(r'-----BEGIN [A-Z ]+PRIVATE KEY-----[\s\S]+?-----END [A-Z ]+PRIVATE KEY-----'), 
             '[REDACTED_PRIVATE_KEY]'),
            
            # JWT Tokens
            (re.compile(r'eyJ[a-zA-Z0-9_-]+\.eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+'), '[REDACTED_JWT_TOKEN]'),
            
            # Email addresses (optional - can be disabled if needed)
            # (re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'), '[REDACTED_EMAIL]'),
        ]
    
    def filter(self, text: str) -> str:
        """
        Filter sensitive information from the given text.
        
        Args:
            text: The text to filter
            
        Returns:
            The filtered text with sensitive information redacted
        """
        filtered_text = text
        
        for pattern, replacement in self.patterns:
            filtered_text = pattern.sub(replacement, filtered_text)
        
        return filtered_text
    
    def add_pattern(self, pattern: str, replacement: str) -> None:
        """
        Add a custom pattern to the filter.
        
        Args:
            pattern: Regular expression pattern to match
            replacement: Replacement text for matches
        """
        compiled_pattern = re.compile(pattern)
        self.patterns.append((compiled_pattern, replacement))


# Global instance for easy access
_default_filter = PrivacyFilter()


def filter_sensitive_data(text: str) -> str:
    """
    Convenience function to filter sensitive data using the default filter.
    
    Args:
        text: The text to filter
        
    Returns:
        The filtered text with sensitive information redacted
    """
    return _default_filter.filter(text)

# Made with Bob
