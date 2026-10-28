"""Shared v1 contract primitives used by the page, demo, and API layers."""

from app.contract.models import ContractError, DemoState, Page
from app.contract.pages import PAGES, page_contract

__all__ = ["ContractError", "DemoState", "Page", "PAGES", "page_contract"]
