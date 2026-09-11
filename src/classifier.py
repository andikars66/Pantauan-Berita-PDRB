from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from .geography import normalize_text


@dataclass(frozen=True)
class Classification:
    taxonomy_code: str
    dimension: str
    label: str
    sort_order: int
    include_score: float
    impact: str
    positive_score: float
    negative_score: float


def _keyword_terms(value: object) -> list[str]:
    return [term.strip() for term in str(value or "").split(",") if term.strip()]


def _rule_matches(text: str, keyword: str) -> bool:
    keyword = normalize_text(keyword)
    if not keyword:
        return False
    return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None


def _score(terms: list[str], text: str) -> float:
    return float(sum(_rule_matches(text, term) for term in terms))


def classify_text(
    text: object,
    taxonomy: pd.DataFrame,
    classification_keywords: pd.DataFrame,
    global_excludes: pd.DataFrame | None = None,
) -> list[Classification]:
    normalized = normalize_text(text)
    if global_excludes is not None and not global_excludes.empty:
        active_global = global_excludes.loc[global_excludes["active"], "keyword"].tolist()
        if any(_rule_matches(normalized, term) for term in active_global):
            return []

    candidates: list[Classification] = []
    rules_by_code = classification_keywords.set_index("taxonomy_code")
    for node in taxonomy.loc[taxonomy["selectable"]].itertuples():
        if node.taxonomy_code not in rules_by_code.index:
            continue
        rules = rules_by_code.loc[node.taxonomy_code]
        include_terms = _keyword_terms(rules["include_keywords"])
        exclude_terms = _keyword_terms(rules["exclude_keywords"])
        include_score = _score(include_terms, normalized)
        excluded = any(_rule_matches(normalized, term) for term in exclude_terms)
        if include_score == 0 or excluded:
            continue
        positive = _score(_keyword_terms(rules["positive_keywords"]), normalized)
        negative = _score(_keyword_terms(rules["negative_keywords"]), normalized)
        impact = "Positif" if positive > negative else "Negatif" if negative > positive else "Netral"
        candidates.append(Classification(
            node.taxonomy_code, node.dimension, node.label, int(node.sort_order),
            include_score, impact, positive, negative,
        ))

    # Deepest supported node wins within each ancestor branch. Unrelated branches remain multi-label.
    parent = dict(zip(taxonomy["taxonomy_code"], taxonomy["parent_code"]))
    matched = {item.taxonomy_code for item in candidates}
    suppressed: set[str] = set()
    for code in matched:
        ancestor = parent.get(code, "")
        while ancestor:
            if ancestor in matched:
                suppressed.add(ancestor)
            ancestor = parent.get(ancestor, "")
    return sorted(
        (item for item in candidates if item.taxonomy_code not in suppressed),
        key=lambda item: item.sort_order,
    )
