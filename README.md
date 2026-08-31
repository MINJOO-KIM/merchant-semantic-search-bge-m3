# 한국어 가맹점 의미 검색 — BGE-M3 PoC

## 지금 볼 파일

| 목적 | 파일 | 사용 시점 |
|---|---|---|
| 현재 실험 실행 | [전체 데이터 비교 노트북](notebooks/bge_m3_full_corpus_comparison.ipynb) | 원본·보강본을 같은 조건으로 검색·평가 |
| Qdrant 검색 참고 | [원본 기준선 노트북](notebooks/bge_m3_raw_baseline_colab.ipynb) | 기존 원본 검색·시연 흐름 확인. 평가에는 최신 비교 노트북 사용 |
| 회의 준비 | [최신 회의 요약](docs/meeting_summary.md) | Git 공유용. 진행 내용·결론·팀 합의 사항 |
| 결과 확인 | [최신 비교 결과 요약](docs/results_summary.md) | Git 공유용. 상호 익명화 사례·잠정 지표 |
| 결과 파일 찾기 | [로컬 보고서 안내](reports/README.md) | CSV·ZIP·판정표 위치 확인 |

`docs/`의 요약 문서는 Git에 포함합니다. `reports/`의 상세 자료는 **작업한 PC에만 있는 Git 제외 자료**이므로 GitHub에서 해당 링크가 열리지 않는 것이 정상입니다. 실제 데이터·판정표는 회사가 승인한 공유 경로로 전달하세요.

수동 입력 전용 노트북은 중복 기능이므로 `reports/archive/2026-08-31/`에 보관했습니다. 현재 사용하거나 커밋할 필요가 없습니다.

## 현재 상태와 범위

- 원본 CSV/XLSX 프로파일링과 검색 문서 생성 구현.
- 전체 문서에 원본 품목 기반의 보수적인 보강 규칙 적용. 원본과 record_id 보존.
- Colab에서 BGE-M3 dense로 원본·보강본 비교 실행.
- 장소 조건을 제외한 품목·자연어 의도와 상호명 검색 평가.
- 이번 비교는 정규화 벡터의 전체 코사인 검색을 사용. Qdrant 운영 성능 검증과 분리.
- 판정 출처·미확인을 보존한 잠정 지표 계산. 모델 학습/파인튜닝·NICE 공식 분류·웹 서비스는 구현하지 않음.

전체 가맹점 속성 후보와 검색 관련도는 다릅니다. `relevance`는 **query_id + record_id 조합**에 붙이며, 회사 가맹점 전체의 확정 정답을 만든 것은 아닙니다.

## 실행 순서

### 1. 로컬 설치·원본 점검

```powershell
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m src.data_profile "data/raw/merchant.xlsx" --ask-password
python -m src.prepare_experiment "data/raw/merchant.xlsx" --ask-password
```

CSV도 지원합니다. 암호가 없으면 `--ask-password`를 빼세요. Excel 시트 선택은 `--sheet-name`, 프로파일 출력 위치는 `--output-dir`로 지정합니다.

### 2. 전체 문서 보강 규칙 실행

```powershell
python -m src.enrich_corpus data/processed/search_documents_raw.csv --output reports/full_corpus_v1/annotations.json
```

이 명령의 출력은 **JSON**입니다. CSV/입력 ZIP까지 만드는 명령은 아닙니다. 현재 Colab 입력 ZIP은 로컬 실험 산출물로 따로 준비되어 있습니다. 보고서 생성·패키징용 일회성 스크립트도 `reports/`에 보관되어 Git에는 포함되지 않습니다.

### 3. Colab 비교 실행

1. `notebooks/bge_m3_full_corpus_comparison.ipynb`를 Colab에 새로 엽니다.
2. GPU 런타임에서 1~6번을 순서대로 실행합니다.
3. 2번에서 로컬 `reports/full_corpus_v1/full_corpus_comparison_input.zip` 하나를 업로드합니다.
4. 5번에서 내려받는 `comparison_results_bundle.zip`을 보관합니다.
5. 새 검색 후보의 관련도를 검토한 뒤 동일 판정으로 두 버전을 비교합니다.

