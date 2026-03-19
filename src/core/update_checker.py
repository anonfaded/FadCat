"""
Update checker for FadCat
Checks for new versions asynchronously without blocking the UI
"""

from __future__ import annotations

import requests
from typing import Optional
from dataclasses import dataclass


@dataclass
class UpdateResult:
    """Result of an update check"""
    has_update: bool = False
    latest_version: Optional[str] = None
    current_version: Optional[str] = None
    error: Optional[str] = None
    
    @property
    def is_error(self) -> bool:
        return self.error is not None


class UpdateChecker:
    """Async update checker for GitHub releases"""
    
    REPO = "anonfaded/FadCat"
    RELEASES_URL = "https://github.com/anonfaded/FadCat/releases"
    RELEASES_LATEST_URL = "https://github.com/anonfaded/FadCat/releases/latest"
    TIMEOUT = 5
    
    @staticmethod
    def check_for_updates(current_version: str) -> UpdateResult:
        """
        Check for updates synchronously
        Returns UpdateResult with has_update, latest_version, and error (if any)
        """
        try:
            # Get redirect from latest release
            response = requests.head(
                UpdateChecker.RELEASES_LATEST_URL,
                allow_redirects=True,
                timeout=UpdateChecker.TIMEOUT
            )
            response.raise_for_status()
            
            # Extract tag from final URL (format: .../releases/tag/v1.0)
            final_url = response.url
            if "/releases/tag/" not in final_url:
                return UpdateResult(
                    error="Could not parse version information from GitHub"
                )
            
            latest_version = final_url.split("/releases/tag/")[-1]
            
            # Compare versions (2-digit format: major.minor)
            latest_ver = latest_version.lstrip('v')
            current_ver = current_version.lstrip('v')
            
            try:
                # Parse version parts
                latest_parts = [int(x) for x in latest_ver.split('.')[:2]]
                current_parts = [int(x) for x in current_ver.split('.')[:2]]
                
                # Pad to 2 digits if needed
                while len(latest_parts) < 2:
                    latest_parts.append(0)
                while len(current_parts) < 2:
                    current_parts.append(0)
                
                has_update = latest_parts > current_parts
                
                return UpdateResult(
                    has_update=has_update,
                    latest_version=latest_version,
                    current_version=current_version
                )
                
            except (ValueError, IndexError):
                return UpdateResult(
                    error="Could not parse version information"
                )
        
        except requests.ConnectionError:
            # No internet - silently skip
            return UpdateResult(
                error="No internet connection"
            )
        except requests.Timeout:
            # Timeout - silently skip
            return UpdateResult(
                error="Connection timeout"
            )
        except requests.RequestException as e:
            # Other request errors - silently skip
            return UpdateResult(
                error=f"Connection error: {str(e)}"
            )
