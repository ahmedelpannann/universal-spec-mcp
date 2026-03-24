import pytest
from universal_spec_mcp.privacy import privacy_filter

def test_privacy_filter_aws_keys():
    text = "Here is my key: AKIAIOSFODNN7EXAMPLE and secret: aws_secret_access_key='wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY'"
    scrubbed, result = privacy_filter.scrub(text)
    
    assert "AKIAIOSFODNN7EXAMPLE" not in scrubbed
    assert "[REDACTED:AWS_KEY]" in scrubbed
    assert "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY" not in scrubbed
    assert "[REDACTED:AWS_SECRET]" in scrubbed
    assert result.redactions == 2

def test_privacy_filter_github_token():
    text = "Use this token: ghp_16C7e42F292c6912E7710c838347Ae178B4a"
    scrubbed, result = privacy_filter.scrub(text)
    
    assert "ghp_16C7e42F292c6912E7710c838347Ae178B4a" not in scrubbed
    assert "[REDACTED:GITHUB_TOKEN]" in scrubbed
    assert result.redactions == 1

def test_privacy_filter_openai_key():
    text = "export OPENAI_API_KEY=sk-proj-1234567890abcdef1234567890abcdef"
    scrubbed, result = privacy_filter.scrub(text)
    
    assert "sk-proj-1234567890abcdef1234567890abcdef" not in scrubbed
    assert "[REDACTED:API_KEY]" in scrubbed or "[REDACTED:OPENAI_KEY]" in scrubbed
    assert result.redactions == 1

def test_privacy_filter_no_secrets():
    text = "This is a normal design document with no secrets."
    scrubbed, result = privacy_filter.scrub(text)
    
    assert scrubbed == text
    assert result.redactions == 0
