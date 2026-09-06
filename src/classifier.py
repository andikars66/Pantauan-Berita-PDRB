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


def _rule_matches(text: str, keyword: str, mode: str) -> bool:
    keyword = normalize_text(keyword)
    if not keyword:
        return False
    if mode == "token":
        return re.search(rf"(?<!\w){re.escape(keyword)}(?!\w)", text) is not None
    return keyword in text


def _score(rules: pd.DataFrame, text: str, keyword_type: str) -> float:
    relevant = rules[rules["keyword_type"] == keyword_type]
    return float(sum(
        row.weight for row in relevant.itertuples()
        if _rule_matches(text, row.keyword, row.match_mode)
    ))


def classify_text(text: object, taxonomy: pd.DataFrame, keywords: pd.DataFrame) -> list[Classification]:
    normalized = normalize_text(text)
    candidates: list[Classification] = []
    rules_by_code = {code: group for code, group in keywords.groupby("taxonomy_code", sort=False)}
    for node in taxonomy.loc[taxonomy["selectable"]].itertuples():
        rules = rules_by_code.get(node.taxonomy_code)
        if rules is None:
            continue
        include_score = _score(rules, normalized, "include")
        has_include = any(
            _rule_matches(normalized, row.keyword, row.match_mode)
            for row in rules.loc[rules["keyword_type"] == "include"].itertuples()
        )
        excluded = any(
            _rule_matches(normalized, row.keyword, row.match_mode)
            for row in rules.loc[rules["keyword_type"] == "exclude"].itertuples()
        )
        if not has_include or include_score < float(node.min_include_score) or excluded:
            continue
        positive = _score(rules, normalized, "positive")
        negative = _score(rules, normalized, "negative")
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
