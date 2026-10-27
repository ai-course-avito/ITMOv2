"""Server-only configuration; no credentials are exposed to the UI."""
from dataclasses import dataclass, field
import os
from urllib.parse import urlsplit

from app.errors import ReviewError


@dataclass(frozen=True)
class Settings:
    mode: str = 'demo'
    llm_url: str = ''
    llm_model: str = ''
    llm_key: str = field(default='', repr=False)

    @classmethod
    def from_env(cls):
        mode = os.environ.get('REVIEW_MODE', 'demo')
        # Demo never needs or reads a provider credential.
        if mode != 'live':
            return cls(mode=mode)
        return cls(mode=mode, llm_url=os.environ.get('REVIEW_LLM_URL', ''),
                   llm_model=os.environ.get('REVIEW_LLM_MODEL', ''),
                   llm_key=os.environ.get('REVIEW_LLM_KEY', ''))

    def validate(self):
        if self.mode not in ('demo', 'live'):
            raise ReviewError('MODEL_NOT_CONFIGURED')
        if self.mode == 'live':
            try:
                url = urlsplit(self.llm_url)
                configured = (url.scheme in ('http', 'https') and bool(url.netloc)
                              and bool(self.llm_model.strip()) and bool(self.llm_key.strip()))
            except ValueError:
                configured = False
            if not configured:
                raise ReviewError('MODEL_NOT_CONFIGURED')