입력 ZIP이 없는 새 환경에서는 회사 승인 경로로 전달받아야 합니다. Git clone만으로 회사 데이터나 검토 완료 라벨은 복구되지 않습니다. 로컬 코드 수정은 이미 열린 Colab 사본에 자동 반영되지 않습니다.

`requirements.txt`는 로컬 데이터 처리용입니다. BGE-M3 실행 패키지는 노트북의 설치 셀에서 설치합니다.

### 4. 테스트

```powershell
python -m unittest discover -s tests -v
```

## Python 파일 역할

| 파일 | 역할 |
|---|---|
| [data_profile.py](src/data_profile.py) | 파일 로딩, 결측·중복·품목 빈도 등 프로파일링 |
| [preprocess.py](src/preprocess.py) | 행을 검색 문장으로 조립. B안 함수는 구조만 제공 |
| [prepare_experiment.py](src/prepare_experiment.py) | 최소 컬럼의 원본 검색 문서 CSV 생성 |
| [enrich_corpus.py](src/enrich_corpus.py) | 품목 규칙, 근거·미판정 상태, 보강 문서 생성 |
| [compare_metrics.py](src/compare_metrics.py) | 최신 비교용 함수. 검색 결과와 qrels를 받아 P@5·Top1·Hit@5·MRR@5 계산 |
| [evaluate_draft.py](src/evaluate_draft.py) | 초기 판정 형식의 불확실성 진단용 보조 도구. 일상 실행 불필요 |
| `tests/test_*.py` | 보강 원본 보존·미판정 처리·평가 계산 검증 |

`compare_metrics.py`는 CLI가 아니라 함수 모듈입니다. 최신 Colab 노트북에는 같은 평가 로직이 포함되어 있어 별도 Python 파일 업로드가 필요 없습니다.

## 평가 기준

- 2: 명확히 일치한다는 판정.
- 1: 일부 관련성이 있으나 정확한 일치는 아님.
- 0: 불일치 판정.
- 빈칸: 정보 부족으로 미판정. **모름을 1이나 0으로 채우지 않음.**
- AI 제안·상호 기반 추론·사용자 진술·외부 확인을 출처로 구분.

현재 지표는 2만 정확 일치로 계산합니다. 미판정을 모두 불일치/일치로 가정한 두 시나리오와 판정 보유율을 함께 기록합니다. 이는 신뢰구간이 아니며, AI 라벨 자체의 오류를 반영한 범위도 아닙니다.

품목·의도 질의와 특정 상호명 질의를 분리합니다. 현재는 nDCG와 Recall을 비교 지표로 사용하지 않습니다. 기존 기준선 노트북의 7~8번은 과거 라벨·지표 기준이므로 현재 평가에 사용하지 마세요.

보강 규칙이나 유사도 점수로 정답을 만들지 않습니다. 이미 본 질의는 개발용이며, 팀 모델 선정에는 공통 데이터·새 질의·동일 판정 기준이 필요합니다.

## 저장과 커밋

**Git에 포함:** 소스 코드, 테스트, 실행 출력 없는 노트북, 이 README, 실제 가맹점 식별 정보를 제외한 `docs/` 회의·결과 요약.

**Git에서 제외:** `data/raw/`, `data/processed/`, `reports/` 아래의 회사 데이터·보강본·질의/판정 CSV·실험 ZIP·회의자료·보고서·보관 파일. 디렉터리 유지용 `.gitkeep`만 예외입니다.

- 원본을 덮어쓰지 않고 파생 파일로 저장합니다.
- 비밀번호·사업자번호·전화번호·주소를 코드에 넣지 않습니다.
- Colab 업로드와 Drive 저장은 회사 보안 정책을 확인합니다.
- 노트북은 실행 결과에 회사 데이터가 포함될 수 있으므로 출력 제거 후 커밋합니다.
- `git add -f reports/...`로 제외 규칙을 우회하지 마세요.
