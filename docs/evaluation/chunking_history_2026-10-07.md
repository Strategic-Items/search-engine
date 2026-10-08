# Git 청킹 변경과 질문별 개선 기록

검색 실패→성공으로 확인된 사례와 구조 개선 기록을 구분한다. 기존 단계 번호는 유지한다. 45단계 이후 수정은 날짜별 추가 기록이다.

## 확인 범위
카테고리 전달물의 비병합 커밋 전체(28개)를 조사했다. 질문 근거가 바뀐 후보 158건 중 관련 전후 변화 143건을 98개 질문에 연결했다. 구조 변화만으로 검색 성과를 만들지 않았다.

## 발표 대표 사례

- 법령 033: SPLADE 29위·dense 16위·합산 22위, 최종 반환 정답 없음 → 각주 연결 후 41단계 Hybrid 1위. 코퍼스와 설정도 변경됐다.
- 법령 038: 통제번호별 행 분리, 잘못 붙은 부칙 경로 제거. 파서 탈락→통과. 2위→1위 기록에는 라벨 재작성도 포함된다.
- 법령 111·125·143: 표 숫자와 단위를 행에 함께 보존. 검색 수정 후 재측정 없음.
- 법령 130: CAS 53/55→55/55, 물질별 구역 복구. 검색 수정 후 재측정 없음.
- 민원FAQ 025: 덮여 사라진 답변 앞부분 복원. 검색 수정 후 재측정 없음.

## 질문별 연결

