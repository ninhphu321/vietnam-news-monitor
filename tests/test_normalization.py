"""Tests for core/normalization.py (roadmap V1 §6)."""

import unicodedata

from core.normalization import normalize_display_title, normalize_for_matching


def test_normalize_display_title_composes_decomposed_diacritics():
    decomposed = "Xung đột leo thang"  # "đột" with a split dấu nặng
    result = normalize_display_title(decomposed)
    assert result == "Xung đột leo thang"
    assert result == unicodedata.normalize("NFC", result)


def test_normalize_display_title_never_rewrites_wording():
    original = "Ngân hàng đang tăng trưởng cực mạnh"
    assert normalize_display_title(original) == original


def test_normalize_display_title_handles_none():
    assert normalize_display_title(None) == ""


def test_normalize_for_matching_folds_case_and_composes_unicode():
    decomposed = "XUNG ĐỘT"
    assert normalize_for_matching(decomposed) == "xung đột"


def test_normalize_for_matching_lets_precomposed_and_decomposed_forms_compare_equal():
    precomposed = "xung đột"
    decomposed = "xung đột"
    assert precomposed != decomposed  # different strings before normalization
    assert normalize_for_matching(precomposed) == normalize_for_matching(decomposed)


def test_normalize_for_matching_handles_none():
    assert normalize_for_matching(None) == ""
