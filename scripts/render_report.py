# -*- coding: utf-8 -*-
"""qa-tc-studio — TC 데이터(tc_data.json)를 인터랙티브 HTML 리포트/대시보드로 렌더링.

사용:
    python render_report.py [tc_data.json] [-o OUTDIR]

출력:
    <OUTDIR>/report.html      단독 파일(결과는 브라우저 localStorage에 저장)
    <OUTDIR>/dashboard.html   공유 서버용(Pass/Fail·비고를 serve_dashboard.py 서버에 저장)

tc_data.json 스키마: schema/tc_data.schema.json 참조.
위험도/확신도/설계기법/자동화 값은 case에 있으면 그대로, 없으면 규칙(휴리스틱)으로 자동 태깅한다.
"""
import os, sys, json, html, re, argparse
from collections import Counter, defaultdict

# ---------- 판정 규칙(고지용) ----------
RULES = {
 "위험도": [("High", "삭제(실삭제)·정상 등록/저장(데이터 변경)·매핑 저장·비밀번호/계정 잠금·권한/미로그인·업로드·실제 발송/갱신"),
          ("Medium", "유효성 검증(필수/형식/중복/범위)·인라인 수정·토글·설정 저장·연동/제외/일괄"),
          ("Low", "목록 렌더·컬럼 확인·조회/검색/필터·이력 열람·새로고침·UI 확인")],
 "확신도": [("High", "소스에 실제 메시지/명시 로직이 있어 근거가 명확 (대부분)"),
          ("Med", "드래그 매핑·복잡 팝업(Partial), 서버측 검증, 외부 데이터 의존, 즉시 적용, 라우터 레벨"),
          ("Low", "실제 발송/학습/서빙, 파괴적 작업, 오디오, 시각 판정 등 런타임·정성 판단(자동화 N)")],
 "Playwright 자동화": [("가능", "표준 UI 조작으로 재현: 클릭/입력/검증 메시지 확인/CRUD"),
          ("부분", "드래그 매핑·색상 피커·파일 업로드·차트/시각·외부 데이터 의존"),
          ("불가", "실제 알람·메신저 발송, 장시간 잡, 라이선스 갱신, 오디오 재생, 다국어 시각 확인")],
 "설계기법": [("경계값분석", "유효/무효 경계의 ON·OUT 짝"), ("동등분할", "형식·중복 등 같은 처리 그룹 대표값"),
          ("결정테이블", "여러 조건 조합→결과 매핑"), ("상태전이", "토글/삭제확인/등록→수정→삭제 등 상태 변화"),
          ("조합", "타입·옵션·탭 조합 커버리지"), ("네거티브", "필수값 미입력·잘못된 입력 실패 경로"),
          ("명세기반", "소스/화면 명세 기반 정상 동작")],
}
DEFAULT_GAPS = [
 ("임계값·기본값 적정성", "임계치·주기 등 '적정 수치'는 소스에 없음", "기획/운영 확인 후 경계값 TC 보강"),
 ("실제 발송/실행 결과", "실제 알람/메신저 발송, 학습/서빙 결과 정확성은 런타임 검증", "수동/별도 검증"),
 ("외부 연동 정합성", "외부 시스템/데이터에 의존하는 화면", "연동 환경에서 QA 확인"),
 ("성능·응답시간", "목록/대량 처리 SLA 기준 미정", "성능 기준 협의 후 비기능 TC"),
 ("사용성(UI/UX)", "색상·레이아웃·조작 체감은 정성 판단", "QA 실기기 탐색"),
 ("보안 경계", "세션 만료·접근 제어·권한 경계 정책", "보안 정책 확정 후 TC화"),
]
DEFAULT_CHARTERS = [
 ("대량 데이터", "목록/항목이 수천 건", "정렬·검색·페이징·매핑 성능"),
 ("특수·경계 입력", "이모지·매우 긴 문자열·특수문자", "저장/표시/검색 깨짐·잘림"),
 ("동시 편집", "두 세션이 같은 항목 수정 후 저장", "충돌 처리 동작"),
 ("상태 전이", "등록→수정→삭제·토글 반복 중 새로고침/뒤로가기", "상태 유지·정합성"),
 ("권한/세션", "세션 만료 직후 저장, 일반 권한 접근", "리다이렉트·버튼 비활성·서버 차단"),
]

# ---------- 자동 태깅 휴리스틱(값이 없을 때만 사용) ----------
def h_techniques(func, exp):
    s = func + " " + exp; t = []
    if any(k in s for k in ["범위", "최소", "초과", "이상", "이하", "0 보다", "크거나 같", "min", "max", "길이"]): t.append("경계값분석")
    if any(k in s for k in ["미입력", "공백", "비우", "없이 저장", "미선택", "미첨부"]): t.append("네거티브")
    if any(k in s for k in ["형식", "유효", "이메일", "전화", "IP", "중복", "이미 등록", "already"]): t.append("동등분할")
    if any(k in s for k in ["토글", "활성", "스위치", "부팅", "잠금", "적용"]): t.append("상태전이")
    if any(k in s for k in ["확인창", "삭제하시겠습니까", "취소", "Cancel"]): t.append("상태전이")
    if any(k in s for k in ["타입", "옵션", "탭", "조합"]): t.append("조합")
    if not t: t = ["명세기반"]
    out = []
    for x in t:
        if x not in out: out.append(x)
    return out

def h_risk(section, func):
    if section == "삭제": return "High"
    if any(k in func for k in ["정상 등록", "정상 추가", "정상 저장", "매핑 저장", "비밀번호", "계정 잠금", "리다이렉트", "실제", "갱신", "업로드"]): return "High"
    if section in ("목록", "이력", "조회", "재생", "초기화") or any(k in func for k in ["컬럼 확인", "진입", "렌더", "검색", "필터", "새로고침", "조회", "열람", "펼치기", "탭 전환", "탭 확인", "옵션 확인", "선택 시", "정렬 표시", "듣기"]): return "Low"
    return "Medium"

def h_conf(note):
    n = note or ""
    if "자동화 N" in n or "시각" in n or "오디오" in n: return "Low"
    if any(k in n for k in ["Partial", "서버 검증", "외부", "의존", "즉시 적용", "라우터", "파괴적", "APM"]): return "Med"
    return "High"

