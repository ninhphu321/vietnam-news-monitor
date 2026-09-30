"""Tests for web/source_registry.py (roadmap V2 §14)."""

import json

from web.source_registry import DEFAULT_TIER, DEFAULT_WEIGHT, load_source_registry, tier_for, weight_for


def test_missing_file_yields_empty_registry_and_defaults(tmp_path):
    registry = load_source_registry(tmp_path / "nope.json")
    assert registry == {}
    assert weight_for("VnExpress", registry) == DEFAULT_WEIGHT
    assert tier_for("VnExpress", registry) == DEFAULT_TIER


def test_broken_json_falls_back_to_empty_registry(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_source_registry(path) == {}


def test_loads_configured_tier_and_weight(tmp_path):
    path = tmp_path / "reg.json"
    path.write_text(json.dumps({"CafeF": {"tier": "A", "weight": 1.0}, "Blog X": {"tier": "C", "weight": 0.4}}),
                    encoding="utf-8")
    registry = load_source_registry(path)
    assert weight_for("CafeF", registry) == 1.0
    assert weight_for("Blog X", registry) == 0.4
    assert tier_for("Blog X", registry) == "C"


def test_source_missing_from_registry_defaults_neutral(tmp_path):
    path = tmp_path / "reg.json"
    path.write_text(json.dumps({"CafeF": {"tier": "A", "weight": 1.0}}), encoding="utf-8")
    registry = load_source_registry(path)
    # A crawler added after the registry file was last edited must not
    # be silently zeroed out or crash a signal's score.
    assert weight_for("Nguồn Mới", registry) == DEFAULT_WEIGHT
    assert tier_for("Nguồn Mới", registry) == DEFAULT_TIER


def test_malformed_entry_value_falls_back_to_default(tmp_path):
    path = tmp_path / "reg.json"
    path.write_text(json.dumps({"CafeF": {"tier": 5, "weight": "high"}}), encoding="utf-8")
    registry = load_source_registry(path)
    assert weight_for("CafeF", registry) == DEFAULT_WEIGHT
    assert tier_for("CafeF", registry) == DEFAULT_TIER
