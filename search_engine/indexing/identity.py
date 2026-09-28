"""어느 문서인지를 말하는 신호. 관련도가 아니라 동일성을 다룬다.

색인 경로가 둘이다 -- `prepare.py`는 실험실 코퍼스를, `indexer.py`는 파서 산출물을
받는다. 사본이냐 아니냐는 코퍼스의 성질이지 어느 경로로 들어왔느냐의 문제가
아니므로 규칙은 한 군데에 둔다.
"""

import re
from datetime import date

# 청크 번호는 부모마다 0부터 빠짐없이 이어진다. 이 규약은 "첫 청크"를 찾는
# 곳마다 암묵으로 깔려 있었고(prepare·indexer), core가 1부터 매기는 바람에
# 612개 문서 전부 앞머리를 읽지 못한 채로 지나갔다. 규약은 코드가 지킨다.
FIRST_CHUNK_INDEX = 0


def chunk_index(row: dict) -> int:
    """청크 번호. 쪼개지 않은 문서는 번호를 적지 않으므로 첫 청크로 본다."""
    value = row.get("chunk_index")
    return FIRST_CHUNK_INDEX if value is None else value


def check_chunk_indices(indices: dict[str, list]) -> None:
    """부모마다 청크 번호가 0부터 빠짐없이 이어지는지 확인한다.

    어긋나도 조용히 넘어가면 앞머리가 빈 문자열이 될 뿐 아무 신호가 없다.
    그 조용함이 실제로 core 코퍼스를 통째로 빠뜨렸으므로 여기서 멈춘다.
    """
    for parent_id, seen in sorted(indices.items()):
        seen = sorted(FIRST_CHUNK_INDEX if v is None else v for v in seen)
        if seen != list(range(FIRST_CHUNK_INDEX, FIRST_CHUNK_INDEX + len(seen))):
            raise ValueError(
                f"chunk_index must run {FIRST_CHUNK_INDEX}..n-1 without gaps "
                f"for parent {parent_id}: {seen[:8]}"
            )


# 브라우저가 같은 파일을 두 번 내려받으면 `... (1).hwp`가 옆에 남고, 파서는 그것을
# 별개 문서로 색인한다. 본문이 글자까지 같으므로 검색은 같은 답을 두 번 싣고 창을
# 그만큼 좁힌다. 파일명이 스스로 사본이라고 말하고 있으니 추측할 것이 없다 --
# 제목+발행일 같은 추정 열쇠와 달리 서로 다른 문서를 잘못 묶을 여지가 없다.
DOWNLOAD_COPY = re.compile(r"^(?P<stem>.*?)\s*\((?P<copy>\d+)\)(?P<ext>\.[A-Za-z0-9]+)$")

# 본문 앞머리의 날짜. `2016. 3. 8.`과 `2016년 3월 8일` 둘 다 받는다.
HEAD_DATE = re.compile(r"(20\d{2})\s*[.년]\s*(\d{1,2})\s*[.월]\s*(\d{1,2})")
# 앞머리로 볼 범위. 공고문의 발신일은 서두에 있고, 뒤로 갈수록 개정 이력과
# 시행일이 섞여 어느 것이 발행일인지 본문만으로는 가릴 수 없다.
HEAD_CHARS = 600


def download_copy_key(source_path: str) -> tuple[str, int] | None:
    """내려받기 사본을 원본과 한데 묶는 열쇠와, 몇 번째 사본인지.

    `(1)`이 붙지 않은 원본은 0번으로 돌아오므로 정렬하면 언제나 원본이 먼저다.
    경로가 없으면 묶을 수 없고 None을 돌려준다 -- 그 문서는 그대로 남는다.

    열쇠에는 디렉터리가 들어간다. 사본은 원본 옆에 생기기 때문이다. 파일명만
    쓰면 `faq/113.html`과 `posts/69/113.html`처럼 번호만 같은 남남이 묶여, 수집
    코퍼스에서 FAQ 94건이 사본으로 지워졌다(2026-09-23).
    """
    directory, _, name = (source_path or "").rpartition("/")
    if not name:
        return None
    match = DOWNLOAD_COPY.match(name)
    if not match:
        return f"{directory}/{name}", 0
    return f"{directory}/{match.group('stem')}{match.group('ext')}", int(match.group("copy"))


def download_copies(rows: list[dict]) -> set[str]:
    """지워야 할 사본의 parent_id. 각 묶음에서 원본 하나만 남긴다.

    같은 열쇠에 사본만 있고 원본이 없을 수도 있으므로 번호가 가장 낮은 것을
    남긴다. 번호까지 같으면 parent_id로 갈라 실행마다 같은 것이 남게 한다.
    """
    groups: dict[str, list[tuple[int, str]]] = {}
    for row in rows:
        key = download_copy_key(row.get("source_path") or "")
        if key is None:
            continue
        groups.setdefault(key[0], []).append((key[1], row["parent_id"]))
    dropped = set()
    for members in groups.values():
        if len(members) < 2:
            continue
        members.sort()
        dropped.update(parent_id for _, parent_id in members[1:])
    return dropped


def period_hint(head: str) -> str | None:
    """문서 앞머리가 말하는 시점. 발행일이 아니라 시점 힌트다.

    파서는 파일명에서만 날짜를 읽으므로 docs-v2 52문서 중 43문서에
    `published_at`이 없다. 그 43문서 중 28문서는 본문에 날짜를 들고 있다.

    이것을 `published_at`에 넣으면 안 된다. 발행일을 아는 9문서로 맞춰
    보면 날짜까지 정확한 것은 6문서뿐이고 -- 한 문서는 앞머리에 제정일
    2013-04-12이 있어 실제 발행일 2025-09-23 대신 그것이 잡힌다 -- 대체
    판정과 사본 병합이 그 필드를 먹으므로 지금보다 나빠진다.

    연·월 눈금에서는 9문서 중 8문서가 맞는다. `_requested_period`가 그
    눈금으로만 묻기 때문에 그 부스트 전용으로 둔다. 틀린 한 문서는 부스트
    하나를 잘못 받을 뿐 필터처럼 문서를 지우지 않는다.
    """
    match = HEAD_DATE.search(head[:HEAD_CHARS])
    if not match:
        return None
    year, month, day = (int(group) for group in match.groups())
    try:
        return date(year, month, day).isoformat()
    except ValueError:
        return None