def h_pw(note):
    n = note or ""
    if "자동화 N" in n: return "불가"
    if "Partial" in n: return "부분"
    return "가능"

def with_nav(mname, cat, screen, proc, section, enable=True):
    """절차 맨 앞에 '화면으로 이동' 단계를 자동 추가(단독 재현 가능). 권한/이미 이동 단계는 제외."""
    if not enable: return proc
    lines = proc.split("\n")
    if not lines: return proc
    if section == "권한": return proc
    head = lines[0]
    if ("화면으로 이동" in head) or ("직접 접속" in head) or ("직접 진입" in head) or ("로그아웃" in head):
        return proc
    path = mname + (f" > {cat}" if cat and cat != mname else "") + f" > {screen}"
    out = [f"1. {path} 화면으로 이동한다."]
    for ln in lines:
        m = re.match(r"^(\s*)(\d+)\.(.*)$", ln)
        out.append(f"{m.group(1)}{int(m.group(2))+1}.{m.group(3)}" if m else ln)
    return "\n".join(out)

# ---------- 데이터 로드 → TC 리스트 ----------
def build_tcs(data):
    id_prefix = data.get("id_prefix", "TC")
    auto_nav = data.get("auto_nav", True)
    tcs, menus_meta = [], []
    for menu in data.get("menus", []):
        mname, mcode = menu["name"], menu["code"]
        groups = menu.get("groups", [])
        menus_meta.append((mname, mcode, groups))
        for g in groups:
            gcode = g.get("code", "")
            for scr in g.get("screens", []):
                scode = scr["code"]
                for i, c in enumerate(scr.get("cases", [])):
                    section = c.get("section", "")
                    func = c.get("func", "")
                    pre = c.get("precondition", "")
                    proc = c.get("process", "")
                    exp = c.get("expected", "")
                    note = c.get("note", "")
                    tid = "-".join(x for x in [id_prefix, mcode, gcode, scode] if x) + f"-{i+1:03d}"
                    tcs.append({
                        "id": tid, "menu": mname, "mcode": mcode, "category": g["name"], "screen": scr["name"],
                        "section": section, "func": func, "precondition": pre,
                        "process": with_nav(mname, g["name"], scr["name"], proc, section, auto_nav),
                        "expected": exp, "note": note,
                        "techniques": c.get("techniques") or h_techniques(func, exp),
                        "risk": c.get("risk") or h_risk(section, func),
                        "confidence": c.get("confidence") or h_conf(note),
                        "pw": c.get("automation") or h_pw(note),
                        "method": c.get("method", ""),
                    })
    return tcs, menus_meta

# ---------- 렌더 ----------
RISKC = {"High": "#d64545", "Medium": "#e0a01e", "Low": "#8a94a6"}
CONFC = {"High": "#2e9e5b", "Med": "#3b7dd8", "Low": "#8a94a6"}
PWC = {"가능": "#2e9e5b", "부분": "#e0a01e", "불가": "#9aa0a6"}

def esc(x): return html.escape(str(x))
def badge(t, c, fg="#fff"): return f'<span class="b" style="background:{c};color:{fg}">{esc(t)}</span>'
def mchip(lb, v, c): return f'<span class="mc"><i style="background:{c}"></i>{esc(lb)} {esc(v)}</span>'

