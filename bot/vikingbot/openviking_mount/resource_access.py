"""Session-scoped resource access via third-party API."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlencode

import httpx
from loguru import logger

from vikingbot.config.schema import ResourceAccessConfig, SessionKey

VIKING_RESOURCE_ROOT = "viking://resources"


@dataclass(frozen=True)
class ResourceGrant:
    """One resource namespace grant from the third-party API."""

    resource_name: str
    resource_items: tuple[str, ...]

    def to_allowed_uris(self) -> list[str]:
        base = f"{VIKING_RESOURCE_ROOT}/{self.resource_name}".rstrip("/")
        if not self.resource_items:
            return [f"{base}/"]
        uris: list[str] = []
        for item in self.resource_items:
            item = str(item).strip().strip("/")
            if not item:
                continue
            uris.append(f"{base}/{item}")
        return uris


def normalize_viking_uri(uri: str) -> str:
    """Normalize a Viking URI for prefix comparisons."""
    value = (uri or "").strip()
    if not value:
        return VIKING_RESOURCE_ROOT
    if value.startswith("resources/") or value.startswith("/resources/"):
        value = value.lstrip("/")
        return f"{VIKING_RESOURCE_ROOT}/{value[len('resources/'):]}".rstrip("/")
    if not value.startswith("viking://"):
        return value.rstrip("/")
    return value.rstrip("/")


def grants_from_api_payload(payload: Any) -> list[ResourceGrant]:
    """Parse third-party API JSON into resource grants."""
    if payload is None:
        return []

    if isinstance(payload, list):
        items = payload
    elif isinstance(payload, dict):
        for key in ("data", "result","results", "resources", "items"):
            nested = payload.get(key)
            if isinstance(nested, list):
                items = nested
                break
        else:
            items = [payload]
    else:
        return []

    grants: list[ResourceGrant] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("resource_name")
            or item.get("resourceName")
            or item.get("name")
            or ""
        )
        name = str(name).strip()
        if not name:
            continue
        raw_items = item.get("resource_item") or item.get("resourceItem") or item.get("items") or []
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raw_items = [raw_items]
        resource_items = tuple(str(value).strip() for value in raw_items if str(value).strip())
        grants.append(ResourceGrant(resource_name=name, resource_items=resource_items))
    return grants


def allowed_uris_from_grants(grants: list[ResourceGrant]) -> list[str]:
    uris: list[str] = []
    for grant in grants:
        uris.extend(grant.to_allowed_uris())
    # Preserve order while deduplicating
    seen: set[str] = set()
    ordered: list[str] = []
    for uri in uris:
        norm = normalize_viking_uri(uri)
        if norm in seen:
            continue
        seen.add(norm)
        ordered.append(norm)
    return ordered


def is_resource_uri(uri: str) -> bool:
    norm = normalize_viking_uri(uri)
    return norm == VIKING_RESOURCE_ROOT or norm.startswith(f"{VIKING_RESOURCE_ROOT}/")


def is_uri_allowed(uri: str, allowed_uris: list[str]) -> bool:
    """Return True when uri is under one of the allowed resource prefixes."""
    if not allowed_uris:
        return False
    norm = normalize_viking_uri(uri)
    for prefix in allowed_uris:
        base = normalize_viking_uri(prefix)
        if norm == base or norm.startswith(f"{base}/"):
            return True
    return False


def is_list_entry_visible(entry_uri: str, allowed_uris: list[str]) -> bool:
    """Allow entries under granted paths or ancestor directories of grants."""
    if is_uri_allowed(entry_uri, allowed_uris):
        return True
    norm = normalize_viking_uri(entry_uri)
    for prefix in allowed_uris:
        base = normalize_viking_uri(prefix)
        if base.startswith(f"{norm}/") or base == norm:
            return True
    return False


def should_filter_uri(uri: str, allowed_uris: list[str]) -> bool:
    """Only enforce grants on viking://resources paths."""
    if not is_resource_uri(uri):
        return True
    return is_uri_allowed(uri, allowed_uris)


