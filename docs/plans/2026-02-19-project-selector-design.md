# 프로젝트 선택기 설계

## 목표
업로드 시 프로젝트 필드에서 Obsidian Vault의 활성 프로젝트를 드롭다운으로 선택할 수 있도록 한다.

## 백엔드: GET /projects
- `VAULT_PATH/20_Projects/` 하위를 재귀 스캔
- `*Dashboard*.md` 파일의 frontmatter에서 `status: 진행` 항목만 수집
- display: 서브폴더명에서 숫자 접두사 제거 (`22_USV_ECS_개발` → `USV ECS 개발`)
- link: `[[파일명(확장자 제외)]]` (Obsidian WikiLink 형식)
- 반환: `[{ "display": str, "link": str }]`

## 프론트엔드: select 드롭다운
- 현재 프로젝트 `<input type="text">` → `<select>`로 교체
- 페이지 로드 시 `GET /projects` 호출해 옵션 채움
- 첫 옵션: `선택 안 함` (value="")
- 선택 시 value = `[[Dashboard 파일명]]`

## 활성 판단 기준
- frontmatter `status: 진행` 인 Dashboard 파일만 포함
- 오류 발생 시 빈 목록 반환 (드롭다운은 비어있지만 입력 불가 상태 방지)
