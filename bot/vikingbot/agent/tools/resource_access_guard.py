"""Helpers to enforce session-scoped OpenViking resource access in tools."""

from __future__ import annotations

from typing import Any, Optional

from vikingbot.agent.tools.base import ToolContext
from vikingbot.openviking_mount.resource_access import (
    filter_ls_entries,
    filter_search_grouped_items,
    filter_uri_list,
    get_session_allowed_uris,
    is_uri_allowed,
    resolve_search_target_uri,
    should_filter_uri,
)


class ResourceAccessGuard:
    def __init__(self, allowed_uris: list[str] | None):
        self.enabled = allowed_uris is not None
        self.allowed_uris = allowed_uris or []

    @classmethod
    async def from_context(cls, tool_context: ToolContext) -> "ResourceAccessGuard":
        allowed = await get_session_allowed_uris(tool_context.session_key)
        return cls(allowed)

    def deny_message(self) -> str:
        if not self.allowed_uris:
            return "No resource access granted for this session."
        return (
            "Resource access denied. Allowed prefixes: "
            + ", ".join(self.allowed_uris)
        )

    def ensure_uri_allowed(self, uri: str) -> str | None:
        if not self.enabled:
            return None
        if should_filter_uri(uri, self.allowed_uris):
            return None
        return self.deny_message()

    def resolve_search_target(self, target_uri: Optional[str]) -> str | list[str] | None:
        if not self.enabled:
            return target_uri or ""
        resolved = resolve_search_target_uri(target_uri, self.allowed_uris)
        if resolved is None:
            return None
        if resolved == []:
            return None
        return resolved

    def filter_ls(self, entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not self.enabled:
            return entries
        return filter_ls_entries(entries, self.allowed_uris)

    def filter_grouped_search(
        self, grouped_items: dict[str, list[dict[str, Any]]]
    ) -> dict[str, list[dict[str, Any]]]:
        if not self.enabled:
            return grouped_items
        return filter_search_grouped_items(grouped_items, self.allowed_uris)

    def filter_uris(self, uris: list[str]) -> tuple[list[str], list[str]]:
        if not self.enabled:
            return uris, []
        allowed = filter_uri_list(uris, self.allowed_uris)
        denied = [uri for uri in uris if uri not in allowed]
        return allowed, denied

    def list_scope_allowed(self, uri: str) -> bool:
        if not self.enabled:
            return True
        norm_uri = uri or "viking://resources/"
        if is_uri_allowed(norm_uri, self.allowed_uris):
            return True
        from vikingbot.openviking_mount.resource_access import is_list_entry_visible

        return is_list_entry_visible(norm_uri, self.allowed_uris)

    def search_fetch_limit(self, base_limit: int) -> int:
        if not self.enabled:
            return base_limit
        from vikingbot.config.loader import load_config

        multiplier = max(1, load_config().resource_access.search_overfetch_multiplier)
        return base_limit * multiplier

    def trim_grouped_to_limit(
        self, grouped_items: dict[str, list[dict[str, Any]]], limit: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Keep top-scoring items up to limit across all groups."""
        flat: list[tuple[str, dict[str, Any]]] = []
        for item_type, items in grouped_items.items():
            for item in items:
                flat.append((item_type, item))
        flat.sort(key=lambda pair: float(pair[1].get("score", 0.0)), reverse=True)
        trimmed = flat[:limit]
        result: dict[str, list[dict[str, Any]]] = {
            "memory": [],
            "resource": [],
            "skill": [],
        }
        for item_type, item in trimmed:
            result.setdefault(item_type, []).append(item)
        return result
