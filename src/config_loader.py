from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


class ConfigError(ValueError):
    pass


@dataclass(frozen=True)
class AppConfig:
    taxonomy: pd.DataFrame
    serper_keywords: pd.DataFrame
    classification_keywords: pd.DataFrame
    global_excludes: pd.DataFrame
    geography: pd.DataFrame
    portals: pd.DataFrame


TAXONOMY_COLUMNS = {
    "dimension", "taxonomy_code", "parent_code", "level", "sort_order",
    "label", "is_leaf", "selectable",
}
SERPER_KEYWORD_COLUMNS = {"taxonomy_code", "keyword", "priority", "active"}
CLASSIFICATION_KEYWORD_COLUMNS = {
    "taxonomy_code", "include_keywords", "exclude_keywords",
    "positive_keywords", "negative_keywords",
}
GLOBAL_EXCLUDE_COLUMNS = {"keyword", "active"}
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
    for column in ("level", "sort_order"):
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


def _keyword_terms(value: object) -> list[str]:
    return [term.strip() for term in str(value or "").split(",") if term.strip()]


def _duplicate_terms(terms: list[str]) -> list[str]:
    normalized = pd.Series(terms, dtype=str).str.casefold()
    return sorted(set(normalized[normalized.duplicated()].tolist()))


