from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Optional

# Where a model is called when it says nothing else
DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


@dataclass(frozen=True)
class ModelConnection:
    """How a model is reached: where, through the proxy or not, and with which key (None: the deployment's)."""

    base_url: str = DEFAULT_BASE_URL
    use_proxy: bool = True
    api_token: Optional[str] = None

    def fingerprint(self) -> Optional[str]:
        """Eight characters of the hash of the key: enough to see that it changed (versions record it), not enough to find it."""
        return hashlib.sha256(self.api_token.encode()).hexdigest()[:8] if self.api_token else None
