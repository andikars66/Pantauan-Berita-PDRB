from __future__ import annotations

import re
import unicodedata

import pandas as pd


def normalize_text(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).casefold()
    text = re.sub(r"[^\w\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _matches(text: str, term: str) -> bool:
    normalized = normalize_text(term)
    if not normalized:
        return False
    return re.search(rf"(?<!\w){re.escape(normalized)}(?!\w)", text) is not None


def geographic_relevance(
    text: object,
    geography: pd.DataFrame,
    source_context_local: bool = False,
) -> tuple[bool, str]:
    if source_context_local:
        return True, "source_context_local"
    normalized = normalize_text(text)
    active = geography[geography["active"]]
    groups = {
        group: active.loc[active["group"] == group, "term"].tolist()
        for group in ("local", "province", "other_ntb")
    }
    if any(_matches(normalized, term) for term in groups["local"]):
        return True, "local"
    province = any(_matches(normalized, term) for term in groups["province"])
    other = any(_matches(normalized, term) for term in groups["other_ntb"])
    if province and not other:
        return True, "province"
    return False, "other_ntb" if other else "no_geography"