def render(data):
    title = data.get("title", "테스트케이스 리포트")
    summary_label = data.get("summary_label", "종합")
    tcs, menus_meta = build_tcs(data)
    gaps = [tuple(x) for x in data.get("gaps", DEFAULT_GAPS)]
    charters = [tuple(x) for x in data.get("charters", DEFAULT_CHARTERS)]

    # 검증
    errors, warnings, seen = [], [], set()
    for t in tcs:
        if t["id"] in seen: errors.append(f"{t['id']}: 중복 ID")
        seen.add(t["id"])
        if not t["expected"].strip(): errors.append(f"{t['id']}: 기대결과 공란")
        if not t["process"].strip().startswith("1."): warnings.append(f"{t['id']}: 절차 스텝형식 확인")
        if t["confidence"] == "Low": warnings.append(f"{t['id']}: 확신도 Low → QA 확인")

    cats, cat_menu = [], {}
    by_cat, by_screen, screen_of_cat = defaultdict(list), defaultdict(list), defaultdict(list)
    for mname, mcode, groups in menus_meta:
        for g in groups:
            cats.append(g["name"]); cat_menu[g["name"]] = mcode
            screen_of_cat[g["name"]] = [s["name"] for s in g.get("screens", [])]
    for t in tcs:
        by_cat[t["category"]].append(t); by_screen[(t["category"], t["screen"])].append(t)
    menu_has_data = {mc for _, mc, _ in menus_meta}

    P = []
    P.append(f"<div class='wrap'><header><h1>{esc(title)}</h1>"
             "<div class='hbtn'><button onclick='exportCSV()'>결과 내보내기(CSV)</button>"
             "<label class='imp'>결과 불러오기(CSV)<input type='file' accept='.csv' onchange='importCSV(event)' hidden></label>"
             "<button onclick='resetStatus()' class='ghost'>초기화</button></div></header>"
             "<p class='sub'>AI 초안 · QA 검증 · Pass/Fail/N·T·검증방법·비고 는 이 페이지에서 입력하면 저장됩니다</p>")

    # 대메뉴 바 (종합 + 데이터 메뉴들)
    menus_top = [(summary_label, "SUMMARY")] + [(m[0], m[1]) for m in menus_meta]
    mb = []
    for nm, code in menus_top:
        has = (code == "SUMMARY") or (code in menu_has_data)
        on = " on" if code == "SUMMARY" else ""
        if has:
            mb.append(f"<button class='mb{on}' data-code='{code}' onclick=\"showMenu('{code}',this)\">{esc(nm)}</button>")
        else:
            mb.append(f"<button class='mb' data-code='{code}' disabled>{esc(nm)} <span class='soon-badge'>준비중</span></button>")
    P.append("<nav class='menunav'>" + "".join(mb) + "</nav>")

    tabs = ["소개", "종합 결과"] + cats + ["설계맵", "판정 기준"]
    P.append("<nav class='tabs'>")
    for i, tb in enumerate(tabs):
        mc = cat_menu.get(tb, "SUMMARY")
        P.append(f"<button class='tab{' on' if i==0 else ''}' data-menu='{mc}' onclick=\"showTab('{esc(tb)}',this)\">{esc(tb)}</button>")
    P.append("</nav>")

    # 소개
    steps = [("소스코드·기획서·매뉴얼 대조", "제품 소스코드·기획서·매뉴얼·실제 화면 등 근거 자료를 대조해 필드·버튼·검증 메시지 확인(추측 최소화)"),
             ("화면별 섹션 분해", "각 화면을 목록/등록/수정/삭제/조회/권한 등 섹션으로 분해"),
             ("TC 작성", "일반 사용자 관점 번호 절차(1.~를 클릭한다) + 실제 제품 메시지로 기대결과"),
             ("메타 태깅", "설계기법·위험도·확신도·자동화 가능여부를 규칙으로 부여"),
             ("단일 정본화 (JSON)", "모든 TC를 구조화된 tc_data.json 한 파일로 관리 — 내용(데이터)과 화면(렌더러)을 분리"),
             ("자체 검증", "AI가 만든 TC를 Python 스크립트가 규칙으로 점검 — 중복 ID·공란·형식(사람/AI 판단 아님)"),
             ("산출물 생성", "같은 JSON에서 HTML 리포트·공유 대시보드·CSV로 자동 변환"),
             ("QA 실행·보완", "Pass/Fail·비고·검증방법 기록, 필터로 우선순위, Gap·탐색차터로 보완")]
    flow = "".join((f"<div class='fstep'><span class='fn'>{i+1}</span><b>{esc(a)}</b><span class='fd'>{esc(d)}</span></div>"
                    + ("<div class='farrow'>▼</div>" if i < len(steps)-1 else "")) for i, (a, d) in enumerate(steps))
    P.append("<section class='pane on' data-tab='소개'><div class='intro'>"
             f"<h2>이 리포트는?</h2><p>테스트케이스를 <b>대메뉴 &gt; 카테고리 &gt; 화면</b> 구조로 정리하고, "
             "수동 테스트 실행(Pass/Fail·비고)과 설계 근거 추적을 한 곳에서 하도록 만든 리포트입니다. 상단 <b>대메뉴 바</b>에서 전환하세요.</p>"
             "<h2>단일 정본(JSON)으로 관리하는 이유</h2>"
             "<div class='expl'>모든 TC는 <b>tc_data.json</b> 한 파일을 정본으로 두고, 이 리포트/대시보드/CSV는 전부 그 JSON에서 생성됩니다. "
             "<b>내용(데이터)과 화면(렌더러)을 분리</b>했기에:"
             "<ul class='use' style='margin-top:6px'>"
             "<li><b>한 곳만 수정</b> → 모든 산출물에 반영 (HTML을 직접 손대지 않음)</li>"
             "<li><b>기계 검증 가능</b> → 중복 ID·공란·형식을 스크립트가 자동 점검</li>"
             "<li><b>재사용·이식</b> → 같은 도구로 다른 제품도 리포트화 (내용만 교체)</li>"
             "<li><b>결과가 TC ID에 고정</b> → 메뉴 순서를 바꿔도 Pass·비고·검증방법이 안 깨짐</li>"
             "</ul></div>"
             "<h2>어떻게 설계했나 — 진행 순서</h2><div class='flow'>" + flow + "</div>"
             "<h2>구성</h2><div class='tabgrid'>"
             "<div class='tcard'><b>종합 결과</b><div>진행율·Pass/Fail 집계·검증방법(자동/수동)·자동화 커버리지·위험도/확신도 분포·Fail 목록</div></div>"
             "<div class='tcard'><b>대메뉴 · 카테고리</b><div>상단 대메뉴 선택 → 카테고리별 화면 TC + Pass/Fail·비고·검증방법 + 필터</div></div>"
             "<div class='tcard'><b>설계맵</b><div>확신도 히트맵·기능 분류 트리·Gap 분석·탐색 차터</div></div>"
             "<div class='tcard'><b>판정 기준</b><div>위험도·확신도·설계기법·자동화 태깅 규칙</div></div></div>"
             "<h2>두 개의 축 — 결과 vs 검증방법</h2>"
             "<div class='expl'><b>결과(Pass/Fail/N·T)</b> = 테스트가 통과했는가. <b>검증방법(🤖자동/✋수동)</b> = 누가 확인했는가. "
             "<u>서로 독립</u>이라 조합이 가능합니다 — 예: <b>Pass + 🤖자동</b>(Playwright가 통과 확인) vs <b>Pass + ✋수동</b>(QA가 직접 통과 확인). "
             "나중에 “이거 누가 확인한 거지?”가 한눈에 구분됩니다. <span class='hint'>· N·T = 아직 안 함/보류(Not Tested)</span></div>"
             "<h2>사용법</h2><ul class='use'>"
             "<li>각 TC의 <b>[Pass][Fail][N·T]</b> 클릭·<b>비고</b> 입력 → 자동 저장</li>"
             "<li><b>검증방법</b> 버튼(🤖 자동 / ✋ 수동)으로 '누가 확인했는지' 표시 — Playwright 자동확인분은 🤖로 미리 표기됨(클릭하면 —→✋→🤖 순환)</li>"
             "<li><b>필터</b>: 자동확인 / 수동확인 / 미확인 / 자동화 가능·불가 / Fail만 / 미실행만 으로 골라보기</li>"
             "<li>상단 <b>[결과 내보내기(CSV)]</b> 백업·공유(TC ID·결과·검증방법·비고 포함), <b>[결과 불러오기(CSV)]</b> 복원, <b>[초기화]</b> Pass/Fail 리셋(비고는 유지)</li>"
             "<li>공유는 <b>serve_dashboard.py</b> 로 dashboard.html 을 띄우면 결과·비고·검증방법이 서버에 저장돼 여러 명이 공유(단독 report.html은 브라우저에 저장)</li>"
             "</ul></div></section>")

    # 종합 결과
    rd = Counter(t['risk'] for t in tcs); cd = Counter(t['confidence'] for t in tcs); NT = max(1, len(tcs))
    P.append("<section class='pane' data-tab='종합 결과'>")
    P.append("<h2>전체 진행 현황</h2><div id='overall'></div>")
    P.append("<h3>검증 방법 <span class='hint'>🤖 Playwright 자동 확인 / ✋ 수동 확인</span></h3><div id='methsum'></div>")
    P.append("<h3>카테고리별</h3><table class='sum'><thead><tr><th>카테고리</th><th>총</th><th>Pass</th><th>Fail</th><th>N/T</th><th>미실행</th><th>진행율</th></tr></thead><tbody id='catsum'></tbody></table>")
    P.append("<h3>자동화(Playwright) 커버리지</h3><div id='pwsum'></div>")
    P.append("<h3>위험도 · 확신도 분포 (설계 기준)</h3><div class='dist'>")
    P.append("<div class='dbox'><div class='dt'>위험도 <span class='hint'>실패 시 업무 영향</span></div>")
    for k in ['High', 'Medium', 'Low']:
        P.append(f"<div class='drow'><span class='dl'>{k}</span><span class='dbar'><i style='width:{rd.get(k,0)/NT*100:.0f}%;background:{RISKC[k]}'></i></span><span class='dn'>{rd.get(k,0)}</span></div>")
    P.append("</div><div class='dbox'><div class='dt'>확신도 <span class='hint'>TC가 소스대로 정확한지 신뢰</span></div>")
    for k in ['High', 'Med', 'Low']:
        P.append(f"<div class='drow'><span class='dl'>{k}</span><span class='dbar'><i style='width:{cd.get(k,0)/NT*100:.0f}%;background:{CONFC[k]}'></i></span><span class='dn'>{cd.get(k,0)}</span></div>")
    P.append("</div></div>")
    P.append("<div class='expl'><b>위험도</b> = 기능이 잘못되면 업무 타격 크기. <b>확신도</b> = 이 TC가 소스대로 정확한지 신뢰. "
             "<u>위험 High + 확신 Low = 최우선 정밀 검토</u>. 규칙은 [판정 기준] 탭 참고.</div>")
    P.append("<h3 style='color:#d64545'>Fail 목록 (이슈)</h3><div id='faillist' class='faillist'>아직 Fail 없음</div>")
    P.append(f"<p class='hint'>자체 검증(스크립트): Error <b style='color:#d64545'>{len(errors)}</b> · Warning <b style='color:#e0a01e'>{len(warnings)}</b></p>")
    P.append("</section>")

    def status_ctrl(tid):
        return (f"<span class='st' data-id='{tid}'>"
                f"<button class='s p' data-v='Pass' onclick=\"setSt('{tid}','Pass')\">Pass</button>"
                f"<button class='s f' data-v='Fail' onclick=\"setSt('{tid}','Fail')\">Fail</button>"
                f"<button class='s n' data-v='N/T' onclick=\"setSt('{tid}','N/T')\">N/T</button></span>"
                f"<button class='mth' data-id='{tid}' onclick=\"cycleM('{tid}')\" title='검증 방법 (자동/수동) — 클릭해 전환'>—</button>")

    for cat in cats:
        P.append(f"<section class='pane' data-tab='{esc(cat)}' data-menu='{cat_menu[cat]}'>")
        P.append(f"<h2>{esc(cat)} <span class='cnt'>{len(by_cat[cat])} TC</span></h2>")
        P.append("<div class='filt'>필터: "
                 "<button class='fb on' data-f='all' onclick='filt(this)'>전체</button>"
                 "<button class='fb' data-f='m-auto' onclick='filt(this)'>🤖 자동확인</button>"
                 "<button class='fb' data-f='m-manual' onclick='filt(this)'>✋ 수동확인</button>"
                 "<button class='fb' data-f='m-none' onclick='filt(this)'>미확인</button>"
                 "<button class='fb' data-f='pw-가능' onclick='filt(this)'>자동화 가능</button>"
                 "<button class='fb' data-f='pw-불가' onclick='filt(this)'>자동화 불가</button>"
                 "<button class='fb' data-f='st-Fail' onclick='filt(this)'>Fail만</button>"
                 "<button class='fb' data-f='st-none' onclick='filt(this)'>미실행만</button></div>")
        for sn in screen_of_cat[cat]:
            rows = by_screen[(cat, sn)]
            P.append(f"<h3 class='scr'>{esc(sn)} <span class='cnt'>{len(rows)}</span></h3>")
            for t in rows:
                techs = "기법: " + ", ".join(t["techniques"])
                P.append(f"<div class='tc' id='row-{t['id']}' data-risk='{t['risk']}' data-conf='{t['confidence']}' data-pw='{t['pw']}'><div class='tc-main'>")
                P.append("<div class='tc-h'>" + status_ctrl(t['id'])
                         + f" <span class='id'>{esc(t['id'])}</span> <span class='sec2'>[{esc(t['section'])}]</span> <b>{esc(t['func'])}</b></div>")
                P.append("<div class='tc-b'>"
                         + f"<div><span class='k'>사전조건</span><span class='v'>{esc(t['precondition'])}</span></div>"
                         + f"<div><span class='k'>절차</span><span class='v proc'>{esc(t['process']).replace(chr(10),'<br>')}</span></div>"
                         + f"<div><span class='k'>기대결과</span><span class='v'>{esc(t['expected'])}</span></div>"
                         + f"<div class='meta'>{mchip('자동화',t['pw'],PWC[t['pw']])}<span class='tk'>{esc(techs)}{(' · '+esc(t['note'])) if t['note'] else ''}</span></div></div></div>")
                P.append(f"<div class='tc-note'><div class='nlab'>비고</div><textarea class='note-in' data-id='{t['id']}' oninput=\"setNote('{t['id']}',this.value)\" placeholder='특이사항 메모…'></textarea></div></div>")
        P.append("</section>")

    # 설계맵
    P.append("<section class='pane' data-tab='설계맵'>")
    P.append("<h2>확신도 히트맵 (화면 × 확신도)</h2><table class='hm'><tr><th>카테고리</th><th>화면</th><th>High</th><th>Med</th><th>Low</th><th>계</th></tr>")
    for cat in cats:
        for sn in screen_of_cat[cat]:
            rows = by_screen[(cat, sn)]; c = Counter(t["confidence"] for t in rows)
            def cell(k):
                v = c.get(k, 0)
                return f"<td style='background:{CONFC[k]};color:#fff;font-weight:700'>{v}</td>" if v else "<td class='z'></td>"
            P.append(f"<tr><td class='sn'>{esc(cat)}</td><td class='sn'>{esc(sn)}</td>{cell('High')}{cell('Med')}{cell('Low')}<td class='tot'>{len(rows)}</td></tr>")
    P.append("</table><p class='hint'>Low/Med 화면일수록 QA 검증 비중 ↑</p>")
    P.append("<h2>기능 분류 트리</h2>")
    for cat in cats:
        P.append(f"<details class='tree'><summary><b>{esc(cat)}</b> <span class='cnt'>{len(by_cat[cat])}</span></summary>")
        for sn in screen_of_cat[cat]:
            rows = by_screen[(cat, sn)]; secs = defaultdict(list)
            for t in rows: secs[t["section"]].append(t)
            P.append(f"<details class='tree'><summary>{esc(sn)} <span class='cnt'>{len(rows)}</span></summary>")
            for sec, lst in secs.items():
                P.append(f"<div class='leaf'><span class='sec'>{esc(sec)}</span> <span class='cnt'>{len(lst)}</span> <span class='ids'>{esc(' · '.join(x['id'].split('-')[-1] for x in lst))}</span></div>")
            P.append("</details>")
        P.append("</details>")
    P.append("<h2>Gap Analysis</h2><table class='gap'><tr><th>영역</th><th>이유</th><th>처리</th></tr>")
    for a, w, h in gaps: P.append(f"<tr><td><b>{esc(a)}</b></td><td>{esc(w)}</td><td>{esc(h)}</td></tr>")
    P.append("</table><h2>탐색 테스트 차터</h2><table class='gap'><tr><th>차터</th><th>조건</th><th>살펴볼 점</th></tr>")
    for a, w, h in charters: P.append(f"<tr><td><b>{esc(a)}</b></td><td>{esc(w)}</td><td>{esc(h)}</td></tr>")
    P.append("</table></section>")

    # 판정 기준
    P.append("<section class='pane' data-tab='판정 기준'>")
    P.append("<h2>판정 기준 고지 <span class='hint'>AI가 아래 규칙(휴리스틱)으로 자동 태깅합니다. 최종 판단은 QA가 검토·수정하세요.</span></h2>")
    for name, rows in RULES.items():
        P.append(f"<h3>{esc(name)}</h3><table class='gap'><tr><th style='width:110px'>값</th><th>기준</th></tr>")
        for k, v in rows: P.append(f"<tr><td><b>{esc(k)}</b></td><td>{esc(v)}</td></tr>")
        P.append("</table>")
    P.append("</section>")
    P.append("</div>")

    IDX = [{"id": t["id"], "cat": t["category"], "pw": t["pw"], "risk": t["risk"], "screen": t["screen"], "func": t["func"]} for t in tcs]
    body = "".join(P)
    return body, IDX, {"errors": errors, "warnings": warnings, "total": len(tcs)}, tcs