def resolve_search_target_uri(
    target_uri: Optional[str],
    allowed_uris: list[str],
) -> Optional[str | list[str]]:
    """
    Resolve OpenViking search target_uri from session grants.

    Returns None when the requested scope is not allowed.
    """
    if not allowed_uris:
        return []

    requested = (target_uri or "").strip()
    if not requested:
        return allowed_uris if len(allowed_uris) > 1 else allowed_uris[0]

    norm = normalize_viking_uri(requested)
    if not is_resource_uri(norm):
        return requested

    if is_uri_allowed(norm, allowed_uris):
        return requested

    scoped = [prefix for prefix in allowed_uris if is_uri_allowed(prefix, [norm])]
    if scoped:
        return scoped if len(scoped) > 1 else scoped[0]

    return None


def filter_ls_entries(entries: list[dict[str, Any]], allowed_uris: list[str]) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for entry in entries:
        uri = str(entry.get("uri") or "")
        if is_list_entry_visible(uri, allowed_uris):
            filtered.append(entry)
    return filtered


def filter_search_grouped_items(
    grouped_items: dict[str, list[dict[str, Any]]],
    allowed_uris: list[str],
) -> dict[str, list[dict[str, Any]]]:
    filtered: dict[str, list[dict[str, Any]]] = {
        "memory": [],
        "resource": [],
        "skill": [],
    }
    for item_type, items in grouped_items.items():
        bucket = filtered.setdefault(item_type, [])
        for item in items:
            uri = str(item.get("uri") or "")
            if item_type == "resource":
                if should_filter_uri(uri, allowed_uris):
                    bucket.append(item)
            else:
                bucket.append(item)
    return filtered


def filter_uri_list(uris: list[str], allowed_uris: list[str]) -> list[str]:
    return [uri for uri in uris if should_filter_uri(uri, allowed_uris)]


@dataclass
class _CacheEntry:
    allowed_uris: list[str]
    expires_at: float


class ResourceAccessService:
    """Fetch and cache allowed resource URIs per session."""

    def __init__(self, config: ResourceAccessConfig):
        self.config = config
        self._cache: dict[str, _CacheEntry] = {}

    def session_key_value(self, session_key: SessionKey) -> str:
        return session_key.chat_id

    async def get_allowed_uris(self, session_key: SessionKey) -> list[str]:
        if not self.config.enabled or not self.config.api_url:
            return []

        cache_key = self.session_key_value(session_key)
        now = time.time()
        cached = self._cache.get(cache_key)
        if cached and cached.expires_at > now:
            return list(cached.allowed_uris)

        grants = await self._fetch_grants(cache_key)
        allowed = allowed_uris_from_grants(grants)
        ttl = max(0, int(self.config.cache_ttl_seconds))
        self._cache[cache_key] = _CacheEntry(allowed_uris=allowed, expires_at=now + ttl)
        return allowed

    async def _fetch_grants(self, session_key_value: str) -> list[ResourceGrant]:
        base_url = self.config.api_url.rstrip("/")
        query = urlencode({self.config.session_key_param: session_key_value})
        url = f"{base_url}?{query}" if "?" not in base_url else f"{base_url}&{query}"

        headers: dict[str, str] = {}
        if self.config.auth_header and self.config.auth_token:
            headers[self.config.auth_header] = self.config.auth_token

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except Exception as exc:
            logger.warning(f"Resource access API failed for session {session_key_value}: {exc}")
            if self.config.deny_on_error:
                return []
            raise

        grants = grants_from_api_payload(payload)
        logger.info(
            f"Resource access for session {session_key_value}: "
            f"{len(grants)} grant(s), {len(allowed_uris_from_grants(grants))} URI(s)"
        )
        return grants

    def invalidate(self, session_key: SessionKey) -> None:
        self._cache.pop(self.session_key_value(session_key), None)


_service: ResourceAccessService | None = None
_service_config: ResourceAccessConfig | None = None


def get_resource_access_service(config: ResourceAccessConfig) -> ResourceAccessService:
    global _service, _service_config
    if _service is None or _service_config is not config:
        _service = ResourceAccessService(config)
        _service_config = config
    return _service


async def get_session_allowed_uris(session_key: SessionKey | None) -> list[str] | None:
    """
    Return allowed URIs for the session, or None when access control is disabled.
    """
    if session_key is None:
        return None

    from vikingbot.config.loader import load_config

    config = load_config()
    access_config = getattr(config, "resource_access", None)
    if access_config is None or not access_config.enabled:
        return None

    service = get_resource_access_service(access_config)
    return await service.get_allowed_uris(session_key)
