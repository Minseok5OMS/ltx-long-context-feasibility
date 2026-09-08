# Local smoke · pilot_000_local_cooking

[이 실험의 사례 목록](README.md) · [전체 실험](../README.md) · [입력 방식](../../docs/METHODS.md)

Local을 고정 조건으로 다음 3초를 생성하는 실행 경로 점검입니다.

관찰·해석은 [실험별 결과](../../docs/EXPERIMENTS.md)를 함께 확인하세요.

**GIF는 축소 미리보기(8 FPS)입니다.** 모든 생성 Target은 원본 3초입니다. 미리보기 또는 MP4 링크를 클릭하면 저장소 파일을 열 수 있습니다. 재사용 표시는 같은 원실행을 다시 비교했다는 뜻입니다.

## 실제 입력과 평가용 후속

Local은 생성 조건입니다. 원본 후속은 입력에 넣지 않았습니다.

### Local · 고정 생성 조건

[![Local · 고정 생성 조건](../../media/previews/3c0afc106b7156c97f1adea5d5eb6730157531ce708b1097031238947f0d5e5a.gif)](../../media/videos/3c0afc106b7156c97f1adea5d5eb6730157531ce708b1097031238947f0d5e5a.mp4)

RGB 표시 · 48 frames / 24 FPS · [MP4 파일](../../media/videos/3c0afc106b7156c97f1adea5d5eb6730157531ce708b1097031238947f0d5e5a.mp4) · [원본 열기/다운로드](../../media/videos/3c0afc106b7156c97f1adea5d5eb6730157531ce708b1097031238947f0d5e5a.mp4?raw=true)

### 원본 후속 · 생성 입력 제외

[![원본 후속 · 생성 입력 제외](../../media/previews/8bbde594ec52ce8d98420acb65c99bb558fe09cf919da284551c1b949884bbdc.gif)](../../media/videos/8bbde594ec52ce8d98420acb65c99bb558fe09cf919da284551c1b949884bbdc.mp4)

원본 후속 · 생성 입력 제외 · [MP4 파일](../../media/videos/8bbde594ec52ce8d98420acb65c99bb558fe09cf919da284551c1b949884bbdc.mp4) · [원본 열기/다운로드](../../media/videos/8bbde594ec52ce8d98420acb65c99bb558fe09cf919da284551c1b949884bbdc.mp4?raw=true)

원본: Vendakka Moru Curry, Ladysfinger Yoghurt Curry, Okra curd curry · [구간·출처 metadata](../../records/data/pilot_000_local_cooking/metadata.json)

## 생성 결과

###  Local-only · seed 42

**신규 실행 · run_096**

[![Local-only](../../media/previews/a5d38af5a97e257c30fb33f6c3358f743ba77c32fa4a57de1c5c4f8ed20db533.gif)](../../media/videos/a5d38af5a97e257c30fb33f6c3358f743ba77c32fa4a57de1c5c4f8ed20db533.mp4)

[Target MP4](../../media/videos/a5d38af5a97e257c30fb33f6c3358f743ba77c32fa4a57de1c5c4f8ed20db533.mp4) · [원본 열기/다운로드](../../media/videos/a5d38af5a97e257c30fb33f6c3358f743ba77c32fa4a57de1c5c4f8ed20db533.mp4?raw=true) · [Local + Target 5초](../../media/videos/a25d71625b8fa404ea1e2d80ef79350eb6edf63b9fa7ffe538892fdbc261d741.mp4) · [원실행 config](../../records/outputs/pilot_000_local_cooking/local_seed42/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
An overhead kitchen shot continues as a person stirs the contents of a pan on the stove.
```

- 참조 모델 좌표: `원본 config 참조`
- Target 모델 좌표: `원본 config 참조`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/pilot_000_local_cooking/local_seed42/config.json`

</details>
