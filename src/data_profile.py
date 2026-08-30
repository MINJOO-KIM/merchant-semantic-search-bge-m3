"""Profile Korean merchant CSV/XLSX data without modifying the source file."""

from __future__ import annotations

import argparse
import getpass
import io
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


ITEM_COLUMN = "취급품목"
MERCHANT_NAME_COLUMN = "가맹점명"
DISTRIBUTION_COLUMNS = [
    "시장분류코드",
    "시장명",
    "법정동코드",
    "카드결제여부",
    "모바일결제여부",
]
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp949", "euc-kr")
LEGACY_EXCEL_SIGNATURE = bytes.fromhex("D0CF11E0A1B11AE1")
MULTI_VALUE_PATTERN = re.compile(r"[,，;/|·、]|\s+(?:및|와|과)\s+")
AMBIGUOUS_EXACT = {
    "-",
    "--",
    ".",
    "기타",
    "기타 등",
    "기타등",
    "등",
    "외",
    "음식",
    "식품",
    "일반",
    "없음",
    "미상",
}


def load_data(
    path: str | Path,
    sheet_name: str | int = 0,
    password: str | None = None,
) -> pd.DataFrame:
    """Load a CSV or XLSX as strings so identifier leading zeroes are retained."""
    source = Path(path)
    if not source.is_file():
        raise FileNotFoundError(f"입력 파일을 찾을 수 없습니다: {source}")

    suffix = source.suffix.lower()
    if suffix == ".xlsx":
        # Some company exports use the XLSX suffix for a legacy binary XLS file.
        # Detect the content signature instead of trusting the extension alone.
        with source.open("rb") as file:
            is_legacy_xls = file.read(8) == LEGACY_EXCEL_SIGNATURE
        engine = "xlrd" if is_legacy_xls else "openpyxl"
        excel_source: Path | io.BytesIO = source
        if password:
            import msoffcrypto

            decrypted = io.BytesIO()
            with source.open("rb") as encrypted_file:
                office_file = msoffcrypto.OfficeFile(encrypted_file)
                office_file.load_key(password=password)
                office_file.decrypt(decrypted)
            decrypted.seek(0)
            engine = (
                "xlrd"
                if decrypted.read(8) == LEGACY_EXCEL_SIGNATURE
                else "openpyxl"
            )
            decrypted.seek(0)
            excel_source = decrypted
        return pd.read_excel(excel_source, sheet_name=sheet_name, dtype=str, engine=engine)
    if suffix == ".csv":
        errors: list[str] = []
        for encoding in CSV_ENCODINGS:
            try:
                return pd.read_csv(source, dtype=str, encoding=encoding, low_memory=False)
            except UnicodeDecodeError as error:
                errors.append(f"{encoding}: {error}")
        raise UnicodeError("CSV 인코딩을 판별하지 못했습니다. " + " | ".join(errors))
    raise ValueError("지원하는 파일 형식은 .csv와 .xlsx입니다.")


def _text_values(series: pd.Series) -> pd.Series:
    return series.dropna().astype(str)


def _blank_mask(series: pd.Series) -> pd.Series:
    return series.notna() & series.astype("string").str.strip().eq("")


def _display_value(value: object) -> str:
    if pd.isna(value):
        return "<NULL>"
    text = str(value)
    return "<EMPTY>" if text.strip() == "" else text


