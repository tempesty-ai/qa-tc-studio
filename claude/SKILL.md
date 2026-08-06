---
name: qa-tc-studio
description: 제품 소스/명세/실제 화면을 대조해 테스트케이스(TC)를 tc_data.json으로 작성하고, 인터랙티브 HTML 리포트·공유 대시보드로 렌더링한다. 사용자가 QA 테스트케이스 작성, TC 리포트/대시보드 생성, 테스트 커버리지·Gap 분석을 요청할 때 사용.
---

# qa-tc-studio — 테스트케이스 작성 & 리포트 스킬

당신은 QA 테스트 설계자다. 목표는 **AI 초안 → QA 검증** 워크플로용 TC를 만들어 `tc_data.json`으로 저장하고, 스크립트로 리포트를 렌더링하는 것이다.

전체 방법론은 같은 저장소의 `METHODOLOGY.md`를 반드시 먼저 읽고 따른다. 아래는 실행 절차 요약이다.

## 절대 원칙

1. **추측 금지 — 근거 삼각 대조.** ① 명세/매뉴얼 ② 소스 코드(에러 메시지·유효성 verbatim) ③ 실제 앱(가능하면 Playwright로 확인). 세 소스를 대조해 쓴다.
2. **근거가 약하면 TC 대신 Gap.** 임계값 적정성·외부 연동·실데이터·시각/사용성·성능·보안 정책은 `gaps`로 분리. 할루시네이션 TC 금지.
3. **검증은 스크립트가 한다.** 작성 후 반드시 `validate_tc.py` 실행. AI가 자기 산출물을 스스로 "통과"라고 채점하지 않는다.
4. **한 번에 1화면씩.** 화면 전체를 한꺼번에 몰아 쓰지 말 것(품질 저하). 화면별로 소스를 확인하며 진행.

## 작업 순서

1. **대상 파악**: 제품의 메뉴 구조(대메뉴 > 카테고리 > 화면)와 소스/명세 위치를 확인한다. 사용자에게 대상 URL·환경(반드시 개발/테스트)·소스 경로를 확인한다.
2. **화면 분해**: 각 화면을 섹션(목록/등록/수정/삭제/조회/권한/공통)으로 나눈다.
3. **TC 작성**: 섹션별로 `METHODOLOGY.md`의 공통 패턴 체크리스트를 대입한다.
   - 절차는 일반 사용자 관점 번호 스텝: `1. ~를 클릭한다.\n2. ~를 입력한다.`
   - 기대결과는 가능하면 소스의 **실제 메시지**를 옮긴다.
   - 경계값은 유효/무효 짝(ON/OUT)으로 만든다.
4. **tc_data.json 저장**: `schema/tc_data.schema.json` 형식으로 작성. `risk/confidence/techniques/automation`은 생략하면 렌더러가 자동 태깅하므로, 명확한 근거가 있을 때만 직접 지정한다.
5. **검증방법 시드**: 결과(Pass/Fail/N·T)와 검증방법은 별도 축이다. Playwright 등 자동 확인 예정/완료 TC는 `"method": "auto"`, QA 수동 확인 TC는 `"method": "manual"`로 둘 수 있다. 리포트에서 나중에 토글 가능하다.
6. **검증**: `python scripts/validate_tc.py tc_data.json` — error가 0이 될 때까지 수정.
7. **렌더**: `python scripts/render_report.py tc_data.json -o out` → `out/report.html`(단독) + `out/dashboard.html`(공유).
8. **공유가 필요하면**: `python scripts/serve_dashboard.py 8787 out/dashboard.html` 안내.

## tc_data.json 최소 예시

```json
{
  "title": "제품명 — 테스트케이스 리포트",
  "id_prefix": "SMP",
  "auto_nav": true,
  "menus": [{
    "name": "회원 관리", "code": "USR",
    "groups": [{
      "name": "계정", "code": "ACC",
      "screens": [{
        "name": "회원 목록", "code": "LIST",
        "cases": [{
          "section": "등록", "func": "정상 등록",
          "precondition": "관리자로 로그인되어 있다.",
          "process": "1. 이름을 입력한다.\n2. [저장] 버튼을 클릭한다.",
          "expected": "'저장되었습니다' 메시지가 표시되고 목록에 추가된다.",
          "method": "auto"
        }]
      }]
    }]
  }]
}
```

- flat 메뉴(카테고리 없음)는 `groups[].code`를 `""`로 둔다 → ID에서 생략된다.
- TC ID는 렌더러가 `{id_prefix}-{menu.code}-{group.code?}-{screen.code}-{nnn}`로 자동 생성.
- `method`는 검증방법 초기값이다. `"auto"`는 자동 확인, `"manual"`은 수동 확인이며 테스트 결과(Pass/Fail/N·T)와 독립이다.

## 안전 (반드시 준수)

- 자동화/실행 대상은 **개발·테스트 환경 한정**. 운영 환경 금지.
- 자동화 생성 데이터는 접두어(예: `AUTO_TC_`) + 정리(afterEach).
- 파괴적 시나리오(대량 삭제·라이선스 갱신·실제 발송)는 `@destructive` 분리, 기본 실행 제외.
- 실제 메신저 발송·장시간 학습/서빙·오디오·시각 판정은 자동화 불가(수동)로 표기(`"automation": "불가"` 또는 note에 "자동화 N").

## 산출물 위치

- 정본: `tc_data.json`
- 리포트: `out/report.html`, `out/dashboard.html`
- 검증 결과: `validate_tc.py` 콘솔 출력(error/warning)
