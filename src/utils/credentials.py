"""
Credential management for Job Search Automation System.
Retrieves API keys from ~/databases/productivity.db credentials table.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional, Dict
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)

PRODUCTIVITY_DB = Path.home() / "databases" / "productivity.db"


class CredentialManager:
    """Manages API credentials from the productivity database."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or PRODUCTIVITY_DB
        self._cache: Dict[str, str] = {}

    def _get_from_db(self, service_name: str) -> Optional[str]:
        """Get credential from database."""
        if not self.db_path.exists():
            logger.warning(f"Productivity database not found: {self.db_path}")
            return None

        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.execute(
                "SELECT api_key FROM credentials WHERE service_name = ? AND is_active = 1",
                (service_name,)
            )
            row = cursor.fetchone()
            conn.close()

            if row and row[0]:
                return row[0]
        except Exception as e:
            logger.error(f"Error fetching credential for {service_name}: {e}")

        return None

    def _get_from_env(self, env_var: str) -> Optional[str]:
        """Get credential from environment variable."""
        return os.environ.get(env_var)

    def get(self, service_name: str, env_var: str = None) -> Optional[str]:
        """
        Get a credential by service name.

        Lookup order:
        1. Cache
        2. Environment variable (if specified)
        3. Database

        Args:
            service_name: Name of the service in the credentials table
            env_var: Optional environment variable to check first

        Returns:
            API key/credential or None
        """
        # Check cache
        if service_name in self._cache:
            return self._cache[service_name]

        # Check environment variable
        if env_var:
            value = self._get_from_env(env_var)
            if value:
                self._cache[service_name] = value
                return value

        # Check database
        value = self._get_from_db(service_name)
        if value:
            self._cache[service_name] = value
            return value

        logger.warning(f"No credential found for {service_name}")
        return None

    def clear_cache(self):
        """Clear the credential cache."""
        self._cache.clear()


# Singleton instance
_manager: Optional[CredentialManager] = None


def get_credential_manager() -> CredentialManager:
    """Get the singleton credential manager."""
    global _manager
    if _manager is None:
        _manager = CredentialManager()
    return _manager


# Convenience functions for common credentials
def get_openai_key() -> Optional[str]:
    """Get OpenAI API key."""
    return get_credential_manager().get('openai', 'OPENAI_API_KEY')


def get_github_token() -> Optional[str]:
    """Get GitHub personal access token."""
    # Try the specific token first, then the general one
    manager = get_credential_manager()
    token = manager.get('github_personal_token', 'GITHUB_TOKEN')
    if not token:
        token = manager.get('github', 'GITHUB_TOKEN')
    return token


def get_brave_api_key() -> Optional[str]:
    """Get Brave Search API key."""
    return get_credential_manager().get('brave', 'BRAVE_API_KEY')


def get_tavily_api_key() -> Optional[str]:
    """Get Tavily API key."""
    return get_credential_manager().get('tavily', 'TAVILY_API_KEY')


def get_slack_webhook() -> Optional[str]:
    """Get Slack webhook URL."""
    return get_credential_manager().get('slack_webhook', 'SLACK_WEBHOOK_URL')


def get_notification_email() -> Optional[str]:
    """Get notification email address."""
    return get_credential_manager().get('notification_email', 'NOTIFICATION_EMAIL')


def validate_credentials() -> Dict[str, bool]:
    """Validate all required credentials are available."""
    return {
        'openai': bool(get_openai_key()),
        'github': bool(get_github_token()),
        'brave': bool(get_brave_api_key()),
        'tavily': bool(get_tavily_api_key()),
    }
