"""Create a minimal raw-data search corpus for embedding experiments."""

from __future__ import annotations

import argparse
import getpass
from pathlib import Path

import pandas as pd

from src.data_profile import load_data
from src.preprocess import build_search_document_a


OUTPUT_COLUMNS = [
    "record_id",
    "merchant_name",
    "original_items",
    "market_name",
    "search_document",
]


def prepare_raw_corpus(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Build the V1 corpus without normalizing or inferring source values."""
    required = ["가맹점명", "취급품목"]
    missing = [column for column in required if column not in dataframe.columns]
    if missing:
        raise KeyError("필수 컬럼이 없습니다: " + ", ".join(missing))

    result = pd.DataFrame(index=dataframe.index)
    result["record_id"] = range(len(dataframe))
    result["merchant_name"] = dataframe["가맹점명"].fillna("").astype(str)
    result["original_items"] = dataframe["취급품목"].fillna("").astype(str)
    result["market_name"] = (
        dataframe["시장명"].fillna("").astype(str)
        if "시장명" in dataframe.columns
        else ""
    )
    result["search_document"] = dataframe.apply(build_search_document_a, axis=1)
    return result[OUTPUT_COLUMNS]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="BGE-M3 원본 기준선 검색 문서 생성")
    parser.add_argument("input_path", help="원본 CSV/XLSX 경로")
    parser.add_argument(
        "--output",
        default="data/processed/search_documents_raw.csv",
        help="출력 CSV 경로",
    )
    parser.add_argument("--sheet-name", default="0", help="Excel 시트 이름 또는 번호")
    parser.add_argument(
        "--ask-password",
        action="store_true",
        help="암호화 Excel의 암호를 화면에 표시하지 않고 입력",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sheet_name: str | int = int(args.sheet_name) if args.sheet_name.isdigit() else args.sheet_name
    password = getpass.getpass("Excel 암호: ") if args.ask_password else None
    source = load_data(args.input_path, sheet_name=sheet_name, password=password)
    corpus = prepare_raw_corpus(source)

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    corpus.to_csv(output, index=False, encoding="utf-8-sig")
    print(f"생성 완료: {output.resolve()}")
    print(f"행 수: {len(corpus):,}")
    print(f"취급품목 결측 문서: {int(corpus['original_items'].eq('').sum()):,}")


if __name__ == "__main__":
    main()
