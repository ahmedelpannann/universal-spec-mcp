"""Tests for the privacy filter module."""

import pytest

from universal_spec_mcp.privacy import PrivacyFilter, filter_sensitive_data


class TestPrivacyFilter:
    """Test suite for PrivacyFilter class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.filter = PrivacyFilter()
    
    def test_aws_access_key_redaction(self):
        """Test that AWS access keys are redacted."""
        text = "My AWS key is AKIAIOSFODNN7EXAMPLE"
        filtered = self.filter.filter(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in filtered
        assert "[REDACTED_AWS_KEY]" in filtered
    
    def test_aws_secret_key_redaction(self):
        """Test that AWS secret keys are redacted."""
        text = "Secret: wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        filtered = self.filter.filter(text)
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in filtered
        assert "[REDACTED_AWS_SECRET]" in filtered
    
    def test_github_token_redaction(self):
        """Test that GitHub tokens are redacted."""
        tokens = [
            "ghp_1234567890abcdefghijklmnopqrstuvwxyz",
            "gho_1234567890abcdefghijklmnopqrstuvwxyz",
            "ghu_1234567890abcdefghijklmnopqrstuvwxyz",
            "ghs_1234567890abcdefghijklmnopqrstuvwxyz",
            "ghr_1234567890abcdefghijklmnopqrstuvwxyz",
        ]
        
        for token in tokens:
            text = f"GitHub token: {token}"
            filtered = self.filter.filter(text)
            assert token not in filtered
            assert "[REDACTED_GITHUB_TOKEN]" in filtered
    
    def test_anthropic_key_redaction(self):
        """Test that Anthropic API keys are redacted (checked before OpenAI pattern)."""
        # Anthropic keys start with sk-ant- and are longer
        text = "sk-ant-api03-1234567890abcdefghijklmnopqrstuvwxyz1234567890abcdefghijklmnopqrstuvwxyz1234567890abcdefg"
        filtered = self.filter.filter(text)
        assert "sk-ant-" not in filtered
        assert "[REDACTED_ANTHROPIC_KEY]" in filtered
    
    def test_openai_key_redaction(self):
        """Test that OpenAI API keys are redacted."""
        # OpenAI keys are sk- followed by 48 characters
        text = "sk-123456789012345678901234567890123456789012345678"
        filtered = self.filter.filter(text)
        assert "sk-123456789012345678901234567890123456789012345678" not in filtered
        assert "[REDACTED_OPENAI_KEY]" in filtered
    
    def test_anthropic_key_priority_over_openai(self):
        """Test that Anthropic keys are matched before generic OpenAI pattern."""
        # This is important because Anthropic keys also start with 'sk-'
        text = "sk-ant-api03-" + "x" * 95
        filtered = self.filter.filter(text)
        # Should be redacted as Anthropic key, not OpenAI key
        assert "[REDACTED_ANTHROPIC_KEY]" in filtered
        assert "[REDACTED_OPENAI_KEY]" not in filtered
    
    def test_generic_api_key_redaction(self):
        """Test that generic API keys are redacted."""
        texts = [
            'api_key="1234567890abcdefghijklmnopqrstuvwxyz"',
            "api-key: 1234567890abcdefghijklmnopqrstuvwxyz",
            "apikey='1234567890abcdefghijklmnopqrstuvwxyz'",
        ]
        
        for text in texts:
            filtered = self.filter.filter(text)
            assert "1234567890abcdefghijklmnopqrstuvwxyz" not in filtered
            assert "[REDACTED_API_KEY]" in filtered
    
    def test_database_connection_string_redaction(self):
        """Test that database connection strings are redacted."""
        connection_strings = [
            "postgres://user:password@localhost:5432/mydb",
            "mysql://admin:secret123@db.example.com:3306/production",
            "mongodb://dbuser:dbpass@mongo.example.com:27017/myapp",
        ]
        
        for conn_str in connection_strings:
            filtered = self.filter.filter(conn_str)
            assert "password" not in filtered
            assert "secret123" not in filtered
            assert "dbpass" not in filtered
            assert "[REDACTED_USER]" in filtered
            assert "[REDACTED_PASSWORD]" in filtered
            assert "[REDACTED_HOST]" in filtered
    
    def test_private_key_redaction(self):
        """Test that private keys in PEM format are redacted."""
        text = """
-----BEGIN RSA PRIVATE KEY-----
MIIEpAIBAAKCAQEA1234567890abcdefghijklmnopqrstuvwxyz
-----END RSA PRIVATE KEY-----
"""
        filtered = self.filter.filter(text)
        assert "BEGIN RSA PRIVATE KEY" not in filtered
        assert "[REDACTED_PRIVATE_KEY]" in filtered
    
    def test_jwt_token_redaction(self):
        """Test that JWT tokens are redacted."""
        text = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
        filtered = self.filter.filter(text)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in filtered
        assert "[REDACTED_JWT_TOKEN]" in filtered
    
    def test_multiple_secrets_in_same_text(self):
        """Test that multiple secrets in the same text are all redacted."""
        text = """
AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz
DATABASE_URL=postgres://user:password@localhost:5432/mydb
"""
        filtered = self.filter.filter(text)
        
        assert "AKIAIOSFODNN7EXAMPLE" not in filtered
        assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in filtered
        assert "ghp_1234567890abcdefghijklmnopqrstuvwxyz" not in filtered
        assert "password" not in filtered
        
        assert "[REDACTED_AWS_KEY]" in filtered
        assert "[REDACTED_AWS_SECRET]" in filtered
        assert "[REDACTED_GITHUB_TOKEN]" in filtered
        assert "[REDACTED_PASSWORD]" in filtered
    
    def test_non_sensitive_text_unchanged(self):
        """Test that non-sensitive text is not modified."""
        text = "This is a normal text without any secrets."
        filtered = self.filter.filter(text)
        assert filtered == text
    
    def test_add_custom_pattern(self):
        """Test adding a custom pattern to the filter."""
        self.filter.add_pattern(r'SECRET-\d{6}', '[REDACTED_CUSTOM]')
        text = "My secret code is SECRET-123456"
        filtered = self.filter.filter(text)
        assert "SECRET-123456" not in filtered
        assert "[REDACTED_CUSTOM]" in filtered
    
    def test_filter_sensitive_data_convenience_function(self):
        """Test the convenience function for filtering."""
        text = "AWS key: AKIAIOSFODNN7EXAMPLE"
        filtered = filter_sensitive_data(text)
        assert "AKIAIOSFODNN7EXAMPLE" not in filtered
        assert "[REDACTED_AWS_KEY]" in filtered
    
    def test_empty_string(self):
        """Test filtering an empty string."""
        filtered = self.filter.filter("")
        assert filtered == ""
    
    def test_case_insensitive_api_key_pattern(self):
        """Test that API key patterns are case-insensitive."""
        texts = [
            'API_KEY="1234567890abcdefghijklmnopqrstuvwxyz"',
            'Api_Key="1234567890abcdefghijklmnopqrstuvwxyz"',
            'api_key="1234567890abcdefghijklmnopqrstuvwxyz"',
        ]
        
        for text in texts:
            filtered = self.filter.filter(text)
            assert "1234567890abcdefghijklmnopqrstuvwxyz" not in filtered


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

# Made with Bob
