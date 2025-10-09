# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0

import os
import pytest
import tempfile
import yaml
from tools.index_filter import (
    IndexFilterConfig,
    load_index_filter_config,
    validate_index_access,
)


class TestIndexFilterConfig:
    """Test IndexFilterConfig class."""

    def test_no_patterns_allows_all(self):
        """Test that no patterns configured allows all indexes."""
        config = IndexFilterConfig()
        is_allowed, reason = config.is_index_allowed('any-index')
        assert is_allowed is True
        assert reason is None

    def test_wildcard_allowed_pattern(self):
        """Test wildcard pattern in allowed list."""
        config = IndexFilterConfig(allowed_index_patterns=['logs-*', 'metrics-*'])

        # Should allow matching indexes
        is_allowed, _ = config.is_index_allowed('logs-2024-01')
        assert is_allowed is True

        is_allowed, _ = config.is_index_allowed('metrics-cpu')
        assert is_allowed is True

        # Should deny non-matching indexes
        is_allowed, reason = config.is_index_allowed('other-index')
        assert is_allowed is False
        assert 'does not match any allowed patterns' in reason

    def test_wildcard_denied_pattern(self):
        """Test wildcard pattern in denied list."""
        config = IndexFilterConfig(denied_index_patterns=['sensitive-*', '.security*'])

        # Should deny matching indexes
        is_allowed, reason = config.is_index_allowed('sensitive-data')
        assert is_allowed is False
        assert 'matches denied pattern' in reason

        is_allowed, reason = config.is_index_allowed('.security-index')
        assert is_allowed is False

        # Should allow non-matching indexes (no allowed patterns)
        is_allowed, _ = config.is_index_allowed('public-index')
        assert is_allowed is True

    def test_denied_takes_priority_over_allowed(self):
        """Test that denied patterns have higher priority than allowed."""
        config = IndexFilterConfig(
            allowed_index_patterns=['logs-*'], denied_index_patterns=['logs-sensitive-*']
        )

        # Should deny even though it matches allowed pattern
        is_allowed, reason = config.is_index_allowed('logs-sensitive-data')
        assert is_allowed is False
        assert 'matches denied pattern' in reason

        # Should allow if matches allowed and not denied
        is_allowed, _ = config.is_index_allowed('logs-public-data')
        assert is_allowed is True

    def test_regex_pattern_allowed(self):
        """Test regex pattern in allowed list."""
        config = IndexFilterConfig(allowed_index_patterns=[r'regex:^logs-\d{4}-\d{2}$'])

        # Should allow matching indexes
        is_allowed, _ = config.is_index_allowed('logs-2024-01')
        assert is_allowed is True

        # Should deny non-matching indexes
        is_allowed, reason = config.is_index_allowed('logs-202-01')
        assert is_allowed is False

        is_allowed, reason = config.is_index_allowed('logs-2024-1')
        assert is_allowed is False

    def test_regex_pattern_denied(self):
        """Test regex pattern in denied list."""
        config = IndexFilterConfig(denied_index_patterns=[r'regex:.*-dev-.*'])

        # Should deny matching indexes
        is_allowed, reason = config.is_index_allowed('app-dev-testing')
        assert is_allowed is False
        assert 'matches denied pattern' in reason

        # Should allow non-matching indexes
        is_allowed, _ = config.is_index_allowed('app-prod-testing')
        assert is_allowed is True

    def test_comma_separated_indexes(self):
        """Test handling of comma-separated index names."""
        config = IndexFilterConfig(
            allowed_index_patterns=['logs-*'], denied_index_patterns=['logs-sensitive-*']
        )

        # All allowed
        is_allowed, _ = config.is_index_allowed('logs-public,logs-app')
        assert is_allowed is True

        # One denied
        is_allowed, reason = config.is_index_allowed('logs-public,logs-sensitive-data')
        assert is_allowed is False
        assert 'logs-sensitive-data' in reason

    def test_wildcard_in_index_name_bypasses_validation(self):
        """Test that index names with wildcards bypass validation."""
        config = IndexFilterConfig(allowed_index_patterns=['logs-*'])

        # Wildcard in index name should be allowed through
        # (OpenSearch will expand it)
        is_allowed, _ = config.is_index_allowed('metrics-*')
        assert is_allowed is True

        is_allowed, _ = config.is_index_allowed('test-?-index')
        assert is_allowed is True

    def test_question_mark_wildcard(self):
        """Test question mark wildcard pattern."""
        config = IndexFilterConfig(allowed_index_patterns=['test-?-index'])

        # Should allow single character match
        is_allowed, _ = config.is_index_allowed('test-1-index')
        assert is_allowed is True

        is_allowed, _ = config.is_index_allowed('test-a-index')
        assert is_allowed is True

        # Should deny multi-character or no match
        is_allowed, _ = config.is_index_allowed('test-12-index')
        assert is_allowed is False

        is_allowed, _ = config.is_index_allowed('test--index')
        assert is_allowed is False

    def test_empty_index_name(self):
        """Test handling of empty index name."""
        config = IndexFilterConfig(allowed_index_patterns=['logs-*'])

        # Empty index name should be allowed
        is_allowed, _ = config.is_index_allowed('')
        assert is_allowed is True

        is_allowed, _ = config.is_index_allowed(None)
        assert is_allowed is True

    def test_multiple_patterns(self):
        """Test multiple allowed and denied patterns."""
        config = IndexFilterConfig(
            allowed_index_patterns=['logs-*', 'metrics-*', 'app-*'],
            denied_index_patterns=['*-test', '*-dev', 'temp-*'],
        )

        # Should allow matching allowed and not denied
        is_allowed, _ = config.is_index_allowed('logs-production')
        assert is_allowed is True

        # Should deny matching denied
        is_allowed, _ = config.is_index_allowed('logs-test')
        assert is_allowed is False

        is_allowed, _ = config.is_index_allowed('temp-metrics')
        assert is_allowed is False

        # Should deny not matching allowed
        is_allowed, _ = config.is_index_allowed('other-index')
        assert is_allowed is False