def validate_serper_keywords(frame: pd.DataFrame, taxonomy: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    valid_codes = set(taxonomy["taxonomy_code"])
    unknown = sorted(set(result["taxonomy_code"]) - valid_codes)
    if unknown:
        raise ConfigError(f"serper_keywords.csv: taxonomy_code tidak dikenal: {', '.join(unknown)}")
    if (result["keyword"].str.strip() == "").any():
        raise ConfigError("serper_keywords.csv: keyword tidak boleh kosong")
    result["priority"] = pd.to_numeric(result["priority"], errors="coerce")
    if result["priority"].isna().any() or (result["priority"] < 1).any():
        raise ConfigError("serper_keywords.csv: priority harus integer positif")
    result["priority"] = result["priority"].astype(int)
    result["active"] = _parse_bool(result["active"], "active", "serper_keywords.csv")
    normalized = result["keyword"].str.strip().str.casefold()
    if result.assign(_keyword=normalized).duplicated(["taxonomy_code", "_keyword"]).any():
        raise ConfigError("serper_keywords.csv: keyword duplikat dalam taxonomy yang sama")

    selectable = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    active = result[result["active"]]
    counts = active.groupby("taxonomy_code")["keyword"].size()
    uncovered = sorted(code for code in selectable if counts.get(code, 0) < 3)
    if uncovered:
        raise ConfigError(
            "serper_keywords.csv: taxonomy harus memiliki minimal 3 keyword aktif: "
            + ", ".join(uncovered)
        )
    leaf_codes = set(taxonomy.loc[taxonomy["is_leaf"] & taxonomy["selectable"], "taxonomy_code"])
    excessive = sorted(code for code in leaf_codes if counts.get(code, 0) > 10)
    if excessive:
        raise ConfigError(
            "serper_keywords.csv: taxonomy leaf maksimal memiliki 10 keyword aktif: "
            + ", ".join(excessive)
        )

    terms_by_code = {
        code: set(group["keyword"].str.strip().str.casefold())
        for code, group in active.groupby("taxonomy_code", sort=False)
    }
    missing_representation: list[str] = []
    for parent in taxonomy.loc[~taxonomy["is_leaf"] & taxonomy["selectable"], "taxonomy_code"]:
        children = taxonomy.loc[
            (taxonomy["parent_code"] == parent) & taxonomy["selectable"], "taxonomy_code",
        ]
        for child in children:
            if not terms_by_code.get(parent, set()) & terms_by_code.get(child, set()):
                missing_representation.append(f"{parent}->{child}")
    if missing_representation:
        raise ConfigError(
            "serper_keywords.csv: keyword parent belum mewakili child: "
            + ", ".join(missing_representation)
        )
    return result.sort_values(["taxonomy_code", "priority"], kind="stable").reset_index(drop=True)


def validate_classification_keywords(frame: pd.DataFrame, taxonomy: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    valid_codes = set(taxonomy["taxonomy_code"])
    unknown = sorted(set(result["taxonomy_code"]) - valid_codes)
    if unknown:
        raise ConfigError(
            f"classification_keywords.csv: taxonomy_code tidak dikenal: {', '.join(unknown)}"
        )
    duplicates = sorted(result.loc[result["taxonomy_code"].duplicated(), "taxonomy_code"].unique())
    if duplicates:
        raise ConfigError(
            f"classification_keywords.csv: taxonomy_code duplikat: {', '.join(duplicates)}"
        )
    selectable = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    missing = sorted(selectable - set(result["taxonomy_code"]))
    if missing:
        raise ConfigError(
            "classification_keywords.csv: taxonomy selectable belum dikonfigurasi: "
            + ", ".join(missing)
        )
    for row in result.itertuples():
        include = _keyword_terms(row.include_keywords)
        if not include:
            raise ConfigError(
                f"classification_keywords.csv: include_keywords kosong untuk {row.taxonomy_code}"
            )
        for column in (
            "include_keywords", "exclude_keywords", "positive_keywords", "negative_keywords",
        ):
            if "|" in str(getattr(row, column)):
                raise ConfigError("classification_keywords.csv: gunakan koma, bukan |, sebagai pemisah keyword")
            terms = _keyword_terms(getattr(row, column))
            duplicate_terms = _duplicate_terms(terms)
            if duplicate_terms:
                raise ConfigError(
                    f"classification_keywords.csv: {column} duplikat untuk {row.taxonomy_code}: "
                    + ", ".join(duplicate_terms)
                )
        excluded = {term.casefold() for term in _keyword_terms(row.exclude_keywords)}
        conflict = sorted({term.casefold() for term in include} & excluded)
        if conflict:
            raise ConfigError(
                f"classification_keywords.csv: include/exclude konflik untuk {row.taxonomy_code}: "
                + ", ".join(conflict)
            )
    return result


def validate_global_excludes(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    if (result["keyword"].str.strip() == "").any():
        raise ConfigError("global_exclude_keywords.csv: keyword tidak boleh kosong")
    result["active"] = _parse_bool(result["active"], "active", "global_exclude_keywords.csv")
    normalized = result["keyword"].str.strip().str.casefold()
    if normalized.duplicated().any():
        raise ConfigError("global_exclude_keywords.csv: keyword duplikat")
    return result


def load_config(config_dir: str | Path) -> AppConfig:
    root = Path(config_dir)
    taxonomy = validate_taxonomy(_read_csv(root / "taxonomy.csv", TAXONOMY_COLUMNS))
    serper_keywords = validate_serper_keywords(
        _read_csv(root / "serper_keywords.csv", SERPER_KEYWORD_COLUMNS), taxonomy,
    )
    classification_keywords = validate_classification_keywords(
        _read_csv(root / "classification_keywords.csv", CLASSIFICATION_KEYWORD_COLUMNS), taxonomy,
    )
    global_excludes = validate_global_excludes(
        _read_csv(root / "global_exclude_keywords.csv", GLOBAL_EXCLUDE_COLUMNS),
    )
    geography = _read_csv(root / "geography.csv", GEOGRAPHY_COLUMNS)
    geography["active"] = _parse_bool(geography["active"], "active", "geography.csv")
    if not geography["group"].isin({"local", "province", "other_ntb"}).all():
        raise ConfigError("geography.csv: group hanya boleh local, province, atau other_ntb")
    portals = _read_csv(root / "portals.csv", PORTAL_COLUMNS)
    portals["active"] = _parse_bool(portals["active"], "active", "portals.csv")
    if "max_pages" in portals.columns:
        portals["max_pages"] = pd.to_numeric(portals["max_pages"], errors="coerce")
        if (portals["max_pages"].isna().any() or (portals["max_pages"] < 1).any()
                or (portals["max_pages"] % 1 != 0).any()):
            raise ConfigError("portals.csv: max_pages harus integer positif")
        portals["max_pages"] = portals["max_pages"].astype(int)
    from .portal_scrapers import PORTAL_PARSERS
    if portals["id"].duplicated().any() or not portals["id"].isin(PORTAL_PARSERS).all():
        raise ConfigError("portals.csv: id portal duplikat atau tidak didukung")
    return AppConfig(
        taxonomy, serper_keywords, classification_keywords, global_excludes, geography, portals,
    )


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


def update_hierarchical_selection(
    selected: list[str], code: str, checked: bool, taxonomy: pd.DataFrame,
) -> list[str]:
    """Apply one checkbox change while keeping parent/descendant semantics intuitive."""
    valid = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    if code not in valid:
        raise ValueError(f"Taxonomy pilihan tidak valid: {code}")
    updated = set(selected) & valid
    branch = {code, *descendants(code, taxonomy)}
    if checked:
        updated.update(branch)
    else:
        updated.difference_update(branch)
        parent_by_code = dict(zip(taxonomy["taxonomy_code"], taxonomy["parent_code"]))
        ancestor = parent_by_code.get(code, "")
        while ancestor:
            updated.discard(ancestor)
            ancestor = parent_by_code.get(ancestor, "")
    order = dict(zip(taxonomy["taxonomy_code"], taxonomy["sort_order"]))
    return sorted(updated, key=order.__getitem__)


def query_targets(selected: list[str], taxonomy: pd.DataFrame) -> list[str]:
    """Use the highest selected nodes so a selected parent supplies its own Serper keywords."""
    selectable = set(taxonomy.loc[taxonomy["selectable"], "taxonomy_code"])
    unknown = set(selected) - selectable
    if unknown:
        raise ValueError(f"Taxonomy pilihan tidak valid: {', '.join(sorted(unknown))}")
    selected_set = set(selected)
    parent_by_code = dict(zip(taxonomy["taxonomy_code"], taxonomy["parent_code"]))
    targets: set[str] = set()
    for code in selected:
        ancestor = parent_by_code.get(code, "")
        has_selected_ancestor = False
        while ancestor:
            if ancestor in selected_set:
                has_selected_ancestor = True
                break
            ancestor = parent_by_code.get(ancestor, "")
        if not has_selected_ancestor:
            targets.add(code)
    order = dict(zip(taxonomy["taxonomy_code"], taxonomy["sort_order"]))
    return sorted(targets, key=order.__getitem__)
