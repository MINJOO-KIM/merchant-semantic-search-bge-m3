"""Search-document builders for later embedding experiments."""

from __future__ import annotations

import pandas as pd


def _clean_text(value: object) -> str:
    """Return a display-safe string without changing the source dataframe."""
    if pd.isna(value):
        return ""
    return str(value).strip()


def build_search_document_a(
    row: pd.Series,
    merchant_name_column: str = "가맹점명",
    item_column: str = "취급품목",
) -> str:
    """Build option A: merchant name plus the original item value."""
    name = _clean_text(row.get(merchant_name_column))
    item = _clean_text(row.get(item_column))
    if item:
        return f"가맹점명: {name}. 취급품목: {item}."
    return f"가맹점명: {name}."


def build_search_document_b(
    row: pd.Series,
    merchant_name_column: str = "가맹점명",
    normalized_items_column: str = "normalized_items",
    derived_category_column: str = "derived_category",
) -> str:
    """Build option B once its two derived columns have been created upstream.

    This function deliberately does not normalize or classify any values.
    """
    required = [merchant_name_column, normalized_items_column, derived_category_column]
    missing = [column for column in required if column not in row.index]
    if missing:
        raise KeyError(
            "B안 Search Document에 필요한 컬럼이 없습니다: " + ", ".join(missing)
        )

    name = _clean_text(row[merchant_name_column])
    items = _clean_text(row[normalized_items_column])
    category = _clean_text(row[derived_category_column])
    return f"가맹점명: {name}. 정규화 취급품목: {items}. 파생 카테고리: {category}."


def add_search_documents(
    dataframe: pd.DataFrame,
    version: str = "A",
    output_column: str = "search_document",
) -> pd.DataFrame:
    """Return a copy with search documents; never mutate the supplied dataframe."""
    result = dataframe.copy()
    normalized_version = version.upper()
    if normalized_version == "A":
        builder = build_search_document_a
    elif normalized_version == "B":
        builder = build_search_document_b
    else:
        raise ValueError("version은 'A' 또는 'B'여야 합니다.")

    result[output_column] = result.apply(builder, axis=1)
    return result