CSS = """<meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>TC 리포트</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f6f8;color:#222;font-family:'Malgun Gothic',Arial,sans-serif;font-size:13px;line-height:1.5}
.wrap{max-width:1180px;margin:0 auto;padding:20px}
header{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px}
h1{font-size:21px;margin:0;color:#1f6b6b}.sub{color:#667;margin:4px 0 14px}
.hbtn button,.hbtn .imp{font-size:12px;padding:6px 12px;border:1px solid #1f6b6b;background:#1f6b6b;color:#fff;border-radius:6px;cursor:pointer;margin-left:6px}
.hbtn .ghost{background:#fff;color:#1f6b6b}.hbtn .imp{display:inline-block}
h2{font-size:16px;margin:22px 0 10px;border-left:4px solid #1f6b6b;padding-left:8px}h3{font-size:14px;margin:16px 0 8px}h3.scr{color:#1f6b6b}
.menunav{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 12px;padding-bottom:8px;border-bottom:2px solid #1f6b6b}
.mb{border:1px solid #cfd6db;background:#fff;color:#445;padding:7px 15px;border-radius:8px;cursor:pointer;font-size:13px;font-weight:700}
.mb.on{background:#1f6b6b;color:#fff;border-color:#1f6b6b}.mb:disabled{opacity:.5;cursor:not-allowed}.soon-badge{font-size:10px;color:#a0a6ad;font-weight:400}
.tabs{display:flex;flex-wrap:wrap;gap:4px;position:sticky;top:0;background:#f4f6f8;padding:6px 0;z-index:5;border-bottom:2px solid #dde3e7}
.tab{border:1px solid #cfd6db;background:#fff;color:#445;padding:6px 12px;border-radius:6px 6px 0 0;cursor:pointer;font-size:12.5px}
.tab.on{background:#1f6b6b;color:#fff;border-color:#1f6b6b;font-weight:700}
.pane{display:none}.pane.on{display:block}
.cnt{background:#eef2f4;border-radius:10px;padding:0 7px;font-size:11px;color:#557}
.b{display:inline-block;padding:1px 7px;border-radius:10px;font-size:11px;font-weight:700;margin-right:3px}
table{border-collapse:collapse;width:100%;background:#fff;border:1px solid #e2e6ea;border-radius:8px;overflow:hidden;margin:4px 0}
th,td{border:1px solid #eceff1;padding:7px 9px;text-align:left;vertical-align:top}th{background:#1f6b6b;color:#fff}
.hm td{text-align:center}.hm .sn{text-align:left;color:#333;font-weight:600}.hm .z{background:#f7f8f9}.hm .tot{font-weight:700}
.sum td{text-align:center}.sum td:first-child{text-align:left;font-weight:700}
.bar{height:12px;border-radius:6px;background:#e6eaed;overflow:hidden;min-width:120px}.bar>i{display:block;height:100%;background:#2e9e5b}
.tc{background:#fff;border:1px solid #e2e6ea;border-left:5px solid #cfd6db;border-radius:6px;padding:9px 12px;margin:8px 0;display:flex;gap:12px;align-items:stretch}
.tc-main{flex:1;min-width:0}.tc-note{flex:0 0 210px;display:flex;flex-direction:column}
.tc-note .nlab{font-size:11px;color:#889;font-weight:700;margin-bottom:3px}
.note-in{flex:1;min-height:66px;resize:vertical;border:1px solid #dfe4e8;border-radius:6px;padding:6px 8px;font-family:inherit;font-size:12px;background:#fcfdfe;color:#333}
.note-in:focus{outline:none;border-color:#1f6b6b;background:#fff}
@media(max-width:760px){.tc{flex-direction:column}.tc-note{flex:none}}
.tc.Pass{border-left-color:#2e9e5b}.tc.Fail{border-left-color:#d64545;background:#fef7f7}.tc.NT{border-left-color:#9aa0a6}
.tc-h .id{font-weight:800;color:#1f6b6b}.tc-h .sec2{color:#889;font-size:11px;margin:0 4px}
.tc-b{margin-top:6px;font-size:12.5px}
.tc-b>div{display:flex;gap:8px;padding:5px 0;border-top:1px dashed #d7dde2}
.tc-b>div:first-child{border-top:0;padding-top:2px}.tc-b>div.meta{display:block}
.k{flex:0 0 66px;color:#889;font-weight:700;border-right:1px solid #d7dde2;padding-right:9px}.v{flex:1}.proc{white-space:normal}
.st{display:inline-flex;gap:2px;margin-right:6px}.s{border:1px solid #cfd6db;background:#fff;color:#556;font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px;cursor:pointer}
.s.p.on{background:#2e9e5b;color:#fff;border-color:#2e9e5b}.s.f.on{background:#d64545;color:#fff;border-color:#d64545}.s.n.on{background:#9aa0a6;color:#fff;border-color:#9aa0a6}
.mth{margin-left:6px;border:1px solid #cfd6db;background:#fff;color:#889;font-size:11px;font-weight:700;padding:2px 8px;border-radius:5px;cursor:pointer;min-width:64px}
.mth.auto{background:#eaf3ff;color:#1c5fb0;border-color:#9dc4f0}.mth.manual{background:#fef2e6;color:#b26a12;border-color:#f0c68a}
.meta{margin-top:6px;color:#8a94a6;font-size:11px}.mc{margin-right:10px;white-space:nowrap}.mc i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:3px;vertical-align:middle}.tk{color:#a7adb4}
.filt{margin:2px 0 10px}.filt .fb{border:1px solid #cfd6db;background:#fff;color:#556;font-size:11.5px;padding:3px 10px;border-radius:12px;cursor:pointer;margin:2px 4px 2px 0}
.filt .fb.on{background:#1f6b6b;color:#fff;border-color:#1f6b6b}
.leaf{margin:2px 0 2px 20px;color:#445}.leaf .sec{font-weight:700}.leaf .ids{color:#99a;font-size:11px}
.tree{margin:2px 0 2px 6px}.tree>summary{cursor:pointer;padding:3px 0}
.faillist a{display:block;color:#b0203a;text-decoration:none;padding:2px 0}.hint{color:#778;font-size:12px;font-weight:400}
.pill{display:inline-block;padding:2px 10px;border-radius:12px;color:#fff;font-weight:700;margin:2px 6px 2px 0}
.dist{display:flex;gap:16px;flex-wrap:wrap}.dbox{flex:1;min-width:240px;background:#fff;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px}
.dt{font-weight:700;margin-bottom:6px}.drow{display:flex;align-items:center;gap:8px;margin:4px 0}
.dl{width:60px;color:#556}.dbar{flex:1;height:12px;background:#eef1f3;border-radius:6px;overflow:hidden}.dbar>i{display:block;height:100%}.dn{width:36px;text-align:right;font-weight:700}
.expl{background:#f0f6f5;border:1px solid #d6e4e1;border-radius:8px;padding:11px 13px;margin:10px 0;color:#334;font-size:12.5px;line-height:1.75}
.intro p{color:#334}.flow{max-width:640px;margin:6px 0}
.fstep{background:#fff;border:1px solid #cfd6db;border-left:4px solid #1f6b6b;border-radius:8px;padding:9px 13px}
.fstep .fn{display:inline-block;width:22px;height:22px;border-radius:50%;background:#1f6b6b;color:#fff;text-align:center;line-height:22px;font-weight:700;margin-right:8px;font-size:12px}
.fstep b{color:#1f6b6b}.fstep .fd{color:#556;font-size:12px;margin:3px 0 0 30px;display:block}
.farrow{color:#9bb;text-align:center;font-size:13px;line-height:1;margin:4px 0 4px 10px}
.tabgrid{display:flex;gap:12px;flex-wrap:wrap}.tcard{flex:1;min-width:220px;background:#fff;border:1px solid #e2e6ea;border-radius:8px;padding:10px 12px}
.tcard b{color:#1f6b6b}.tcard div{color:#556;font-size:12px;margin-top:3px}.use{margin:6px 0 0 18px;color:#334}.use li{margin:3px 0}
</style>"""