def profile_summary(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Create dataset-level and column-level profile rows."""
    row_count = len(dataframe)
    duplicate_rows = int(dataframe.duplicated().sum())
    if MERCHANT_NAME_COLUMN in dataframe.columns:
        merchant_names = _text_values(dataframe[MERCHANT_NAME_COLUMN])
        merchant_names = merchant_names[merchant_names.str.strip().ne("")]
        merchant_duplicate_rows = int(merchant_names.duplicated(keep=False).sum())
        merchant_duplicate_extra = int(merchant_names.duplicated().sum())
    else:
        merchant_duplicate_rows = pd.NA
        merchant_duplicate_extra = pd.NA

    rows: list[dict[str, object]] = [
        {
            "record_type": "dataset",
            "column": "",
            "dtype": "",
            "row_count": row_count,
            "column_count": dataframe.shape[1],
            "null_count": "",
            "empty_string_count": "",
            "missing_count": "",
            "missing_ratio": "",
            "unique_count": "",
            "duplicate_row_count": duplicate_rows,
            "merchant_name_duplicate_row_count": merchant_duplicate_rows,
            "merchant_name_duplicate_extra_count": merchant_duplicate_extra,
        }
    ]

    for column in dataframe.columns:
        series = dataframe[column]
        null_count = int(series.isna().sum())
        empty_count = int(_blank_mask(series).sum())
        missing_count = null_count + empty_count
        rows.append(
            {
                "record_type": "column",
                "column": column,
                "dtype": str(series.dtype),
                "row_count": "",
                "column_count": "",
                "null_count": null_count,
                "empty_string_count": empty_count,
                "missing_count": missing_count,
                "missing_ratio": missing_count / row_count if row_count else 0.0,
                "unique_count": int(series.nunique(dropna=True)),
                "duplicate_row_count": "",
                "merchant_name_duplicate_row_count": "",
                "merchant_name_duplicate_extra_count": "",
            }
        )
    return pd.DataFrame(rows)


def analyze_items(dataframe: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Return item counts, unique-value diagnostics, and aggregate statistics."""
    if ITEM_COLUMN not in dataframe.columns:
        raise KeyError(f"필수 분석 컬럼이 없습니다: {ITEM_COLUMN}")

    series = dataframe[ITEM_COLUMN]
    text = _text_values(series)
    stripped = text.str.strip()
    nonblank = stripped[stripped.ne("")]
    row_count = len(series)
    null_count = int(series.isna().sum())
    empty_count = int(_blank_mask(series).sum())
    multi_count = int(nonblank.str.contains(MULTI_VALUE_PATTERN, regex=True).sum())
    outer_whitespace_count = int(text.ne(stripped).sum())
    trimmed_collision_count = int(
        pd.DataFrame({"raw": text, "trimmed": stripped})
        .drop_duplicates()
        .groupby("trimmed")["raw"]
        .nunique()
        .gt(1)
        .sum()
    )

    counts = (
        series.map(_display_value)
        .value_counts(dropna=False)
        .rename_axis("item_value")
        .reset_index(name="count")
    )
    counts["ratio"] = counts["count"] / row_count if row_count else 0.0
    counts["rank"] = range(1, len(counts) + 1)
    counts = counts[["rank", "item_value", "count", "ratio"]]

    unique_rows = counts.loc[~counts["item_value"].isin(["<NULL>", "<EMPTY>"])].copy()
    unique_rows["trimmed_value"] = unique_rows["item_value"].str.strip()
    unique_rows["character_length"] = unique_rows["trimmed_value"].str.len()
    unique_rows["has_outer_whitespace"] = unique_rows["item_value"].ne(
        unique_rows["trimmed_value"]
    )
    unique_rows["has_multiple_value_delimiter"] = unique_rows["trimmed_value"].str.contains(
        MULTI_VALUE_PATTERN, regex=True
    )
    unique_rows["is_short_candidate"] = unique_rows["character_length"].le(1)
    unique_rows["is_ambiguous_candidate"] = (
        unique_rows["trimmed_value"].isin(AMBIGUOUS_EXACT)
        | unique_rows["trimmed_value"].str.fullmatch(r"기타\s*유사.*", na=False)
        | unique_rows["trimmed_value"].str.fullmatch(r".+\s*외", na=False)
    )

    stats = {
        "row_count": row_count,
        "null_count": null_count,
        "null_ratio": null_count / row_count if row_count else 0.0,
        "empty_string_count": empty_count,
        "empty_string_ratio": empty_count / row_count if row_count else 0.0,
        "null_or_empty_count": null_count + empty_count,
        "null_or_empty_ratio": (null_count + empty_count) / row_count if row_count else 0.0,
        "unique_non_null_count": int(series.nunique(dropna=True)),
        "unique_nonblank_trimmed_count": int(nonblank.nunique()),
        "multiple_value_row_count": multi_count,
        "multiple_value_row_ratio_among_nonblank": multi_count / len(nonblank) if len(nonblank) else 0.0,
        "outer_whitespace_row_count": outer_whitespace_count,
        "outer_whitespace_row_ratio_among_non_null": outer_whitespace_count / len(text) if len(text) else 0.0,
        "trimmed_spelling_collision_count": trimmed_collision_count,
        "short_candidate_unique_count": int(unique_rows["is_short_candidate"].sum()),
        "ambiguous_candidate_unique_count": int(unique_rows["is_ambiguous_candidate"].sum()),
        "min_character_length": int(nonblank.str.len().min()) if len(nonblank) else pd.NA,
        "median_character_length": float(nonblank.str.len().median()) if len(nonblank) else pd.NA,
        "max_character_length": int(nonblank.str.len().max()) if len(nonblank) else pd.NA,
    }
    return counts, unique_rows, stats


def distribution_counts(dataframe: pd.DataFrame, columns: Iterable[str]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for column in columns:
        if column not in dataframe.columns:
            continue
        counts = (
            dataframe[column]
            .map(_display_value)
            .value_counts(dropna=False)
            .rename_axis("value")
            .reset_index(name="count")
        )
        counts.insert(0, "column", column)
        counts["ratio"] = counts["count"] / len(dataframe) if len(dataframe) else 0.0
        counts["rank"] = range(1, len(counts) + 1)
        frames.append(counts[["column", "rank", "value", "count", "ratio"]])
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(
        columns=["column", "rank", "value", "count", "ratio"]
    )


def _write_csv(dataframe: pd.DataFrame, path: Path) -> None:
    dataframe.to_csv(path, index=False, encoding="utf-8-sig")


def run_profile(
    input_path: str | Path,
    output_dir: str | Path,
    sheet_name: str | int = 0,
    password: str | None = None,
) -> None:
    dataframe = load_data(input_path, sheet_name=sheet_name, password=password)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)

    summary = profile_summary(dataframe)
    item_counts, item_unique, item_stats = analyze_items(dataframe)
    distributions = distribution_counts(dataframe, DISTRIBUTION_COLUMNS)

    item_stat_rows = pd.DataFrame(
        {
            "record_type": "item_metric",
            "column": ITEM_COLUMN,
            "metric": list(item_stats),
            "metric_value": list(item_stats.values()),
        }
    )
    summary = pd.concat([summary, item_stat_rows], ignore_index=True)

    _write_csv(summary, output / "data_profile_summary.csv")
    _write_csv(item_counts, output / "item_value_counts.csv")
    _write_csv(item_unique, output / "item_unique_values.csv")
    _write_csv(distributions, output / "category_value_counts.csv")

    print(f"입력 파일: {input_path}")
    print(f"전체 크기: {len(dataframe):,}행 x {dataframe.shape[1]:,}열")
    print("컬럼: " + ", ".join(map(str, dataframe.columns)))
    print(f"완전 중복 행: {int(dataframe.duplicated().sum()):,}개")
    if MERCHANT_NAME_COLUMN in dataframe.columns:
        merchant_names = _text_values(dataframe[MERCHANT_NAME_COLUMN])
        merchant_names = merchant_names[merchant_names.str.strip().ne("")]
        duplicate_rows = int(merchant_names.duplicated(keep=False).sum())
        duplicate_extra = int(merchant_names.duplicated().sum())
        print(f"가맹점명 중복 그룹 포함 행: {duplicate_rows:,}개 (초과 중복 {duplicate_extra:,}개)")
    else:
        print(f"주의: '{MERCHANT_NAME_COLUMN}' 컬럼이 없어 중복을 계산하지 못했습니다.")

    print("\n[취급품목 통계]")
    for key, value in item_stats.items():
        print(f"- {key}: {value}")
    print("\n[취급품목 빈도 Top 50]")
    print(item_counts.head(50).to_string(index=False))
    print("\n[취급품목 unique 샘플 20개]")
    print(item_unique.head(20)[["item_value", "count"]].to_string(index=False))
    print(f"\n결과 저장 위치: {output.resolve()}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="가맹점 원본 데이터 프로파일링")
    parser.add_argument("input_path", help="분석할 .csv 또는 .xlsx 파일 경로")
    parser.add_argument("--output-dir", default="reports", help="결과 CSV 저장 폴더 (기본: reports)")
    parser.add_argument(
        "--sheet-name",
        default="0",
        help="XLSX 시트 이름 또는 0부터 시작하는 시트 번호 (기본: 0)",
    )
    parser.add_argument(
        "--ask-password",
        action="store_true",
        help="암호화된 Excel 파일의 암호를 화면에 표시하지 않고 입력",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    sheet_name: str | int = int(args.sheet_name) if args.sheet_name.isdigit() else args.sheet_name
    password = getpass.getpass("Excel 암호: ") if args.ask_password else None
    run_profile(args.input_path, args.output_dir, sheet_name, password=password)


if __name__ == "__main__":
    main()
