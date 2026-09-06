from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    taxonomy: pd.DataFrame
    keywords: pd.DataFrame
    geography: pd.DataFrame
    portals: pd.DataFrame


TAXONOMY_COLUMNS = {
    "dimension", "taxonomy_code", "parent_code", "level", "sort_order",
    "label", "is_leaf", "selectable", "min_include_score",
}
KEYWORD_COLUMNS = {
    "taxonomy_code", "keyword_type", "keyword", "weight", "match_mode", "serper_query",
}
GEOGRAPHY_COLUMNS = {"term", "group", "active"}
PORTAL_COLUMNS = {"id", "name", "url", "active"}


def _read_csv(path: Path, required: set[str]) -> pd.DataFrame:
    if not path.exists():
        raise ConfigError(f"File konfigurasi tidak ditemukan: {path.name}")
    try:
        frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    except Exception as exc:
        raise ConfigError(f"Tidak dapat membaca {path.name}: {exc}") from exc
    missing = required - set(frame.columns)
    if missing:
        raise ConfigError(f"{path.name} kehilangan kolom wajib: {', '.join(sorted(missing))}")
    return frame


def _parse_bool(series: pd.Series, field: str, filename: str) -> pd.Series:
    normalized = series.astype(str).str.strip().str.lower()
    invalid = ~normalized.isin({"true", "false", "1", "0", "yes", "no"})
    if invalid.any():
        bad = sorted(normalized[invalid].unique())
        raise ConfigError(f"{filename}: nilai boolean tidak valid pada {field}: {bad}")
    return normalized.isin({"true", "1", "yes"})