JS = """<script>
var IDX=__IDX__;var MSEED=__MSEED__;var KEY='TCSTUDIO_STATUS';var NKEY='TCSTUDIO_NOTE';var MKEY='TCSTUDIO_METHOD';
function load(){try{return JSON.parse(localStorage.getItem(KEY)||'{}')}catch(e){return {}}}
function save(o){localStorage.setItem(KEY,JSON.stringify(o))}
function loadN(){try{return JSON.parse(localStorage.getItem(NKEY)||'{}')}catch(e){return {}}}
function saveN(o){localStorage.setItem(NKEY,JSON.stringify(o))}
function loadM(){try{return JSON.parse(localStorage.getItem(MKEY)||'{}')}catch(e){return {}}}
function saveM(o){localStorage.setItem(MKEY,JSON.stringify(o))}
function methodOf(id){var m=loadM();return (id in m)?m[id]:(MSEED[id]||'')}
var MLBL={'':'—','auto':'🤖 자동','manual':'✋ 수동'};
function applyMethodOne(id){var b=document.querySelector(".mth[data-id='"+id+"']");if(!b)return;var v=methodOf(id);b.textContent=MLBL[v]||'—';b.classList.remove('auto','manual');if(v)b.classList.add(v);var row=document.getElementById('row-'+id);if(row)row.dataset.method=v||''}
function applyAllM(){IDX.forEach(function(t){applyMethodOne(t.id)})}
function cycleM(id){var m=loadM();var cur=methodOf(id);var nx=cur===''?'manual':(cur==='manual'?'auto':'');m[id]=nx;saveM(m);applyMethodOne(id);recompute();if(window._methodHook)window._methodHook(id,nx)}
function setSt(id,v){var o=load();if(o[id]===v){delete o[id]}else{o[id]=v}save(o);applyOne(id,o[id]);recompute()}
function setNote(id,v){var o=loadN();if(v){o[id]=v}else{delete o[id]}saveN(o);if(window._noteHook)window._noteHook(id,v)}
function applyOne(id,v){var st=document.querySelector(".st[data-id='"+id+"']");if(st){st.querySelectorAll('.s').forEach(function(b){b.classList.toggle('on',b.dataset.v===v)})}
 var row=document.getElementById('row-'+id);if(row){row.classList.remove('Pass','Fail','NT');if(v==='Pass')row.classList.add('Pass');else if(v==='Fail')row.classList.add('Fail');else if(v==='N/T')row.classList.add('NT')}}
function applyAll(){var o=load();IDX.forEach(function(t){applyOne(t.id,o[t.id])})}
function applyNotes(){var o=loadN();document.querySelectorAll('.note-in').forEach(function(ta){ta.value=o[ta.dataset.id]||''})}
function parseCSVLine(line){var out=[],cur='',q=false;for(var i=0;i<line.length;i++){var c=line[i];if(q){if(c=='"'){if(line[i+1]=='"'){cur+='"';i++}else q=false}else cur+=c}else{if(c=='"')q=true;else if(c==','){out.push(cur);cur=''}else cur+=c}}out.push(cur);return out}
function recompute(){var o=load();var cats={},pw={'가능':{t:0},'부분':{t:0},'불가':{t:0}};var tot={Pass:0,Fail:0,'N/T':0,n:IDX.length};
 IDX.forEach(function(t){var s=o[t.id];cats[t.cat]=cats[t.cat]||{Pass:0,Fail:0,'N/T':0,n:0};cats[t.cat].n++;if(s){cats[t.cat][s]++;tot[s]++}pw[t.pw].t++});
 var done=tot.Pass+tot.Fail+tot['N/T'];var pct=Math.round(done/tot.n*100);
 document.getElementById('overall').innerHTML="<div class='bar'><i style='width:"+pct+"%'></i></div><p><b>"+pct+"%</b> 진행 ("+done+"/"+tot.n+") · <span style='color:#2e9e5b'>Pass "+tot.Pass+"</span> · <span style='color:#d64545'>Fail "+tot.Fail+"</span> · N/T "+tot['N/T']+" · 미실행 "+(tot.n-done)+"</p>";
 var h='';Object.keys(cats).forEach(function(c){var x=cats[c];var d=x.Pass+x.Fail+x['N/T'];var p=Math.round(d/x.n*100);h+="<tr><td>"+c+"</td><td>"+x.n+"</td><td style='color:#2e9e5b'>"+x.Pass+"</td><td style='color:#d64545'>"+x.Fail+"</td><td>"+x['N/T']+"</td><td>"+(x.n-d)+"</td><td><div class='bar'><i style='width:"+p+"%'></i></div>"+p+"%</td></tr>"});
 document.getElementById('catsum').innerHTML=h;
 var pk=Object.keys(pw).map(function(k){var c={'가능':'#2e9e5b','부분':'#e0a01e','불가':'#9aa0a6'}[k];return "<span class='pill' style='background:"+c+"'>"+k+" "+pw[k].t+"건</span>"}).join(' ');
 document.getElementById('pwsum').innerHTML=pk;
 var mc={auto:0,manual:0,none:0};IDX.forEach(function(t){var v=methodOf(t.id);mc[v==='auto'?'auto':(v==='manual'?'manual':'none')]++});
 var ms=document.getElementById('methsum');if(ms)ms.innerHTML="<span class='pill' style='background:#1c5fb0'>🤖 자동확인 "+mc.auto+"건</span><span class='pill' style='background:#b26a12'>✋ 수동확인 "+mc.manual+"건</span><span class='pill' style='background:#9aa0a6'>미확인 "+mc.none+"건</span>";
 var fl=IDX.filter(function(t){return o[t.id]==='Fail'});
 document.getElementById('faillist').innerHTML=fl.length?fl.map(function(t){return "<a href='#row-"+t.id+"' onclick=\\"gotoTC('"+t.cat+"','"+t.id+"')\\">● "+t.id+" · "+t.screen+" · "+t.func+"</a>"}).join(''):'아직 Fail 없음';}
function showTab(name,btn){document.querySelectorAll('.pane').forEach(function(p){p.classList.toggle('on',p.dataset.tab===name)});document.querySelectorAll('.tab').forEach(function(b){b.classList.remove('on')});if(btn)btn.classList.add('on');window.scrollTo(0,0)}
function menuTabs(code){var first=null;document.querySelectorAll('.tab[data-menu]').forEach(function(tb){var vis=tb.dataset.menu===code;tb.style.display=vis?'':'none';if(vis&&!first)first=tb});return first}
function showMenu(code,btn){document.querySelectorAll('.mb').forEach(function(b){b.classList.remove('on')});if(btn)btn.classList.add('on');var f=menuTabs(code);if(f)f.click();window.scrollTo(0,0)}
function initMenu(){menuTabs('SUMMARY')}
function gotoTC(cat,id){var tb=null;document.querySelectorAll('.tab[data-menu]').forEach(function(b){if(b.textContent.trim()===cat)tb=b});if(tb){var mc=tb.dataset.menu;menuTabs(mc);document.querySelectorAll('.mb').forEach(function(b){b.classList.toggle('on',b.dataset.code===mc)});tb.click()}setTimeout(function(){var el=document.getElementById('row-'+id);if(el){el.scrollIntoView({block:'center'});el.style.outline='2px solid #d64545';setTimeout(function(){el.style.outline=''},1500)}},80)}
function csvCell(c){c=(''+c).replace(/"/g,'""');return /[",\\n]/.test(c)?'"'+c+'"':c}
function exportCSV(){var o=load(),no=loadN();var ml={'':'','auto':'자동','manual':'수동'};var rows=[['TC ID','결과','검증방법','비고','카테고리','화면','기능명']];IDX.forEach(function(t){rows.push([t.id,o[t.id]||'',ml[methodOf(t.id)]||'',no[t.id]||'',t.cat,t.screen,t.func])});
 var csv='\\ufeff'+rows.map(function(r){return r.map(csvCell).join(',')}).join('\\r\\n');var blob=new Blob([csv],{type:'text/csv;charset=utf-8'});var a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download='TC_결과.csv';a.click()}
function importCSV(e){var f=e.target.files[0];if(!f)return;var r=new FileReader();r.onload=function(){try{var txt=r.result.replace(/^\\ufeff/,'');var lines=txt.split(/\\r?\\n/);var hdr=parseCSVLine(lines[0]||'');var hasM=hdr.indexOf('검증방법')>=0;var mi=hasM?2:-1,ni=hasM?3:2;var o={},no={},mo={};var mmap={'자동':'auto','수동':'manual'};for(var i=1;i<lines.length;i++){if(!lines[i].trim())continue;var p=parseCSVLine(lines[i]);var id=(p[0]||'').trim(),st=(p[1]||'').trim(),nt=(p[ni]||'').trim();if(id&&(st==='Pass'||st==='Fail'||st==='N/T'))o[id]=st;if(id&&nt)no[id]=nt;if(hasM&&id){var mv=mmap[(p[mi]||'').trim()];if(mv)mo[id]=mv}}save(o);saveN(no);if(hasM)saveM(mo);applyAll();applyNotes();applyAllM();recompute();alert('불러왔습니다 (결과 '+Object.keys(o).length+' · 비고 '+Object.keys(no).length+')')}catch(x){alert('형식 오류')}};r.readAsText(f)}
function resetStatus(){if(confirm('모든 Pass/Fail/N·T 를 초기화할까요? (비고는 유지)')){localStorage.removeItem(KEY);applyAll();recompute()}}
function filt(btn){var pane=btn.closest('.pane');pane.querySelectorAll('.fb').forEach(function(b){b.classList.toggle('on',b===btn)});var f=btn.dataset.f;var o=load();
 pane.querySelectorAll('.tc').forEach(function(row){var id=row.id.slice(4);var show=true;if(f==='all')show=true;else if(f.indexOf('pw-')===0)show=row.dataset.pw===f.slice(3);else if(f==='m-auto')show=methodOf(id)==='auto';else if(f==='m-manual')show=methodOf(id)==='manual';else if(f==='m-none')show=!methodOf(id);else if(f==='st-Fail')show=o[id]==='Fail';else if(f==='st-none')show=!o[id];row.style.display=show?'':'none'});
 pane.querySelectorAll('h3.scr').forEach(function(h){var n=h.nextElementSibling,any=false;while(n&&!n.classList.contains('scr')){if(n.classList&&n.classList.contains('tc')&&n.style.display!=='none')any=true;n=n.nextElementSibling}h.style.display=any?'':'none'})}
initMenu();applyAll();applyNotes();applyAllM();recompute();
</script>"""

