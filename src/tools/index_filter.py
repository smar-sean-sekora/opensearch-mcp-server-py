# Copyright OpenSearch Contributors
# SPDX-License-Identifier: Apache-2.0

import fnmatch
import json
import logging
import os
import re
import yaml
from typing import Dict, List, Optional


class IndexFilterConfig:
    """Configuration for index filtering."""

    def __init__(
        self,
        allowed_index_patterns: Optional[List[str]] = None,
        denied_index_patterns: Optional[List[str]] = None,
    ):
        """
        Initialize index filter configuration.

        :param allowed_index_patterns: List of allowed index patterns (wildcards and regex)
        :param denied_index_patterns: List of denied index patterns (wildcards and regex)
        """
        self.allowed_index_patterns = allowed_index_patterns or []
        self.denied_index_patterns = denied_index_patterns or []

    def is_index_allowed(self, index_name: str) -> tuple[bool, Optional[str]]:
        """
        Check if an index is allowed based on configured patterns.

        Priority: Denied patterns are checked first. If no patterns are configured,
        all indexes are allowed.

        :param index_name: The index name to check
        :return: Tuple of (is_allowed, reason)
        """
        if not index_name:
            return True, None

        # Handle comma-separated index names or wildcards in a single string
        # Some tools may pass multiple indexes like "index1,index2"
        index_names = [name.strip() for name in index_name.split(',')]

        for single_index in index_names:
            allowed, reason = self._check_single_index(single_index)
            if not allowed:
                return False, reason

        return True, None

    def _check_single_index(self, index_name: str) -> tuple[bool, Optional[str]]:
        """Check a single index name against patterns."""
        # If index contains wildcards, we cannot validate it at this stage
        # Allow it through - OpenSearch will handle the expansion
        if '*' in index_name or '?' in index_name:
            logging.debug(
                f'Index pattern "{index_name}" contains wildcards, allowing through for OpenSearch expansion'
            )
            return True, None

        # Check denied patterns first (higher priority)
        if self.denied_index_patterns:
            for pattern in self.denied_index_patterns:
                if self._matches_pattern(index_name, pattern):
                    reason = f'Index "{index_name}" matches denied pattern: {pattern}'
                    logging.warning(reason)
                    return False, reason

        # If allowed patterns are configured, index must match at least one
        if self.allowed_index_patterns:
            for pattern in self.allowed_index_patterns:
                if self._matches_pattern(index_name, pattern):
                    logging.debug(f'Index "{index_name}" matches allowed pattern: {pattern}')
                    return True, None

            reason = f'Index "{index_name}" does not match any allowed patterns'
            logging.warning(reason)
            return False, reason

        # No patterns configured, allow all indexes
        return True, None

    def _matches_pattern(self, index_name: str, pattern: str) -> bool:
        """
        Check if an index name matches a pattern.

        Supports:
        - Wildcards: * and ? (e.g., "logs-*", "test-?-index")
        - Regex patterns: patterns starting with "regex:" (e.g., "regex:^logs-\\d{4}-\\d{2}$")

        :param index_name: The index name to check
        :param pattern: The pattern to match against
        :return: True if matches, False otherwise
        """
        # Regex pattern (starts with "regex:")
        if pattern.startswith('regex:'):
            regex_pattern = pattern[6:]  # Remove "regex:" prefix
            try:
                return bool(re.match(regex_pattern, index_name))
            except re.error as e:
                logging.error(f'Invalid regex pattern "{regex_pattern}": {e}')
                return False

        # Wildcard pattern
        return fnmatch.fnmatch(index_name, pattern)


# Global index filter configuration
_index_filter_config: Optional[IndexFilterConfig] = None


def load_index_filter_config(config_file_path: str = '') -> IndexFilterConfig:
    """
    Load index filter configuration from YAML file or environment variables.

    Priority order:
    1. YAML configuration file (if provided)
    2. Environment variables

    :param config_file_path: Path to YAML configuration file
    :return: IndexFilterConfig instance
    """
    global _index_filter_config

    allowed_patterns = []
    denied_patterns = []

    # Load from YAML file first
    if config_file_path:
        try:
            with open(config_file_path, 'r') as f:
                config = yaml.safe_load(f)
                if config and 'index_security' in config:
                    security_config = config['index_security']
                    allowed_patterns = security_config.get('allowed_index_patterns', [])
                    denied_patterns = security_config.get('denied_index_patterns', [])
                    logging.info(f'Loaded index filter config from {config_file_path}')
        except Exception as e:
            logging.error(f'Error loading index filter config from file: {e}')

    # Load from environment variables (only if not loaded from file)
    if not allowed_patterns and not denied_patterns:
        allowed_env = os.getenv('OPENSEARCH_ALLOWED_INDEX_PATTERNS', '')
        denied_env = os.getenv('OPENSEARCH_DENIED_INDEX_PATTERNS', '')

        if allowed_env:
            try:
                # Support both JSON array and comma-separated list
                if allowed_env.strip().startswith('['):
                    allowed_patterns = json.loads(allowed_env)
                else:
                    allowed_patterns = [p.strip() for p in allowed_env.split(',') if p.strip()]
                logging.info(f'Loaded allowed index patterns from environment: {allowed_patterns}')
            except json.JSONDecodeError as e:
                logging.error(f'Error parsing OPENSEARCH_ALLOWED_INDEX_PATTERNS: {e}')

        if denied_env:
            try:
                # Support both JSON array and comma-separated list
                if denied_env.strip().startswith('['):
                    denied_patterns = json.loads(denied_env)
                else:
                    denied_patterns = [p.strip() for p in denied_env.split(',') if p.strip()]
                logging.info(f'Loaded denied index patterns from environment: {denied_patterns}')
            except json.JSONDecodeError as e:
                logging.error(f'Error parsing OPENSEARCH_DENIED_INDEX_PATTERNS: {e}')

    _index_filter_config = IndexFilterConfig(
        allowed_index_patterns=allowed_patterns, denied_index_patterns=denied_patterns
    )

    return _index_filter_config


def get_index_filter_config() -> IndexFilterConfig:
    """
    Get the current index filter configuration.

    :return: IndexFilterConfig instance
    """
    global _index_filter_config
    if _index_filter_config is None:
        _index_filter_config = load_index_filter_config()
    return _index_filter_config


def validate_index_access(index_name: str) -> None:
    """
    Validate if an index can be accessed based on configured patterns.

    Raises an exception if access is denied.

    :param index_name: The index name to validate
    :raises Exception: If index access is denied
    """
    if not index_name:
        return

    config = get_index_filter_config()
    is_allowed, reason = config.is_index_allowed(index_name)

    if not is_allowed:
        raise Exception(f'Index access denied: {reason}')
