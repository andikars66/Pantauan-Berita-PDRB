import pandas as pd

from src.classifier import classify_text


def by_code(text, config):
    return {
        item.taxonomy_code: item
        for item in classify_text(
            text, config.taxonomy, config.classification_keywords, config.global_excludes,
        )
    }


def test_include_and_negative(config):
    result = by_code("Gagal panen menyebabkan produksi padi turun di Praya", config)
    assert result["LU.A.1.a"].impact == "Negatif"


def test_exclusion_veto(config):
    result = by_code("Produksi kayu terkait pembalakan liar", config)
    assert "LU.A.2" not in result


def test_multi_label_and_positive(config):
    result = by_code(
        "Proyek konstruksi pembangunan hotel baru mulai dibangun di Mandalika", config,
    )
    assert {"LU.F", "LU.I.1", "EXP.4.a"} <= set(result)
    assert result["LU.F"].impact == "Positif"


def test_ancestor_suppression(config):
    result = by_code("Sektor pertanian dan usaha pertanian mencatat produksi padi", config)
    assert "LU.A.1.a" in result
    assert "LU.A.1" not in result
    assert "LU.A" not in result


def test_parent_fallback(config):
    result = by_code("Sektor pertanian menjadi penopang ekonomi NTB", config)
    assert set(result) == {"LU.A"}


def test_neutral_without_direction(config):
    assert by_code("Produksi padi dibahas dalam rapat di Praya", config)["LU.A.1.a"].impact == "Netral"


def test_tied_impact_is_neutral(config):
    result = by_code("Panen raya tetapi gagal panen juga terjadi pada produksi padi", config)
    assert result["LU.A.1.a"].impact == "Netral"


def test_global_exclude_prevents_all_classification(config):
    assert by_code("Kecelakaan bus di Lombok Tengah mengganggu angkutan darat", config) == {}


def test_token_matching_respects_word_boundaries(config):
    result = by_code("Pengembangan perbankan digital di Lombok Tengah", config)
    assert "LU.K.1" not in result


def test_search_keyword_alone_is_not_classification_evidence(config):
    rules = config.classification_keywords.copy()
    rules.loc[rules["taxonomy_code"] == "LU.F", "include_keywords"] = "evidence khusus"
    result = classify_text(
        "Pembangunan jalan di Lombok Tengah",
        config.taxonomy,
        rules,
        pd.DataFrame(columns=["keyword", "active"]),
    )
    assert "LU.F" not in {item.taxonomy_code for item in result}
