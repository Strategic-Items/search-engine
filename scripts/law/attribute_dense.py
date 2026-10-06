"""카테고리별 검색의 dense 상위 5청크에 질문별 검색과 같은 어절·구간 기여도(근사 ablation)를 붙인다.

질문 어절을 하나씩 빼고 다시 임베딩해 질문 쪽 기여도(occ)를, 청크 본문을 6어절 구간으로
나눠 하나씩 빼고 다시 임베딩해 청크 쪽 기여도(cs)를 잰다. BGE-m3-ko(Ollama)로 직접 코사인을
재서 실제 색인 점수(코사인을 (1+코사인)/2로 옮긴 값)와는 약간 다를 수 있는 근사치다.

    .venv/bin/python scripts/law/attribute_dense.py
"""

import json
import math
import re
from pathlib import Path

from search_engine.embeddings import OllamaEmbedder, embedding_text

ROOT = Path(__file__).resolve().parents[2]
EXPDIR = ROOT / "docs/presentation/question_explorer"
DETAIL = EXPDIR / "data/category-detail.js"
CATEGORIES = EXPDIR / "data/categories.js"
SEG_SIZE = 6


def tidy(s: str) -> str:
    s = re.sub(r"<br\s*/?>", " ", s, flags=re.I)
    s = re.sub(r"\\[*_]", "", s)
    s = s.replace("**", "")
    s = re.sub(r"^#+\s*", "", s)
    s = re.sub(r"\s#{1,4}\s", " ", s)
    s = s.replace("|", " ")
    s = re.sub(r"-{3,}", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def load_object(path: Path, varname: str):
    txt = path.read_text(encoding="utf-8")
    m = re.search(rf"var {varname}=(\{{.*?\}});", txt, re.S)
    if not m:
        raise ValueError(f"{varname} not found in {path}")
    return json.loads(m.group(1)), m.span(1), txt


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb)


def chunks(words: list[str], n: int) -> list[list[str]]:
    return [words[i : i + n] for i in range(0, len(words), n)]


def main() -> None:
    cath, cath_span, detail_txt = load_object(DETAIL, "CATH")
    catb, _, _ = load_object(DETAIL, "CATB")
    catd, _, _ = load_object(CATEGORIES, "CATD")

    qtext = {(setk, r["i"]): r["q"] for setk, rows in catd.items() for r in rows}
    embedder = OllamaEmbedder()

    total = sum(len(qs) for qs in cath.values())
    done = 0
    for setk, questions in cath.items():
        for qid, qd in questions.items():
            done += 1
            dn = qd.get("dn")
            if not dn:
                continue
            query = qtext[(setk, qid)]
            words = query.split()

            texts = [query] + [" ".join(words[:i] + words[i + 1 :]) for i in range(len(words))]
            chunk_at = []
            chunk_segs = []
            for hit in dn:
                title, body = catb[hit["c"]]
                body_t = tidy(body)
                cwords = body_t.split()
                segs = chunks(cwords, SEG_SIZE)
                chunk_at.append(len(texts))
                texts.append(embedding_text(title, body_t))
                seg_at = []
                pos = 0
                for seg in segs:
                    remaining = cwords[:pos] + cwords[pos + len(seg) :]
                    seg_at.append(len(texts))
                    texts.append(embedding_text(title, " ".join(remaining)))
                    pos += len(seg)
                chunk_segs.append((segs, seg_at))

            embs = embedder.embed(texts)
            qv = embs[0]
            word_vs = embs[1 : 1 + len(words)]

            base = []
            d_rows = [[] for _ in words]
            for hi, hit in enumerate(dn):
                cv = embs[chunk_at[hi]]
                b = cosine(qv, cv)
                base.append(round(b, 3))
                for wi, wv in enumerate(word_vs):
                    d_rows[wi].append(round(b - cosine(wv, cv), 4))
                segs, seg_at = chunk_segs[hi]
                cs = []
                for seg, at in zip(segs, seg_at):
                    drop = round(b - cosine(qv, embs[at]), 4)
                    cs.append([" ".join(seg), drop])
                hit["cs"] = cs

            qd["occ"] = {"w": words, "base": base, "d": d_rows}
            print(f"[{done}/{total}] {setk}-{qid} 완료", flush=True)

    new_cath = json.dumps(cath, ensure_ascii=False, separators=(",", ":"))
    new_txt = detail_txt[: cath_span[0]] + new_cath + detail_txt[cath_span[1] :]
    DETAIL.write_text(new_txt, encoding="utf-8")
    print(f"저장: {DETAIL}")


if __name__ == "__main__":
    main()