DASH_OVERRIDE = ("<script>(function(){var S='/api/status',N='/api/note',M='/api/method';var _set=setSt;"
 "setSt=function(id,v){_set(id,v);var o=load();fetch(S,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,status:o[id]||''})}).catch(function(){})};"
 "window._noteHook=function(id,v){fetch(N,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,note:v||''})}).catch(function(){})};"
 "window._methodHook=function(id,v){fetch(M,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({id:id,method:v||''})}).catch(function(){})};"
 "fetch(S).then(function(r){return r.json()}).then(function(d){if(d&&typeof d==='object'){save(d);applyAll();recompute()}}).catch(function(){});"
 "fetch(N).then(function(r){return r.json()}).then(function(d){if(d&&typeof d==='object'){saveN(d);applyNotes()}}).catch(function(){});"
 "fetch(M).then(function(r){return r.json()}).then(function(d){if(d&&typeof d==='object'){saveM(d);applyAllM();recompute()}}).catch(function(){});"
 "var b=document.querySelector('.hbtn');if(b){var s=document.createElement('span');s.style.cssText='margin-left:10px;color:#2e9e5b;font-size:11px;font-weight:700';s.textContent='● 서버 공유 모드';b.appendChild(s)}"
 "})();</script>")

def main():
    ap = argparse.ArgumentParser(description="tc_data.json → report.html + dashboard.html")
    ap.add_argument("data", nargs="?", default="tc_data.json", help="입력 tc_data.json 경로")
    ap.add_argument("-o", "--outdir", default=".", help="출력 폴더")
    args = ap.parse_args()
    data = json.load(open(args.data, encoding="utf-8"))
    body, IDX, val, tcs = render(data)
    os.makedirs(args.outdir, exist_ok=True)
    mseed = {t["id"]: t["method"] for t in tcs if t.get("method")}
    js = JS.replace("__IDX__", json.dumps(IDX, ensure_ascii=False)).replace("__MSEED__", json.dumps(mseed, ensure_ascii=False))
    open(os.path.join(args.outdir, "report.html"), "w", encoding="utf-8").write(CSS + body + js)
    open(os.path.join(args.outdir, "dashboard.html"), "w", encoding="utf-8").write(CSS + body + js + DASH_OVERRIDE)
    print("report.html / dashboard.html 생성 | TC %d | err %d warn %d" % (val["total"], len(val["errors"]), len(val["warnings"])))
    for e in val["errors"][:20]: print("  [ERROR]", e)

if __name__ == "__main__":
    main()
