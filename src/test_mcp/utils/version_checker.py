import importlib.metadata
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

import httpx
from packaging import version

from ..config.config_manager import ConfigManager


class VersionChecker:
    """Handles version checking against PyPI with smart caching"""

    def __init__(self, package_name: str = "mcp-testing", timeout: int = 5):
        self.package_name = package_name
        self.timeout = timeout
        self.config_manager = ConfigManager()
        self.cache_file = self._get_cache_file()

    def _get_cache_file(self) -> Path:
        """Get version cache file path"""
        cache_dir = self.config_manager.paths.get_system_paths()["cache_dir"]
        return cache_dir / "version_check.json"

    def get_current_version(self) -> str:
        """Get currently installed package version"""
        try:
            return importlib.metadata.version(self.package_name)
        except importlib.metadata.PackageNotFoundError:
            return "0.0.0"  # Development fallback

    def check_for_update_async(self, callback=None):
        """Run version check in background thread"""

        def check():
            try:
                result = self.check_for_update()
                if callback:
                    callback(result)
            except Exception:
                # Silently fail - don't interrupt user workflow
                pass

        thread = threading.Thread(target=check)
        thread.daemon = True
        thread.start()

    def check_for_update(self) -> dict | None:
        """Check PyPI for newer version"""
        # Check cache first
        cached_result = self._load_cache()
        if cached_result and not self._is_cache_expired(cached_result):
            return cached_result

        try:
            # Fetch from PyPI
            response = httpx.get(
                f"https://pypi.org/pypi/{self.package_name}/json", timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            latest_version = data["info"]["version"]
            current_version = self.get_current_version()

            # Prepare result
            result = {
                "current_version": current_version,
                "latest_version": latest_version,
                "has_update": version.parse(latest_version)
                > version.parse(current_version),
                "last_check": datetime.now().isoformat(),
                "package_url": f"https://pypi.org/project/{self.package_name}/",
                "release_notes_url": f"https://pypi.org/project/{self.package_name}/{latest_version}/",
            }

            # Cache result
            self._save_cache(result)
            return result

        except Exception:
            # Return cached result on error, or None
            return cached_result

    def _load_cache(self) -> dict | None:
        """Load cached version check result"""
        try:
            if self.cache_file.exists():
                with open(self.cache_file) as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def _save_cache(self, result: dict):
        """Save version check result to cache"""
        try:
            self.cache_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.cache_file, "w") as f:
                json.dump(result, f, indent=2)
        except Exception:
            pass  # Fail silently

    def _is_cache_expired(self, cached_result: dict, ttl_days: int = 7) -> bool:
        """Check if cached result has expired"""
        try:
            last_check = datetime.fromisoformat(cached_result["last_check"])
            return datetime.now() - last_check > timedelta(days=ttl_days)
        except Exception:
            return True  # Treat invalid cache as expired
