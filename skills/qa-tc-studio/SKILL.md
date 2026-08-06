---
name: qa-tc-studio
description: Create, validate, and render QA test cases as tc_data.json plus interactive HTML reports and shared dashboards. Use when the user asks to design QA test cases, convert product/source/spec information into TC data, analyze coverage or gaps, generate tc_data.json, validate qa-tc-studio data, render reports, or prepare a QA dashboard.
---

# qa-tc-studio

Act as a QA test designer. Produce evidence-based test cases for the **AI draft -> QA validation** workflow, store them as `tc_data.json`, validate them with the bundled script, and render HTML reports when requested.

## First Steps

1. Read `references/methodology.md` before writing or reviewing test cases.
2. Inspect the target product context:
   - specification, manual, or requirements
   - source code, especially validation logic and exact messages
   - real development/test environment behavior when available
3. Ask for missing target context only when it cannot be discovered locally.

## Core Rules

1. Do not invent expected behavior. Triangulate from specification/manual, source code, and real app behavior where possible.
2. If evidence is weak, record the item as a gap instead of a test case.
3. Prefer actual source messages verbatim in expected results.
4. Work one screen at a time. Do not mass-generate a whole product in one pass.
5. Use development or test environments only. Do not run destructive actions in production.
6. Mark destructive, real-send, long-running, visual-only, audio, or external-system cases as manual with `"automation": "불가"` unless a safe automated strategy is explicitly available.

## Workflow

1. Map the product structure as menu > category > screen.
2. Split each screen into sections such as list, create, update, delete, search, permission, and common behavior.
3. Write cases using `schema/tc_data.schema.json`.
4. Leave `risk`, `confidence`, `techniques`, and `automation` blank unless there is strong evidence; the renderer can auto-tag them.
5. Validate. If working inside this repository, run:

```bash
python scripts/validate_tc.py tc_data.json
```

If working from an installed skill in another project, run the bundled script by its skill-path location or copy the bundled `scripts/` folder into the working project first.

6. Render. If working inside this repository, run:

```bash
python scripts/render_report.py tc_data.json -o out
```

7. If a shared dashboard is needed:

```bash
python scripts/serve_dashboard.py 8787 out/dashboard.html
```

## tc_data.json Shape

```json
{
  "title": "제품명 - 테스트케이스 리포트",
  "id_prefix": "SMP",
  "auto_nav": true,
  "menus": [
    {
      "name": "회원 관리",
      "code": "USR",
      "groups": [
        {
          "name": "계정",
          "code": "ACC",
          "screens": [
            {
              "name": "회원 목록",
              "code": "LIST",
              "cases": [
                {
                  "section": "등록",
                  "func": "정상 등록",
                  "precondition": "관리자로 로그인되어 있다.",
                  "process": "1. 이름을 입력한다.\n2. [저장] 버튼을 클릭한다.",
                  "expected": "'저장되었습니다' 메시지가 표시되고 목록에 추가된다."
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

- For flat menus without a category, set `groups[].code` to `""`; the ID segment is omitted.
- The renderer generates TC IDs as `{id_prefix}-{menu.code}-{group.code?}-{screen.code}-{nnn}`.
- Write steps from a normal user's point of view, beginning with `1.`.
- Pair boundary values as valid/invalid ON/OUT cases when relevant.

## Bundled Resources

- `references/methodology.md`: full QA methodology and patterns.
- `schema/tc_data.schema.json`: canonical data shape.
- `examples/tc_data.example.json`: sample input.
- `scripts/validate_tc.py`: data validation.
- `scripts/render_report.py`: report/dashboard HTML generation.
- `scripts/serve_dashboard.py`: shared dashboard server.

## Output Style

When responding to humans, include:

- what evidence was used
- what test cases or gaps were created
- validation result from `validate_tc.py`
- generated report paths when rendered

Do not claim a case is validated unless the validation script passed.
