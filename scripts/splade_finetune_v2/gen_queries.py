"""원격 vLLM(30B)으로 청크마다 질의를 만들고, 같은 모델로 검증한다. 이어하기 가능."""
import asyncio, json, re, sys, time, httpx
D = "/private/tmp/claude-501/-Users-jeongbin-git-searchEngine/b71074ab-b8c9-4f2a-a981-afa2931fdbd2/scratchpad/gen/"
env = {}
for l in open("/Users/jeongbin/git/searchEngine/.env"):
    if "=" in l and not l.startswith("#"): k, v = l.split("=", 1); env[k.strip()] = v.strip()
BASE, MODEL, KEY = env["CHAT_BASE_URL_OVERRIDE"].rstrip("/"), env["CHAT_MODEL_OVERRIDE"], env.get("CHAT_API_KEY", "")
OUT = D + (sys.argv[2] if len(sys.argv) > 2 else "generated.jsonl"); LIMIT = int(sys.argv[1]) if len(sys.argv) > 1 else 10**9
COMMON = """아래는 대한민국 전략물자·무역·수출통제 관련 공고·고시·민원서식·FAQ·참고자료의 일부입니다.
본문만으로 답할 수 있는 검색 질문을 만드세요. 규칙:
- 질문만 읽어도 어떤 제도·고시·서식·사안에 관한 것인지 알 수 있게 주제어(제도명, 고시명, 품목명, 대상 등)를 반드시 넣으세요. "이 조건", "해당 품목"처럼 대상이 빠진 질문은 안 됩니다.
- 본문의 문장을 그대로 베끼지 말고 다른 표현을 쓰세요.
- 본문에 없는 사실이나 숫자를 지어내지 마세요. 숫자는 본문에 있는 것만 쓰세요.
- "이 문서", "본문", "위 글", 사람 이름은 쓰지 마세요.
- 제목만 보고도 답이 나오는 질문은 피하세요.
- 서로 겹치는 질문을 만들지 마세요."""
PA = COMMON + """
다음 4개를 만드세요.
- short: 검색창에 치는 짧은 질문(20자 안팎).
- scenario: 구체적인 상황을 2문장으로 설명하는 질문.
- detail: 본문의 세부 조건(기간, 서류, 금액, 조항 번호, 대상 등) 하나를 정확히 묻는 질문.
- why: 규정의 이유·예외·적용 범위를 묻는 질문.
JSON만 출력: {"short":"...","scenario":"...","detail":"...","why":"..."}
"""
PB = COMMON + """
다음 4개를 만드세요.
- colloquial: 실무자가 구어체로 묻는 질문(반말에 가깝게).
- keyword: 핵심어 2~4개만 나열한 검색어(조사 없이).
- compare: 본문 속 두 개념·절차·대상의 차이나 관계를 묻는 질문.
- procedure: 어떤 순서나 방법으로 해야 하는지 묻는 질문.
JSON만 출력: {"colloquial":"...","keyword":"...","compare":"...","procedure":"..."}
"""
PV = """아래 본문과 질문 목록이 있습니다. 질문마다 판정하세요.
- answerable: 본문만으로 답할 수 있는가.
- specific: 질문만 읽어도 어떤 제도·고시·사안인지 알 수 있는가(대상이 빠진 모호한 질문이면 false).
- consistent: 질문에 쓰인 숫자·고유명사가 모두 본문에 근거하는가.
JSON 배열만 출력: [{"i":1,"answerable":true,"specific":true,"consistent":true}, ...]

본문:
%s

질문:
%s"""
sem = asyncio.Semaphore(8)
async def chat(cl, prompt, temp, tries=4):
    for t in range(tries):
        try:
            async with sem:
                r = await cl.post(BASE + "/chat/completions", json={"model": MODEL, "temperature": temp, "max_tokens": 900,
                    "messages": [{"role": "user", "content": prompt}], "chat_template_kwargs": {"enable_thinking": False}})
            r.raise_for_status(); return r.json()["choices"][0]["message"]["content"]
        except Exception as e:
            await asyncio.sleep(2 * (t + 1))
    return None
def pj(txt, kind):
    if not txt: return None
    m = re.search(r"\[.*\]" if kind == "list" else r"\{.*\}", txt, re.S)
    try: return json.loads(m.group(0))
    except Exception: return None
async def one(cl, r, fout, stats):
    body = f"제목: {r['title']}\n유형: {r['source_type']}\n\n{r['body'][:3000]}"
    qs = []
    for P, temp in ((PA, 0.7), (PB, 0.8)):
        j = pj(await chat(cl, P + "\n" + body, temp), "obj")
        if j: qs += [{"type": k, "q": v.strip()} for k, v in j.items() if isinstance(v, str) and len(v.strip()) >= 4]
    seen = set(); uniq = []
    for x in qs:
        key = re.sub(r"\s", "", x["q"])
        if key not in seen: seen.add(key); uniq.append(x)
    qs = uniq
    if qs:
        listing = "\n".join(f"{i+1}. {x['q']}" for i, x in enumerate(qs))
        v = pj(await chat(cl, PV % (body, listing), 0.0), "list") or []
        vm = {d.get("i"): d for d in v if isinstance(d, dict)}
        for i, x in enumerate(qs):
            d = vm.get(i + 1, {}); x["ok"] = bool(d.get("answerable") and d.get("specific") and d.get("consistent")); x["verdict"] = d
    stats["chunks"] += 1; stats["queries"] += len(qs); stats["ok"] += sum(x.get("ok", False) for x in qs)
    fout.write(json.dumps({"id": r["id"], "parent_id": r["parent_id"], "twins": r["twins"], "queries": qs}, ensure_ascii=False) + "\n"); fout.flush()
    if stats["chunks"] % 25 == 0: print(time.strftime("%H:%M:%S"), dict(stats), flush=True)
async def main():
    rows = [json.loads(l) for l in open(D + "pool_final.jsonl")][:LIMIT]
    try: done = {json.loads(l)["id"] for l in open(OUT)}
    except FileNotFoundError: done = set()
    todo = [r for r in rows if r["id"] not in done]; print("todo", len(todo), "done", len(done), flush=True)
    stats = {"chunks": 0, "queries": 0, "ok": 0}
    from collections import Counter; stats = Counter(stats)
    async with httpx.AsyncClient(timeout=httpx.Timeout(60, connect=15), limits=httpx.Limits(max_keepalive_connections=0), headers={"Authorization": f"Bearer {KEY}"} if KEY else {}) as cl:
        q = asyncio.Queue()
        for r in todo: q.put_nowait(r)
        async def worker(fout):
            while True:
                try: r = q.get_nowait()
                except asyncio.QueueEmpty: return
                await one(cl, r, fout, stats)
        with open(OUT, "a") as fout: await asyncio.gather(*(worker(fout) for _ in range(8)))
    print("완료", dict(stats), flush=True)
asyncio.run(main())