class TestLoadIndexFilterConfig:
    """Test loading index filter configuration."""

    def test_load_from_yaml_file(self):
        """Test loading configuration from YAML file."""
        config_data = {
            'index_security': {
                'allowed_index_patterns': ['logs-*', 'metrics-*'],
                'denied_index_patterns': ['sensitive-*'],
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            config = load_index_filter_config(config_file)
            assert config.allowed_index_patterns == ['logs-*', 'metrics-*']
            assert config.denied_index_patterns == ['sensitive-*']
        finally:
            os.unlink(config_file)

    def test_load_from_environment_json_array(self):
        """Test loading configuration from environment variables (JSON array format)."""
        os.environ['OPENSEARCH_ALLOWED_INDEX_PATTERNS'] = '["logs-*", "metrics-*"]'
        os.environ['OPENSEARCH_DENIED_INDEX_PATTERNS'] = '["sensitive-*"]'

        try:
            config = load_index_filter_config()
            assert config.allowed_index_patterns == ['logs-*', 'metrics-*']
            assert config.denied_index_patterns == ['sensitive-*']
        finally:
            del os.environ['OPENSEARCH_ALLOWED_INDEX_PATTERNS']
            del os.environ['OPENSEARCH_DENIED_INDEX_PATTERNS']

    def test_load_from_environment_comma_separated(self):
        """Test loading configuration from environment variables (comma-separated format)."""
        os.environ['OPENSEARCH_ALLOWED_INDEX_PATTERNS'] = 'logs-*, metrics-*, app-*'
        os.environ['OPENSEARCH_DENIED_INDEX_PATTERNS'] = 'sensitive-*, temp-*'

        try:
            config = load_index_filter_config()
            assert config.allowed_index_patterns == ['logs-*', 'metrics-*', 'app-*']
            assert config.denied_index_patterns == ['sensitive-*', 'temp-*']
        finally:
            del os.environ['OPENSEARCH_ALLOWED_INDEX_PATTERNS']
            del os.environ['OPENSEARCH_DENIED_INDEX_PATTERNS']

    def test_yaml_takes_priority_over_env(self):
        """Test that YAML configuration takes priority over environment variables."""
        config_data = {
            'index_security': {
                'allowed_index_patterns': ['from-yaml-*'],
                'denied_index_patterns': ['yaml-denied-*'],
            }
        }

        os.environ['OPENSEARCH_ALLOWED_INDEX_PATTERNS'] = '["from-env-*"]'
        os.environ['OPENSEARCH_DENIED_INDEX_PATTERNS'] = '["env-denied-*"]'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            config = load_index_filter_config(config_file)
            # Should use YAML config, not env vars
            assert config.allowed_index_patterns == ['from-yaml-*']
            assert config.denied_index_patterns == ['yaml-denied-*']
        finally:
            os.unlink(config_file)
            del os.environ['OPENSEARCH_ALLOWED_INDEX_PATTERNS']
            del os.environ['OPENSEARCH_DENIED_INDEX_PATTERNS']

    def test_load_empty_config(self):
        """Test loading with no configuration."""
        config = load_index_filter_config()
        assert config.allowed_index_patterns == []
        assert config.denied_index_patterns == []

    def test_load_missing_index_security_section(self):
        """Test loading YAML without index_security section."""
        config_data = {'clusters': {'cluster1': {'opensearch_url': 'http://localhost:9200'}}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            config = load_index_filter_config(config_file)
            assert config.allowed_index_patterns == []
            assert config.denied_index_patterns == []
        finally:
            os.unlink(config_file)


class TestValidateIndexAccess:
    """Test validate_index_access function."""

    def test_validate_allowed_index(self):
        """Test validation of allowed index."""
        config_data = {'index_security': {'allowed_index_patterns': ['logs-*']}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            # Load config
            load_index_filter_config(config_file)

            # Should not raise exception
            validate_index_access('logs-2024-01')
        finally:
            os.unlink(config_file)

    def test_validate_denied_index_raises_exception(self):
        """Test validation of denied index raises exception."""
        config_data = {'index_security': {'denied_index_patterns': ['sensitive-*']}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            # Load config
            load_index_filter_config(config_file)

            # Should raise exception
            with pytest.raises(Exception) as exc_info:
                validate_index_access('sensitive-data')

            assert 'Index access denied' in str(exc_info.value)
            assert 'sensitive-data' in str(exc_info.value)
        finally:
            os.unlink(config_file)

    def test_validate_empty_index(self):
        """Test validation of empty index."""
        config_data = {'index_security': {'allowed_index_patterns': ['logs-*']}}

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(config_data, f)
            config_file = f.name

        try:
            # Load config
            load_index_filter_config(config_file)

            # Empty index should not raise exception
            validate_index_access('')
            validate_index_access(None)
        finally:
            os.unlink(config_file)
