# 5개 원본 Local / Image-Past · 로봇 모형의 가려졌던 머리

[이 실험의 사례 목록](README.md) · [전체 실험](../README.md) · [입력 방식](../../docs/METHODS.md)

서로 다른 5개 FineVideo 원본에서 Local-only와 Local+Oracle Image-Past를 비교합니다.

관찰·해석은 [실험별 결과](../../docs/EXPERIMENTS.md)를 함께 확인하세요.

**GIF는 축소 미리보기(8 FPS)입니다.** 모든 생성 Target은 원본 3초입니다. 미리보기 또는 MP4 링크를 클릭하면 저장소 파일을 열 수 있습니다. 재사용 표시는 같은 원실행을 다시 비교했다는 뜻입니다.

## 실제 입력과 평가용 후속

Local은 생성 조건입니다. 원본 후속은 입력에 넣지 않았습니다.

### Local · 고정 생성 조건

[![Local · 고정 생성 조건](../../media/previews/d5f6a81366e9ce8d9cca51f3c6a6d2e4984ec9fc2f7145b9d7f144a85bd5e0db.gif)](../../media/videos/d5f6a81366e9ce8d9cca51f3c6a6d2e4984ec9fc2f7145b9d7f144a85bd5e0db.mp4)

RGB 표시 · 48 frames / 24 FPS · [MP4 파일](../../media/videos/d5f6a81366e9ce8d9cca51f3c6a6d2e4984ec9fc2f7145b9d7f144a85bd5e0db.mp4) · [원본 열기/다운로드](../../media/videos/d5f6a81366e9ce8d9cca51f3c6a6d2e4984ec9fc2f7145b9d7f144a85bd5e0db.mp4?raw=true)

### Oracle · 과거 증거

[![Oracle · 과거 증거](../../media/previews/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.gif)](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4)

RGB 표시 · 72 frames / 24 FPS · [MP4 파일](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4) · [원본 열기/다운로드](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4?raw=true)

### 원본 후속 · 생성 입력 제외

[![원본 후속 · 생성 입력 제외](../../media/previews/7fd86bac820db09bbed5316b7ffdbc82c7efae238d4d2638a6792064458d0e82.gif)](../../media/videos/7fd86bac820db09bbed5316b7ffdbc82c7efae238d4d2638a6792064458d0e82.mp4)

원본 후속 · 생성 입력 제외 · [MP4 파일](../../media/videos/7fd86bac820db09bbed5316b7ffdbc82c7efae238d4d2638a6792064458d0e82.mp4) · [원본 열기/다운로드](../../media/videos/7fd86bac820db09bbed5316b7ffdbc82c7efae238d4d2638a6792064458d0e82.mp4?raw=true)

### Oracle 이미지 · 실제 frame 36

![실제 이미지 참조](../../media/stills/five_002_robot_head_oracle_frame36.png)

이미지 조건은 이 한 장을 인코딩했습니다. 영상 조건과 구분합니다.

원본: HG Obsidian Fury Review (Pacific Rim Uprising) · [구간·출처 metadata](../../records/data/five_002_robot_head/metadata.json)

## 생성 결과

###  Local-only · seed 42

**신규 실행 · run_015**

[![Local-only](../../media/previews/4a0c89a0f12fcea5df162189cc7442cef5e954fdf595e51a1c39d17480e31ae1.gif)](../../media/videos/4a0c89a0f12fcea5df162189cc7442cef5e954fdf595e51a1c39d17480e31ae1.mp4)

[Target MP4](../../media/videos/4a0c89a0f12fcea5df162189cc7442cef5e954fdf595e51a1c39d17480e31ae1.mp4) · [원본 열기/다운로드](../../media/videos/4a0c89a0f12fcea5df162189cc7442cef5e954fdf595e51a1c39d17480e31ae1.mp4?raw=true) · [Local + Target 5초](../../media/videos/2a7803c4fbea9868dffa3fc4a4c040f252f219fc0d7ca4bc7e44c5cafa165d22.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/image_past_seed42/local/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The view switches to the same robot model posed on its display turntable, showing its head and upper body.
```

- 참조 모델 좌표: `[0.0000, 0.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/five_002_robot_head/image_past_seed42/local/config.json`

</details>

###  Oracle · Video-Past · seed 42

**신규 실행 · run_016**

[![Oracle · Video-Past](../../media/previews/2dd4d40f74bf9c0403fcec03711e3d394dfd3325b7359cb6be3174d52e2b2368.gif)](../../media/videos/2dd4d40f74bf9c0403fcec03711e3d394dfd3325b7359cb6be3174d52e2b2368.mp4)

[Target MP4](../../media/videos/2dd4d40f74bf9c0403fcec03711e3d394dfd3325b7359cb6be3174d52e2b2368.mp4) · [원본 열기/다운로드](../../media/videos/2dd4d40f74bf9c0403fcec03711e3d394dfd3325b7359cb6be3174d52e2b2368.mp4?raw=true) · [Local + Target 5초](../../media/videos/e8e96399bf10563ed1b72a4b14be2442da558e2f2046be6bb5fd7ed5db60a4e0.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/image_past_seed42/oracle/config.json)

참조: Oracle 영상 · 전체 프레임. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The view switches to the same robot model posed on its display turntable, showing its head and upper body.
```

- 참조 모델 좌표: `[0.0000, 0.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 144
- 원실행: `outputs/five_002_robot_head/image_past_seed42/oracle/config.json`

</details>
