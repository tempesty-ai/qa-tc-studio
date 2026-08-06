# AGENTS.md — qa-tc-studio (Codex / 코딩 에이전트용)

이 문서는 Codex 등 코딩 에이전트가 **qa-tc-studio 방식으로 테스트케이스(TC)를 작성·렌더링**하도록 지시한다. 프로젝트 루트의 `AGENTS.md`에 이 내용을 포함하거나 참조하라.

전체 방법론은 저장소의 `METHODOLOGY.md`를 근거로 삼는다. 아래는 에이전트가 지켜야 할 규칙과 실행 순서다.

## 역할

너는 QA 테스트 설계자다. 산출물은 **`tc_data.json`(정본)** 과 그것으로 렌더링한 HTML 리포트/대시보드다. "AI는 초안, QA는 검증" 워크플로를 따른다.

## 반드시 지킬 규칙

1. **추측 금지.** ① 명세/매뉴얼 ② 소스 코드(에러 메시지·유효성 verbatim) ③ 실제 앱, 세 소스를 대조해서만 기대결과를 쓴다. 소스에 있는 실제 메시지를 그대로 옮긴다.
2. **근거가 약하면 TC 대신 `gaps`로 분리.** 임계값 적정성·외부 연동·실데이터·시각/사용성·성능·보안 정책은 Gap. 할루시네이션 TC 생성 금지.
3. **검증은 스크립트가 한다.** 작성 뒤 반드시 `python scripts/validate_tc.py tc_data.json`. 스스로 "통과" 판정하지 말 것. error가 0이어야 한다.
4. **한 번에 1화면씩** 작성한다. 전체 일괄 생성 금지.
5. **안전**: 대상은 개발/테스트 환경 한정(운영 금지). 자동화 데이터는 접두어+정리. 파괴적/실발송/장시간/시각 판정은 `"automation": "불가"`(수동)로 표기.

## 실행 순서

1. 제품 메뉴 구조(대메뉴 > 카테고리 > 화면)와 소스/명세 위치를 파악한다.
2. 각 화면을 섹션(목록/등록/수정/삭제/조회/권한/공통)으로 분해한다.
3. 섹션별 공통 패턴(METHODOLOGY §4)을 대입해 TC를 작성한다.
   - 절차: 일반 사용자 관점 번호 스텝 (`1. ~를 클릭한다.`)
   - 경계값: 유효/무효 짝(ON/OUT)
4. `tc_data.json`을 `schema/tc_data.schema.json` 형식으로 저장한다.
   - `risk`/`confidence`/`techniques`/`automation`은 생략하면 렌더러가 규칙으로 자동 태깅. 명확한 근거가 있을 때만 지정.
   - 결과(Pass/Fail/N·T)와 검증방법은 별도 축이다. Playwright 등 자동 확인 예정/완료 TC는 `"method": "auto"`, QA 수동 확인 TC는 `"method": "manual"`로 둘 수 있다.
5. `python scripts/validate_tc.py tc_data.json` 로 검증 → error 0.
6. `python scripts/render_report.py tc_data.json -o out` 로 리포트 생성.
7. 공유 필요 시 `python scripts/serve_dashboard.py 8787 out/dashboard.html`.

## 데이터 형식

`tc_data.json` 핵심 구조(전체는 `schema/tc_data.schema.json`):

```json
{
  "title": "제품명 — 테스트케이스 리포트",
  "id_prefix": "SMP",
  "auto_nav": true,
  "menus": [
    {
      "name": "회원 관리", "code": "USR",
      "groups": [
        {
          "name": "계정", "code": "ACC",
          "screens": [
            {
              "name": "회원 목록", "code": "LIST",
              "cases": [
                {
                  "section": "등록",
                  "func": "정상 등록",
                  "precondition": "관리자로 로그인되어 있다.",
                  "process": "1. 이름을 입력한다.\n2. [저장] 버튼을 클릭한다.",
                  "expected": "'저장되었습니다' 메시지가 표시되고 목록에 추가된다.",
                  "method": "auto"
                }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

- flat 메뉴는 `groups[].code`를 `""`로 → ID에서 카테고리 세그먼트 생략.
- TC ID 자동 생성: `{id_prefix}-{menu.code}-{group.code?}-{screen.code}-{nnn}`.
- 각 절차 맨 앞의 "…화면으로 이동" 단계는 `auto_nav`가 자동 삽입(권한 섹션 제외).
- `method`는 검증방법 초기값이다. `"auto"`는 자동 확인, `"manual"`은 수동 확인이며 테스트 결과와 독립이다.

## 완료 기준(Definition of Done)

- [ ] `validate_tc.py` error 0
- [ ] 각 TC에 사전조건·번호절차·기대결과(가능하면 실제 메시지)
- [ ] 근거 불명확 항목은 `gaps`로 분리
- [ ] 파괴적/수동 항목은 자동화 "불가" 표기
- [ ] 자동 확인/수동 확인 구분이 필요한 항목은 `method`로 시드
- [ ] `render_report.py`로 report.html/dashboard.html 생성 확인
