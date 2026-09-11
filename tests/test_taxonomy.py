import pandas as pd
import pytest

from src.config_loader import (
    ConfigError, descendants, expand_selection, query_targets, update_hierarchical_selection,
    validate_serper_keywords, validate_taxonomy,
)


def test_complete_taxonomy_and_official_order(config):
    taxonomy = config.taxonomy
    assert len(taxonomy) == 91
    assert taxonomy["sort_order"].is_monotonic_increasing
    assert taxonomy["taxonomy_code"].tolist()[:9] == [
        "LU.A", "LU.A.1", "LU.A.1.a", "LU.A.1.b", "LU.A.1.c",
        "LU.A.1.d", "LU.A.1.e", "LU.A.2", "LU.A.3",
    ]
    assert taxonomy[taxonomy["dimension"] == "EXP"]["taxonomy_code"].tolist()[-4:] == [
        "EXP.7.a", "EXP.7.a.1", "EXP.7.a.2", "EXP.7.b",
    ]


def test_parent_expands_all_descendants_without_duplicates(config):
    expanded = expand_selection(["LU.A", "LU.A.1.a"], config.taxonomy)
    assert expanded == ["LU.A", "LU.A.1", "LU.A.1.a", "LU.A.1.b", "LU.A.1.c", "LU.A.1.d", "LU.A.1.e", "LU.A.2", "LU.A.3"]
    assert len(expanded) == len(set(expanded))


def test_single_child_does_not_expand_siblings(config):
    assert expand_selection(["LU.A.1.a"], config.taxonomy) == ["LU.A.1.a"]


def test_serper_query_targets_keep_highest_selected_parent(config):
    selected = expand_selection(["LU.A"], config.taxonomy)
    assert query_targets(selected, config.taxonomy) == ["LU.A"]


def test_parent_checkbox_selects_descendants_and_child_clear_releases_parent(config):
    selected = update_hierarchical_selection([], "LU.A.1", True, config.taxonomy)
    assert selected == [
        "LU.A.1", "LU.A.1.a", "LU.A.1.b", "LU.A.1.c", "LU.A.1.d", "LU.A.1.e",
    ]
    selected = update_hierarchical_selection(selected, "LU.A.1.a", False, config.taxonomy)
    assert "LU.A.1" not in selected
    assert "LU.A.1.a" not in selected
    assert "LU.A.1.b" in selected


def test_invalid_parent_is_detected():
    frame = pd.DataFrame([{
        "dimension": "LU", "taxonomy_code": "LU.X", "parent_code": "LU.MISSING",
        "level": "1", "sort_order": "1", "label": "X", "is_leaf": "true",
        "selectable": "true",
    }])
    with pytest.raises(ConfigError, match="parent_code tidak ditemukan"):
        validate_taxonomy(frame)


def test_serper_parent_must_represent_each_child(config):
    keywords = config.serper_keywords.copy()
    keywords = keywords[
        ~(
            (keywords["taxonomy_code"] == "LU.A")
            & keywords["keyword"].isin({"perikanan", "nelayan"})
        )
    ]
    with pytest.raises(ConfigError, match="LU.A->LU.A.3"):
        validate_serper_keywords(keywords, config.taxonomy)


def test_serper_leaf_has_maximum_ten_keywords(config):
    keywords = config.serper_keywords.copy()
    extras = pd.DataFrame([
        {"taxonomy_code": "LU.F", "keyword": f"tambahan konstruksi {index}",
         "priority": 90 + index, "active": True}
        for index in range(4)
    ])
    keywords = pd.concat([keywords, extras], ignore_index=True)
    with pytest.raises(ConfigError, match="leaf maksimal"):
        validate_serper_keywords(keywords, config.taxonomy)


def test_comma_keyword_lists_and_legacy_delimiter_rejection(config):
    from src.config_loader import validate_classification_keywords, ConfigError
    from src.classifier import _keyword_terms
    import pytest
    assert _keyword_terms(" padi, jagung, gagal panen, ") == ["padi", "jagung", "gagal panen"]
    rules = config.classification_keywords.copy()
    rules.loc[0, "include_keywords"] = "padi|jagung"
    with pytest.raises(ConfigError, match="gunakan koma"):
        validate_classification_keywords(rules, config.taxonomy)
    rules.loc[0, "include_keywords"] = "padi, PADI"
    with pytest.raises(ConfigError, match="duplikat"):
        validate_classification_keywords(rules, config.taxonomy)
