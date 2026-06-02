"""Tests for session resource access helpers."""

from vikingbot.openviking_mount.resource_access import (
    allowed_uris_from_grants,
    filter_search_grouped_items,
    grants_from_api_payload,
    is_uri_allowed,
    resolve_search_target_uri,
    ResourceGrant,
)


def test_grants_from_api_payload_single_object():
    payload = {
        "resource_name": "财务部",
        "resource_item": ["财务1部", "财务2部"],
    }
    grants = grants_from_api_payload(payload)
    assert len(grants) == 1
    assert grants[0].resource_name == "财务部"
    assert grants[0].resource_items == ("财务1部", "财务2部")


def test_allowed_uris_from_grants():
    grants = [
        ResourceGrant(resource_name="财务部", resource_items=("财务1部", "财务2部")),
    ]
    uris = allowed_uris_from_grants(grants)
    assert uris == [
        "viking://resources/财务部/财务1部",
        "viking://resources/财务部/财务2部",
    ]


def test_is_uri_allowed_prefix_match():
    allowed = [
        "viking://resources/财务部/财务1部",
        "viking://resources/财务部/财务2部",
    ]
    assert is_uri_allowed("viking://resources/财务部/财务1部/report.md", allowed)
    assert not is_uri_allowed("viking://resources/财务部/财务3部", allowed)


def test_resolve_search_target_uri_defaults_to_allowed_list():
    allowed = [
        "viking://resources/财务部/财务1部",
        "viking://resources/财务部/财务2部",
    ]
    resolved = resolve_search_target_uri("", allowed)
    assert resolved == allowed


def test_resolve_search_target_uri_scopes_parent_directory():
    allowed = [
        "viking://resources/财务部/财务1部",
        "viking://resources/财务部/财务2部",
    ]
    resolved = resolve_search_target_uri("viking://resources/财务部", allowed)
    assert resolved == allowed


def test_resolve_search_target_uri_denies_out_of_scope():
    allowed = ["viking://resources/财务部/财务1部"]
    assert resolve_search_target_uri("viking://resources/市场部", allowed) is None


def test_filter_search_grouped_items_resources_only():
    allowed = ["viking://resources/财务部/财务1部"]
    grouped = {
        "memory": [{"uri": "viking://user/default/memories/a.md", "score": 1.0}],
        "resource": [
            {"uri": "viking://resources/财务部/财务1部/a.md", "score": 0.9},
            {"uri": "viking://resources/财务部/财务2部/b.md", "score": 0.8},
        ],
        "skill": [],
    }
    filtered = filter_search_grouped_items(grouped, allowed)
    assert len(filtered["memory"]) == 1
    assert len(filtered["resource"]) == 1
    assert filtered["resource"][0]["uri"].endswith("财务1部/a.md")
