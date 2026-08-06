# -*- coding: utf-8 -*-
"""qa-tc-studio — TC 데이터 자체 검증 스크립트.

핵심 원칙: **AI 자가채점 금지 — 검증은 스크립트가 한다.**
tc_data.json 을 읽어 중복 ID / 필수 컬럼 누락 / 기대결과 공란 / 절차 스텝 형식 /
확신도·위험도 누락(자동 태깅 후에도 이상값)을 검사해 error/warning 리포트를 낸다.

사용:  python validate_tc.py [tc_data.json]
종료코드: error 가 하나라도 있으면 1, 아니면 0 (CI 연동 가능).
"""
import sys, json, re

REQUIRED = ["section", "func", "precondition", "process", "expected"]
RISK_OK = {"High", "Medium", "Low"}
CONF_OK = {"High", "Med", "Low"}
AUTO_OK = {"가능", "부분", "불가"}

def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "tc_data.json"
    data = json.load(open(path, encoding="utf-8"))
    errors, warnings, seen = [], [], set()
    id_prefix = data.get("id_prefix", "TC")
    n = 0
    for menu in data.get("menus", []):
        mcode = menu.get("code", "")
        if not menu.get("name") or not mcode:
            errors.append("menu name/code 누락: %r" % menu.get("name"))
        for g in menu.get("groups", []):
            gcode = g.get("code", "")
            for scr in g.get("screens", []):
                scode = scr.get("code", "")
                if not scode:
                    errors.append("화면 code 누락: %s > %s" % (menu.get("name"), scr.get("name")))
                for i, c in enumerate(scr.get("cases", [])):
                    n += 1
                    tid = "-".join(x for x in [id_prefix, mcode, gcode, scode] if x) + "-%03d" % (i + 1)
                    if tid in seen:
                        errors.append("%s: 중복 ID" % tid)
                    seen.add(tid)
                    for k in REQUIRED:
                        if not str(c.get(k, "")).strip():
                            errors.append("%s: 필수 항목 '%s' 공란" % (tid, k))
                    proc = str(c.get("process", "")).strip()
                    if proc and not re.match(r"^\s*1\.", proc):
                        warnings.append("%s: 절차가 '1.' 로 시작하지 않음" % tid)
                    r = c.get("risk")
                    if r and r not in RISK_OK:
                        errors.append("%s: 위험도 값 이상 '%s'" % (tid, r))
                    cf = c.get("confidence")
                    if cf and cf not in CONF_OK:
                        errors.append("%s: 확신도 값 이상 '%s'" % (tid, cf))
                    au = c.get("automation")
                    if au and au not in AUTO_OK:
                        errors.append("%s: 자동화 값 이상 '%s'" % (tid, au))

    print("=" * 56)
    print(" qa-tc-studio 자체 검증 — TC %d건" % n)
    print("=" * 56)
    print(" ERROR   : %d" % len(errors))
    for e in errors[:100]:
        print("   [E]", e)
    print(" WARNING : %d" % len(warnings))
    for w in warnings[:100]:
        print("   [W]", w)
    print("=" * 56)
    print(" 결과:", "실패(FAIL) — error 수정 필요" if errors else "통과(PASS)")
    sys.exit(1 if errors else 0)

if __name__ == "__main__":
    main()
