import pandas as pd
import pytest

from src.config_loader import ConfigError, descendants, expand_selection, validate_taxonomy


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


def test_invalid_parent_is_detected():
    frame = pd.DataFrame([{
        "dimension": "LU", "taxonomy_code": "LU.X", "parent_code": "LU.MISSING",
        "level": "1", "sort_order": "1", "label": "X", "is_leaf": "true",
        "selectable": "true", "min_include_score": "1",
    }])
    with pytest.raises(ConfigError, match="parent_code tidak ditemukan"):
        validate_taxonomy(frame)
