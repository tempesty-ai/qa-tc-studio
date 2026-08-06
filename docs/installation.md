# 설치 가이드

이 문서는 `qa-tc-studio`를 Codex와 Claude에서 설치해 사용하는 방법을 정리합니다.

저장소:

```text
https://github.com/tempesty-ai/qa-tc-studio
```

Skill 경로:

```text
skills/qa-tc-studio
```

## Codex에 설치

Codex에게 아래 GitHub 경로를 설치하라고 요청합니다.

```text
Install the Codex skill from https://github.com/tempesty-ai/qa-tc-studio/tree/main/skills/qa-tc-studio
```

설치 후 새 Codex 턴에서 사용할 수 있습니다.

```text
Use qa-tc-studio to create TC data for this product screen and render the report.
```

## Codex 수동 설치

### Windows PowerShell

```powershell
git clone https://github.com/tempesty-ai/qa-tc-studio.git
New-Item -ItemType Directory -Force $env:USERPROFILE\.codex\skills | Out-Null
Copy-Item -Recurse .\qa-tc-studio\skills\qa-tc-studio $env:USERPROFILE\.codex\skills\
```

### macOS 또는 Linux

```bash
git clone https://github.com/tempesty-ai/qa-tc-studio.git
mkdir -p ~/.codex/skills
cp -R qa-tc-studio/skills/qa-tc-studio ~/.codex/skills/
```

설치한 skill은 다음 Codex 턴부터 사용할 수 있습니다.

## Claude에 설치

GitHub Release에서 `qa-tc-studio.zip`을 내려받아 Claude custom skill로 업로드합니다.

다운로드 URL:

```text
https://github.com/tempesty-ai/qa-tc-studio/releases/latest/download/qa-tc-studio.zip
```

ZIP 구조는 아래와 같습니다.

```text
qa-tc-studio.zip
  qa-tc-studio/
    SKILL.md
    agents/
    references/
    schema/
    scripts/
    examples/
```

로컬에서 직접 ZIP을 만들 수도 있습니다.

Windows PowerShell:

```powershell
Compress-Archive -Path .\skills\qa-tc-studio -DestinationPath .\qa-tc-studio.zip -Force
```

macOS 또는 Linux:

```bash
cd skills
zip -r ../qa-tc-studio.zip qa-tc-studio
```

## 로컬 도구 실행

예제 데이터 검증:

```bash
python scripts/validate_tc.py examples/tc_data.example.json
```

리포트 생성:

```bash
python scripts/render_report.py examples/tc_data.example.json -o out
```

공유 대시보드 실행:

```bash
python scripts/serve_dashboard.py 8787 out/dashboard.html
```

브라우저에서 엽니다.

```text
http://localhost:8787
```

## GitHub Release 배포

이 저장소에는 `.github/workflows/release.yml`이 포함되어 있습니다.

버전 태그를 push합니다.

```bash
git tag v0.1.0
git push origin v0.1.0
```

GitHub Actions가 Release를 만들거나 업데이트하고 아래 파일을 첨부합니다.

```text
qa-tc-studio.zip
```
