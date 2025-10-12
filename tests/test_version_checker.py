import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch

from test_mcp.utils.version_checker import VersionChecker


class TestVersionChecker:
    def test_current_version_detection(self):
        """Test current version detection"""
        checker = VersionChecker()
        version = checker.get_current_version()
        assert version != "0.0.0"  # Should find actual version

    @patch("httpx.get")
    def test_pypi_api_integration(self, mock_get):
        """Test PyPI API integration"""
        # Mock successful response
        mock_response = Mock()
        mock_response.json.return_value = {"info": {"version": "2.1.0"}}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Create checker with fresh cache file to avoid cached results
        with tempfile.TemporaryDirectory() as tmp_dir:
            checker = VersionChecker()
            checker.cache_file = Path(tmp_dir) / "test_cache.json"
            result = checker.check_for_update()

            assert result is not None
            assert result["latest_version"] == "2.1.0"
            assert "has_update" in result

    def test_cache_functionality(self):
        """Test caching behavior"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            cache_file = Path(tmp_dir) / "version_check.json"

            # Test cache save/load
            test_result = {
                "current_version": "2.0.0",
                "latest_version": "2.1.0",
                "has_update": True,
                "last_check": datetime.now().isoformat(),
            }

            checker = VersionChecker()
            checker.cache_file = cache_file
            checker._save_cache(test_result)

            loaded = checker._load_cache()
            assert loaded == test_result

    def test_error_handling(self):
        """Test graceful error handling"""
        checker = VersionChecker(timeout=0.001)  # Force timeout
        result = checker.check_for_update()
        # Should not raise exception, may return None or cached result
        assert result is None or isinstance(result, dict)
