import json
import uuid
from datetime import datetime
from typing import Optional

from .. import __version__
from ..config.config_manager import ConfigManager


class UserTracker:
    """Manages anonymous user identification"""

    def __init__(self):
        self.config_manager = ConfigManager()
        self.user_id_file = self.config_manager.get_config_path("user_id.json", "cache")

    def get_or_create_user_id(self) -> str:
        """Get existing or create new anonymous user ID"""
        if self.user_id_file.exists():
            try:
                data = json.loads(self.user_id_file.read_text())
                return data.get("user_id")
            except Exception:
                pass  # Create new ID if file corrupted

        # Generate new anonymous ID
        user_id = str(uuid.uuid4())
        self._save_user_id(user_id)
        return user_id

    def _save_user_id(self, user_id: str):
        """Save user ID to cache file"""
        self.user_id_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "user_id": user_id,
            "created_at": datetime.now().isoformat(),
            "version": __version__,
        }
        self.user_id_file.write_text(json.dumps(data, indent=2))


# Global instance
_user_tracker: Optional[UserTracker] = None


def get_user_tracker() -> UserTracker:
    """Get shared user tracker instance"""
    global _user_tracker
    if _user_tracker is None:
        _user_tracker = UserTracker()
    return _user_tracker
