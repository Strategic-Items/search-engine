"""학습용 청크 풀: core+docs에서 평가 근거 청크(와 같은 본문 사본)를 뺀다. holdout은 쓰지 않는다."""
import glob, json, re, collections
R = "/Users/jeongbin/git/searchEngine/"
rows = []
for p in (R + "data/generated/docs-v2/review-corpus/docs.jsonl", R + "data/generated/core.jsonl"):
    rows += [json.loads(l) for l in open(p)]
ev = set(); gold_parents = set()
for f in glob.glob(R + "data/queries_*.jsonl"):
    for l in open(f):
        q = json.loads(l)
        for g in q.get("evidence_groups") or []: ev.update(g)
        for e in q.get("evidence") or []: ev.add(e["chunk_id"])
def norm(t): return re.sub(r"<[^>]+>|&lt;|&gt;|[\s#*|\\\-:]", "", t)
def sh(t, k=30, step=10): return {t[i:i + k] for i in range(0, max(1, len(t) - k), step)}
N = [norm(r["body"]) for r in rows]; S = [sh(t) for t in N]
id2i = {r["id"]: i for i, r in enumerate(rows)}
# 같은 본문 사본 묶음: 조각을 60% 이상 공유하는 쌍만 사본으로 본다(머리말 등 흔한 조각 하나로 묶지 않는다)
inv = collections.defaultdict(list)
for i, st in enumerate(S):
    for g in st: inv[g].append(i)
parent = list(range(len(rows)))
def find(x):
    while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
    return x
pair = collections.Counter()
for g, idxs in inv.items():
    if 1 < len(idxs) <= 40:
        for a in range(len(idxs)):
            for b in range(a + 1, len(idxs)): pair[(idxs[a], idxs[b])] += 1
for (a, b), c in pair.items():
    if c >= 0.6 * min(len(S[a]), len(S[b])): parent[find(a)] = find(b)
groups = collections.defaultdict(list)
for i in range(len(rows)): groups[find(i)].append(i)
banned_groups = {find(id2i[c]) for c in ev if c in id2i}
def table_ratio(b):
    lines = [l for l in b.splitlines() if l.strip()]
    return sum(len(l) for l in lines if l.lstrip().startswith("|")) / max(1, sum(len(l) for l in lines))
pool = []; stats = collections.Counter()
for gid, idxs in groups.items():
    if gid in banned_groups: stats["평가 근거/사본 제외"] += len(idxs); continue
    i = idxs[0]; r = rows[i]
    if len(r["body"]) < 200: stats["너무 짧음"] += 1; continue
    tr = table_ratio(r["body"])
    if tr > 0.5: stats["표 위주(>50%)"] += 1; continue
    pool.append({"id": r["id"], "title": r["title"], "body": r["body"], "twins": [rows[j]["id"] for j in idxs[1:]],
                 "source_type": r.get("source_type", "?"), "table_ratio": round(tr, 2)})
with open("/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen/pool.jsonl", "w") as f:
    for r in pool: f.write(json.dumps(r, ensure_ascii=False) + "\n")
print("전체 청크", len(rows), "| 묶음", len(groups), "| 풀", len(pool))
print(dict(stats)); print(collections.Counter(r["source_type"] for r in pool).most_common())
print("본문 길이 중앙값", sorted(len(r["body"]) for r in pool)[len(pool) // 2], "| 사본 있는 풀 항목", sum(bool(r["twins"]) for r in pool))