| 카테고리·질문 | 청킹 변경 | 확인된 개선 | 근거 |
|---|---|---|---|
| law100-070 | 조문 맥락 복구 | 조문 제목으로 근거의 소속을 확인할 수 있습니다. 조문 맥락 없는 목록 3→0, 조문 경로 없는 칸 조각 40→0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [f2131ca](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/f2131ca) |
| law100-070 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-012 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| law100-014 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| law100-014 | 표의 조건 계층·표식 각주 연결 | 수출 대상·지역·등급과 각주 조건을 한 행에서 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-014 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-015 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| law100-019 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| law100-066 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| admin30-017 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| admin30-018 | PDF 낱말·빈 서식 경계 수정 | 본문·서식의 문맥과 낱말을 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [c80cda3](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/c80cda3) |
| law100-024 | 절 제목·조문 인용 경계 수정 | 근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [127b4d8](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/127b4d8) |
| law100-024 | 작은 대비표도 조문 쌍으로 분리 | 열별 조문 내용을 구분하여 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [6af69aa](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/6af69aa) |
| law100-024 | 표 행·각주·부속 경계 복구 | 통제번호·조건·설명을 해당 행에서 읽을 수 있습니다. 2017 세부지침 27→44청크, 파서 탈락→통과, 잘못된 부칙 경로 129→0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-028 | 절 제목·조문 인용 경계 수정 | 근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [127b4d8](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/127b4d8) |
| law100-029 | 절 제목·조문 인용 경계 수정 | 근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [127b4d8](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/127b4d8) |
| law100-042 | 절 제목·조문 인용 경계 수정 | 근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [127b4d8](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/127b4d8) |
| law100-043 | 절 제목·조문 인용 경계 수정 | 근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [127b4d8](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/127b4d8) |
| law100-044 | 절 제목·조문 인용 경계 수정 | 근거가 실제 소속 절·조문 경로에 놓이도록 구조가 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [127b4d8](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/127b4d8) |
| law100-005 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-006 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-007 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-023 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-025 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-036 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-036 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-047 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-048 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-049 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-050 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-076 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-076 | 표 행·각주·부속 경계 복구 | 통제번호·조건·설명을 해당 행에서 읽을 수 있습니다. 2017 세부지침 27→44청크, 파서 탈락→통과, 잘못된 부칙 경로 129→0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-098 | 신구대비표를 조문 쌍으로 청킹 | 같은 조문의 현행과 개정안을 한 청크에서 비교할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9c9f994](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9c9f994) |
| law100-098 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-098 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-032 | 표의 조건 계층·표식 각주 연결 | 수출 대상·지역·등급과 각주 조건을 한 행에서 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-032 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-034 | 표 행·각주·부속 경계 복구 | 통제번호·조건·설명을 해당 행에서 읽을 수 있습니다. 2017 세부지침 27→44청크, 파서 탈락→통과, 잘못된 부칙 경로 129→0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-038 | 통제번호별 행 분리와 부칙 경로 제거 | 각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과. 이전 탐색기 정답 2위 → 이후 1위 · 청크 재분할 후 정답 라벨도 재작성 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-038 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-039 | 통제번호별 행 분리와 부칙 경로 제거 | 각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-039 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-039 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-040 | 표의 조건 계층·표식 각주 연결 | 수출 대상·지역·등급과 각주 조건을 한 행에서 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-040 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-055 | 표 행·각주·부속 경계 복구 | 통제번호·조건·설명을 해당 행에서 읽을 수 있습니다. 2017 세부지침 27→44청크, 파서 탈락→통과, 잘못된 부칙 경로 129→0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-055 | 품목 키·이어지는 표·일반기준 분리 | 2010 대비표: 열N 45→0, 통제번호 없는 청크 43→1. 대비표·과태료 별표 2문서 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [bb75fbf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/bb75fbf) |
| law100-055 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-055 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-058 | 표의 조건 계층·표식 각주 연결 | 수출 대상·지역·등급과 각주 조건을 한 행에서 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-058 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-068 | 통제번호별 행 분리와 부칙 경로 제거 | 각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-068 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-068 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-082 | 통제번호별 행 분리와 부칙 경로 제거 | 각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-082 | 품목 키·이어지는 표·일반기준 분리 | 2010 대비표: 열N 45→0, 통제번호 없는 청크 43→1. 대비표·과태료 별표 2문서 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [bb75fbf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/bb75fbf) |
| law100-082 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-089 | 통제번호별 행 분리와 부칙 경로 제거 | 각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-089 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-094 | 통제번호별 행 분리와 부칙 경로 제거 | 각 통제번호와 그 해설이 같은 행 청크에 놓입니다. 2017 세부지침 27→44청크, 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| law100-094 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| admin30-012 | 표 행·각주·부속 경계 복구 | 통제번호·조건·설명을 해당 행에서 읽을 수 있습니다. 2017 세부지침 27→44청크, 파서 탈락→통과, 잘못된 부칙 경로 129→0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [9cc9c54](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/9cc9c54) |
| admin30-012 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-033 | 표 전체 각주를 행에 연결 | 조건과 생략 예외가 한 청크에 들어갑니다. 관련 표 행 44개 변경. 이전 최종 반환에 정답 없음 → 41단계 Hybrid 정답 1위 | [e1749ca](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e1749ca) |
| law100-033 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-062 | 품목 키·이어지는 표·일반기준 분리 | 2010 대비표: 열N 45→0, 통제번호 없는 청크 43→1. 대비표·과태료 별표 2문서 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [bb75fbf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/bb75fbf) |
| law100-062 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-062 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-092 | 품목 키·이어지는 표·일반기준 분리 | 2010 대비표: 열N 45→0, 통제번호 없는 청크 43→1. 대비표·과태료 별표 2문서 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [bb75fbf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/bb75fbf) |
| law100-096 | 품목 키·이어지는 표·일반기준 분리 | 2010 대비표: 열N 45→0, 통제번호 없는 청크 43→1. 대비표·과태료 별표 2문서 파서 탈락→통과. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [bb75fbf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/bb75fbf) |
| law100-041 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-052 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-069 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-069 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-075 | 부칙 뒤 붙임의 제목 경로 복구 | 표의 근거를 붙임·문서 경로로 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [709767e](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/709767e) |
| law100-035 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-056 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-074 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-077 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-077 | 첫 섹션의 짧은 앞머리 유지 | 첫 섹션의 근거와 앞 문맥을 함께 가져올 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [582b5b9](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/582b5b9) |
| law100-087 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-087 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-101 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-101 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-102 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-107 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-107 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-108 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-109 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-109 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-109 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-114 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-114 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-114 | HWP 박스 안 표 복원 | 박스에 든 표의 근거를 표 구조와 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e117272](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e117272) |
| law100-120 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-120 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-121 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-132 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-132 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-132 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-133 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-138 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-144 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-145 | 개정문·서식·넘친 칸 경계 복구 | 근거 본문과 서식의 소속 구조가 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [694d713](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/694d713) |
| law100-145 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-106 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-111 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-111 | HWP 박스 안 표 복원 | 박스에 든 표의 근거를 표 구조와 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e117272](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e117272) |
| law100-111 | 표 행에 단위·머리글 포함 | 숫자와 단위를 함께 읽을 수 있습니다. 125번은 1차·2차·3차 위반 금액의 열 의미도 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-113 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-123 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-124 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-131 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-134 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-134 | HWP 박스 안 표 복원 | 박스에 든 표의 근거를 표 구조와 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e117272](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e117272) |
| law100-137 | 법령정보센터 별표 표지 복구 | 근거가 어느 법령·별표에 속하는지 확인할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [26a43bf](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/26a43bf) |
| law100-137 | HWP 박스 안 표 복원 | 박스에 든 표의 근거를 표 구조와 함께 읽을 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e117272](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e117272) |
| law100-013 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-016 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-017 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-054 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-078 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-081 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-088 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-095 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-097 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-115 | 개정문 머리·제목 판 경계 수정 | 판·제목·본문의 경계가 바뀌어 근거를 구분할 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [07d383c](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/07d383c) |
| law100-061 | 첫 섹션의 짧은 앞머리 유지 | 첫 섹션의 근거와 앞 문맥을 함께 가져올 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [582b5b9](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/582b5b9) |
| law100-067 | 첫 섹션의 짧은 앞머리 유지 | 첫 섹션의 근거와 앞 문맥을 함께 가져올 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [582b5b9](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/582b5b9) |
| admin30-010 | 첫 섹션의 짧은 앞머리 유지 | 첫 섹션의 근거와 앞 문맥을 함께 가져올 수 있습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [582b5b9](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/582b5b9) |
| law100-027 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-057 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-103 | 관광업소 목록 경계 복구 | 별개 업소를 한 이름으로 읽는 문제를 줄였습니다. 원본의 이름·주소 줄 수가 달라 잘못된 일대일 짝짓기는 하지 않았습니다. 질문 자체의 대상 범위도 재검토해야 합니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-125 | 표 행에 단위·머리글 포함 | 숫자와 단위를 함께 읽을 수 있습니다. 125번은 1차·2차·3차 위반 금액의 열 의미도 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-128 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-130 | 누락 CAS 번호와 화학물질 구역 복구 | 원문 CAS 55개 중 53개→55개 보존, 구역 설명이 해당 물질에 맞게 바뀌었습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-136 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-142 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-143 | 표 행에 단위·머리글 포함 | 숫자와 단위를 함께 읽을 수 있습니다. 125번은 1차·2차·3차 위반 금액의 열 의미도 복구됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-147 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| law100-148 | 단위·머리글·목록·내용 유실 복구 | 단위·구역·목록 경계와 누락된 값을 근거 청크에 보존합니다. 원문 숫자 값 약 18,300개 유실 0. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| admin30-007 | 표 칸의 목록·줄바꿈·머리글 보존 | 수정 전후 본문에서 항목 경계를 구분할 수 있습니다. 검색 순위 향상은 측정하지 않았습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |
| faq30-025 | FAQ 답변 첫 조각 복구 | 답변의 도입·법적 근거가 다시 청크에 포함됐습니다. 수정 전후 검색 재측정 기록 없음 · 구조 개선 확인 | [e400e04](https://github.com/Strategic-Items/unstructured-doc-parser_ver2/commit/e400e04) |

## 별도 질문셋 사례

37단계 법령 21문항 law-v1-009: 상황허가 조문 제목 복구(f2131ca). 수정 전 BM25 54위·dense 9위·SPLADE 5위·합산 8위. 같은 질문의 수정 후 순위는 저장돼 있지 않아 현재 150문항의 특정 질문에 대신 붙이지 않았다.

## 유의할 연결

같은 문서의 다른 행이나 경로가 바뀐 경우는 질문의 직접적인 검색 성공으로 계산하지 않는다. 전후 청크 번호가 달라질 수 있어 본문 유사도로 기존 근거를 연결했다. 전체 후보와 제외 대상은 data/generated/chunking-history에 저장한다.
