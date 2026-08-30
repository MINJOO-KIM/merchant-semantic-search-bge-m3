# merchant-semantic-search-bge-m3
가맹점 찾기 서비스 개선

[![Open BGE-M3 baseline in Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/MINJOO-KIM/merchant-semantic-search-bge-m3/blob/master/notebooks/bge_m3_raw_baseline_colab.ipynb)

## 현재 범위

BGE-M3 및 벡터 검색 전에 CSV/XLSX 가맹점 원본 데이터의 구조와 품질을 점검합니다.
자동 표준화, 업종 분류, 임베딩, Qdrant 연동은 아직 수행하지 않습니다.

회사 원본 파일은 `data/raw/`에 두며 Git에 커밋되지 않습니다. 원본에서 파생된
프로파일 CSV도 `reports/` 아래에서 Git 제외됩니다.

## 설치 및 실행

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.data_profile data/raw/가맹점.xlsx
```

CSV도 같은 방식으로 실행할 수 있습니다. XLSX에서 첫 시트가 아닌 시트를 읽으려면
`--sheet-name "시트명"`을 지정하고, 출력 폴더는 `--output-dir`로 바꿀 수 있습니다.
확장자는 `.xlsx`지만 내부가 구형 XLS 형식인 회사 내보내기 파일도 파일 시그니처를
확인해 자동으로 읽습니다.

```powershell
python -m src.data_profile data/raw/가맹점.csv --output-dir reports
python -m src.data_profile data/raw/가맹점.xlsx --sheet-name "원본"
python -m src.data_profile data/raw/암호화가맹점.xlsx --ask-password
```

## 산출물

- `reports/data_profile_summary.csv`: 데이터 크기, 중복, 컬럼별 dtype/결측/unique 및 취급품목 집계 통계
- `reports/item_value_counts.csv`: 취급품목 전체 빈도와 비율(터미널에는 Top 50 출력)
- `reports/item_unique_values.csv`: 취급품목 unique 값과 공백·길이·복수값·모호값 후보 진단
- `reports/category_value_counts.csv`: 주요 분류 컬럼별 값 분포

모든 CSV는 Excel에서 한글이 깨지지 않도록 UTF-8 BOM으로 저장됩니다. 결과는 집계값과
unique 값만 포함하며 사업자번호, 전화번호, 주소 등 원본 전체 행을 복사하지 않습니다.

## Search Document 준비

`src/preprocess.py`에는 다음 함수가 있습니다.

- `build_search_document_a`: `가맹점명 + 원본 취급품목`
- `build_search_document_b`: `가맹점명 + normalized_items + derived_category`
- `add_search_documents`: 원본을 변경하지 않고 복사본에 문서 컬럼 추가

B안은 파생값을 만들지 않으며, 필요한 두 컬럼이 없는 경우 명시적으로 오류를 냅니다.

## BGE-M3 원본 기준선 Colab 실험

암호화 원본에서 Colab 업로드용 최소 검색 문서를 로컬로 생성합니다. 원본 취급품목은
정규화하거나 보완하지 않으며 사업자번호, 전화번호, 주소, 좌표는 출력하지 않습니다.

```powershell
python -m src.prepare_experiment "data/raw/merchant.xlsx" --ask-password
```

생성된 `data/processed/search_documents_raw.csv`를
`notebooks/bge_m3_raw_baseline_colab.ipynb`에서 업로드해 실행합니다. `data/processed/`는
원본 파생 데이터이므로 Git에서 제외됩니다. Colab 업로드 전 회사 외부반출 정책을
확인해야 합니다.

노트북은 25개 1차 평가 질의, Top 5 기준선 결과 저장, 0·1·2 관련도 검토 템플릿,
Hit@5·Precision@5·MRR@10·nDCG@5 계산 및 시장명 Qdrant 필터 비교를 포함합니다.
평가 결과는 웹 서비스에서 직접 검색하는 데이터가 아니라 모델·데이터·검색 규칙 변경
전후의 품질을 비교하는 회귀 테스트 자료입니다.

실제 웹 검색 흐름은 다음과 같습니다.

```text
검색창 → 검색 API → 질의 임베딩/조건 필터 → Qdrant → 가맹점 상세 조회 → 결과 표시
```