def validate_taxonomy(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["taxonomy_code"] = result["taxonomy_code"].str.strip()
    result["parent_code"] = result["parent_code"].str.strip()
    if (result["taxonomy_code"] == "").any():
        raise ConfigError("taxonomy.csv: taxonomy_code tidak boleh kosong")
    duplicates = result.loc[result["taxonomy_code"].duplicated(), "taxonomy_code"].unique()
    if len(duplicates):
        raise ConfigError(f"taxonomy.csv: taxonomy_code duplikat: {', '.join(duplicates)}")
    if not result["dimension"].isin({"LU", "EXP"}).all():
        raise ConfigError("taxonomy.csv: dimension hanya boleh LU atau EXP")
    for column in ("level", "sort_order", "min_include_score"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
        if result[column].isna().any():
            raise ConfigError(f"taxonomy.csv: {column} harus numerik")
    result["level"] = result["level"].astype(int)
    result["sort_order"] = result["sort_order"].astype(int)
    result["is_leaf"] = _parse_bool(result["is_leaf"], "is_leaf", "taxonomy.csv")
    result["selectable"] = _parse_bool(result["selectable"], "selectable", "taxonomy.csv")
    if result["sort_order"].duplicated().any():
        raise ConfigError("taxonomy.csv: sort_order harus unik untuk menjaga urutan resmi")
    codes = set(result["taxonomy_code"])
    invalid_parents = sorted({value for value in result["parent_code"] if value and value not in codes})
    if invalid_parents:
        raise ConfigError(f"taxonomy.csv: parent_code tidak ditemukan: {', '.join(invalid_parents)}")
    lookup = result.set_index("taxonomy_code")
    for row in result.itertuples():
        if row.parent_code:
            parent = lookup.loc[row.parent_code]
            if parent["dimension"] != row.dimension or int(parent["level"]) >= row.level:
                raise ConfigError(f"taxonomy.csv: relasi parent tidak valid untuk {row.taxonomy_code}")
    nodes_with_children = set(result.loc[result["parent_code"] != "", "parent_code"])
    inconsistent = result[
        result.apply(lambda row: bool(row["is_leaf"]) == (row["taxonomy_code"] in nodes_with_children), axis=1)
    ]["taxonomy_code"].tolist()
    if inconsistent:
        raise ConfigError(f"taxonomy.csv: is_leaf tidak konsisten: {', '.join(inconsistent)}")
    return result.sort_values("sort_order", kind="stable").reset_index(drop=True)


def validate_keywords(frame: pd.DataFrame, taxonomy: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    valid_codes = set(taxonomy["taxonomy_code"])
    unknown = sorted(set(result["taxonomy_code"]) - valid_codes)
    if unknown:
        raise ConfigError(f"keywords.csv: taxonomy_code tidak dikenal: {', '.join(unknown)}")
    valid_types = {"include", "exclude", "positive", "negative"}
    invalid_types = sorted(set(result["keyword_type"]) - valid_types)
    if invalid_types:
        raise ConfigError(f"keywords.csv: keyword_type tidak valid: {', '.join(invalid_types)}")
    if not result["match_mode"].isin({"phrase", "token"}).all():
        raise ConfigError("keywords.csv: match_mode hanya boleh phrase atau token")
    result["weight"] = pd.to_numeric(result["weight"], errors="coerce")
    if result["weight"].isna().any() or (result["weight"] <= 0).any():
        raise ConfigError("keywords.csv: weight harus angka positif")
    if (result["keyword"].str.strip() == "").any():
        raise ConfigError("keywords.csv: keyword tidak boleh kosong")
    result["serper_query"] = _parse_bool(result["serper_query"], "serper_query", "keywords.csv")
    selectable = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    covered = set(result.loc[result["keyword_type"] == "include", "taxonomy_code"])
    uncovered = sorted(selectable - covered)
    if uncovered:
        raise ConfigError(f"keywords.csv: taxonomy selectable tanpa include rule: {', '.join(uncovered)}")
    return result


def load_config(config_dir: str | Path) -> AppConfig:
    root = Path(config_dir)
    taxonomy = validate_taxonomy(_read_csv(root / "taxonomy.csv", TAXONOMY_COLUMNS))
    keywords = validate_keywords(_read_csv(root / "keywords.csv", KEYWORD_COLUMNS), taxonomy)
    geography = _read_csv(root / "geography.csv", GEOGRAPHY_COLUMNS)
    geography["active"] = _parse_bool(geography["active"], "active", "geography.csv")
    if not geography["group"].isin({"local", "province", "other_ntb"}).all():
        raise ConfigError("geography.csv: group hanya boleh local, province, atau other_ntb")
    portals = _read_csv(root / "portals.csv", PORTAL_COLUMNS)
    portals["active"] = _parse_bool(portals["active"], "active", "portals.csv")
    if "max_pages" in portals.columns:
        portals["max_pages"] = pd.to_numeric(portals["max_pages"], errors="coerce")
        if portals["max_pages"].isna().any() or (portals["max_pages"] < 1).any():
            raise ConfigError("portals.csv: max_pages harus integer positif")
        portals["max_pages"] = portals["max_pages"].astype(int)
    expected = {"inside_lombok", "lombok_post"}
    if set(portals.loc[portals["active"], "id"]) != expected:
        raise ConfigError("portals.csv: kedua portal MVP harus aktif dan tidak boleh ada portal lain")
    return AppConfig(taxonomy, keywords, geography, portals)


def descendants(code: str, taxonomy: pd.DataFrame) -> list[str]:
    children: dict[str, list[str]] = {}
    for row in taxonomy.itertuples():
        children.setdefault(row.parent_code, []).append(row.taxonomy_code)
    result: list[str] = []
    stack = list(reversed(children.get(code, [])))
    while stack:
        child = stack.pop()
        result.append(child)
        stack.extend(reversed(children.get(child, [])))
    order = dict(zip(taxonomy["taxonomy_code"], taxonomy["sort_order"]))
    return sorted(result, key=order.__getitem__)


def expand_selection(selected: list[str], taxonomy: pd.DataFrame) -> list[str]:
    valid = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    unknown = set(selected) - valid
    if unknown:
        raise ValueError(f"Taxonomy pilihan tidak valid: {', '.join(sorted(unknown))}")
    expanded = set(selected)
    for code in selected:
        expanded.update(descendants(code, taxonomy))
    order = dict(zip(taxonomy["taxonomy_code"], taxonomy["sort_order"]))
    return sorted(expanded, key=order.__getitem__)


def query_targets(selected: list[str], taxonomy: pd.DataFrame) -> list[str]:
    """Expand parents to deepest selectable descendants for efficient Serper queries."""
    targets: set[str] = set()
    selectable = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    for code in selected:
        desc = [item for item in descendants(code, taxonomy) if item in selectable]
        leaves = [item for item in desc if bool(taxonomy.set_index("taxonomy_code").loc[item, "is_leaf"])]
        targets.update(leaves or [code])
    order = dict(zip(taxonomy["taxonomy_code"], taxonomy["sort_order"]))
    return sorted(targets, key=order.__getitem__)
