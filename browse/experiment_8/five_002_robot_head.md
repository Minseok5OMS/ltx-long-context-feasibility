# Prompt P0 / P1 / P2 / P3 · 로봇 모형의 가려졌던 머리

[이 실험의 사례 목록](README.md) · [전체 실험](../README.md) · [입력 방식](../../docs/METHODS.md)

P1 출력 구도·행동, P2 +연속성, P3 +참조 역할. 같은 prompt의 Local/Image-Past/Video-Past를 비교합니다. P0는 재사용입니다.

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

### P0 Local-only · seed 42

**재사용 · run_015**

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

### P0 Oracle · Video-Past · seed 42

**재사용 · run_016**

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

### P0 Oracle · Video-Past · seed 42

**재사용 · run_027**

[![Oracle · Video-Past](../../media/previews/c48aa7d4f054f19541a9ade2e22f3cc4ebe90ccc35aaf1efa96200cb89f620b8.gif)](../../media/videos/c48aa7d4f054f19541a9ade2e22f3cc4ebe90ccc35aaf1efa96200cb89f620b8.mp4)

[Target MP4](../../media/videos/c48aa7d4f054f19541a9ade2e22f3cc4ebe90ccc35aaf1efa96200cb89f620b8.mp4) · [원본 열기/다운로드](../../media/videos/c48aa7d4f054f19541a9ade2e22f3cc4ebe90ccc35aaf1efa96200cb89f620b8.mp4?raw=true) · [Local + Target 5초](../../media/videos/6cca90e58a1da2887bb6ccb7fea1d68c01b497dc22a984f9732771c6fc880862.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/reference_grid_seed42/video_past/config.json)

참조: Oracle 영상 · 전체 프레임. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The view switches to the same robot model posed on its display turntable, showing its head and upper body.
```

- 참조 모델 좌표: `[0.0000, 3.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 1440
- 원실행: `outputs/five_002_robot_head/reference_grid_seed42/video_past/config.json`

</details>

### P1 Local-only · seed 42

**신규 실행 · run_018**

[![Local-only](../../media/previews/d48512b4075b32769e8482ad7fd50bade4abe77f397521cea7589fbe644ae6a7.gif)](../../media/videos/d48512b4075b32769e8482ad7fd50bade4abe77f397521cea7589fbe644ae6a7.mp4)

[Target MP4](../../media/videos/d48512b4075b32769e8482ad7fd50bade4abe77f397521cea7589fbe644ae6a7.mp4) · [원본 열기/다운로드](../../media/videos/d48512b4075b32769e8482ad7fd50bade4abe77f397521cea7589fbe644ae6a7.mp4?raw=true) · [Local + Target 5초](../../media/videos/6809235feaca545fb01fa0e2b765fdebc2019d72a06b18c369f35b9ea68e5224.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P1/local/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[0.0000, 0.0000) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P1/local/config.json`

</details>

### P1 Oracle · Image-Past · seed 42

**신규 실행 · run_017**

[![Oracle · Image-Past](../../media/previews/157f0abba39a9d8a2ff85957e4ff1fc5331c4e068a7a69896ed168e6d4979ee6.gif)](../../media/videos/157f0abba39a9d8a2ff85957e4ff1fc5331c4e068a7a69896ed168e6d4979ee6.mp4)

[Target MP4](../../media/videos/157f0abba39a9d8a2ff85957e4ff1fc5331c4e068a7a69896ed168e6d4979ee6.mp4) · [원본 열기/다운로드](../../media/videos/157f0abba39a9d8a2ff85957e4ff1fc5331c4e068a7a69896ed168e6d4979ee6.mp4?raw=true) · [Local + Target 5초](../../media/videos/18c8744c67489b96fe3399e3f267c09a6967a868aad5b1c9ee0d2f42f05f6338.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P1/image_past/config.json)

참조: Oracle 이미지 · frame 36. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/stills/five_002_robot_head_oracle_frame36.png)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[0.0000, 0.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 144
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P1/image_past/config.json`

</details>

### P1 Oracle · Video-Past · seed 42

**신규 실행 · run_019**

[![Oracle · Video-Past](../../media/previews/2db7fd84f771e51eb368efaef9ac684eddc24c1a9569cf3edc2bd881268682c1.gif)](../../media/videos/2db7fd84f771e51eb368efaef9ac684eddc24c1a9569cf3edc2bd881268682c1.mp4)

[Target MP4](../../media/videos/2db7fd84f771e51eb368efaef9ac684eddc24c1a9569cf3edc2bd881268682c1.mp4) · [원본 열기/다운로드](../../media/videos/2db7fd84f771e51eb368efaef9ac684eddc24c1a9569cf3edc2bd881268682c1.mp4?raw=true) · [Local + Target 5초](../../media/videos/ee495abd32bb64978d681f2225cbe25b9789b28f2d4ff398393d4a798c5d9a1d.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P1/video_past/config.json)

참조: Oracle 영상 · 전체 프레임. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[0.0000, 3.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 1440
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P1/video_past/config.json`

</details>

### P2 Local-only · seed 42

**신규 실행 · run_021**

[![Local-only](../../media/previews/0d5144bfe4521182beb428f4f449c74d886e6bfa01a886d63dc853256c13d174.gif)](../../media/videos/0d5144bfe4521182beb428f4f449c74d886e6bfa01a886d63dc853256c13d174.mp4)

[Target MP4](../../media/videos/0d5144bfe4521182beb428f4f449c74d886e6bfa01a886d63dc853256c13d174.mp4) · [원본 열기/다운로드](../../media/videos/0d5144bfe4521182beb428f4f449c74d886e6bfa01a886d63dc853256c13d174.mp4?raw=true) · [Local + Target 5초](../../media/videos/39e99540944b0697c1b84dc4250cd80458383048fccc637e3345d3f6ec75a613.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P2/local/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot. The robot model and its display turntable keep the same appearance as in the earlier view.
```

- 참조 모델 좌표: `[0.0000, 0.0000) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P2/local/config.json`

</details>

### P2 Oracle · Image-Past · seed 42

**신규 실행 · run_020**

[![Oracle · Image-Past](../../media/previews/ea27275adaa98fb602ffeadf5dc43784cf9d397acd74b6c1dae3dda380709fa9.gif)](../../media/videos/ea27275adaa98fb602ffeadf5dc43784cf9d397acd74b6c1dae3dda380709fa9.mp4)

[Target MP4](../../media/videos/ea27275adaa98fb602ffeadf5dc43784cf9d397acd74b6c1dae3dda380709fa9.mp4) · [원본 열기/다운로드](../../media/videos/ea27275adaa98fb602ffeadf5dc43784cf9d397acd74b6c1dae3dda380709fa9.mp4?raw=true) · [Local + Target 5초](../../media/videos/5556c18aee561be7956c5ff9f1871ec97da364e405a93957d32c142e5d3deef0.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P2/image_past/config.json)

참조: Oracle 이미지 · frame 36. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/stills/five_002_robot_head_oracle_frame36.png)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot. The robot model and its display turntable keep the same appearance as in the earlier view.
```

- 참조 모델 좌표: `[0.0000, 0.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 144
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P2/image_past/config.json`

</details>

### P2 Oracle · Video-Past · seed 42

**신규 실행 · run_022**

[![Oracle · Video-Past](../../media/previews/0a871665e2075565b93bafa51366aa81e715aef4048e84fe58f77fc8cbf13843.gif)](../../media/videos/0a871665e2075565b93bafa51366aa81e715aef4048e84fe58f77fc8cbf13843.mp4)

[Target MP4](../../media/videos/0a871665e2075565b93bafa51366aa81e715aef4048e84fe58f77fc8cbf13843.mp4) · [원본 열기/다운로드](../../media/videos/0a871665e2075565b93bafa51366aa81e715aef4048e84fe58f77fc8cbf13843.mp4?raw=true) · [Local + Target 5초](../../media/videos/eef0a604b950b40aa85ffbfcd364e918fac24e457b13b7b64d2a92cd40acefdf.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P2/video_past/config.json)

참조: Oracle 영상 · 전체 프레임. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot. The robot model and its display turntable keep the same appearance as in the earlier view.
```

- 참조 모델 좌표: `[0.0000, 3.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 1440
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P2/video_past/config.json`

</details>

### P3 Local-only · seed 42

**신규 실행 · run_024**

[![Local-only](../../media/previews/c60d3cc7adf752d866446de5cfbe3480e46aa52005fb1e92219470b00f799941.gif)](../../media/videos/c60d3cc7adf752d866446de5cfbe3480e46aa52005fb1e92219470b00f799941.mp4)

[Target MP4](../../media/videos/c60d3cc7adf752d866446de5cfbe3480e46aa52005fb1e92219470b00f799941.mp4) · [원본 열기/다운로드](../../media/videos/c60d3cc7adf752d866446de5cfbe3480e46aa52005fb1e92219470b00f799941.mp4?raw=true) · [Local + Target 5초](../../media/videos/26dd2a2f87cc85ffe0edaba005547c7b53d8162756e1a7d6cbdff8349f198ca7.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P3/local/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot. The robot model and its display turntable keep the same appearance as in the earlier view. The earlier view provides visual details of the robot and its display setting. The model's pose and the camera framing follow the freestanding display shot described here.
```

- 참조 모델 좌표: `[0.0000, 0.0000) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P3/local/config.json`

</details>

### P3 Oracle · Image-Past · seed 42

**신규 실행 · run_023**

[![Oracle · Image-Past](../../media/previews/4358ad93f79296956b45e6ec945b7b6f7d744087c7421cf103a74b9214832c9c.gif)](../../media/videos/4358ad93f79296956b45e6ec945b7b6f7d744087c7421cf103a74b9214832c9c.mp4)

[Target MP4](../../media/videos/4358ad93f79296956b45e6ec945b7b6f7d744087c7421cf103a74b9214832c9c.mp4) · [원본 열기/다운로드](../../media/videos/4358ad93f79296956b45e6ec945b7b6f7d744087c7421cf103a74b9214832c9c.mp4?raw=true) · [Local + Target 5초](../../media/videos/9db49def796f165ffd2e1f40b08e7fb94c2351c04c6f2a7c22f753df7b8f65da.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P3/image_past/config.json)

참조: Oracle 이미지 · frame 36. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/stills/five_002_robot_head_oracle_frame36.png)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot. The robot model and its display turntable keep the same appearance as in the earlier view. The earlier view provides visual details of the robot and its display setting. The model's pose and the camera framing follow the freestanding display shot described here.
```

- 참조 모델 좌표: `[0.0000, 0.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 144
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P3/image_past/config.json`

</details>

### P3 Oracle · Video-Past · seed 42

**신규 실행 · run_025**

[![Oracle · Video-Past](../../media/previews/6a96ad107859e2bea51743c1be495b87698ec868f2ec3871044bf78d68fc4bee.gif)](../../media/videos/6a96ad107859e2bea51743c1be495b87698ec868f2ec3871044bf78d68fc4bee.mp4)

[Target MP4](../../media/videos/6a96ad107859e2bea51743c1be495b87698ec868f2ec3871044bf78d68fc4bee.mp4) · [원본 열기/다운로드](../../media/videos/6a96ad107859e2bea51743c1be495b87698ec868f2ec3871044bf78d68fc4bee.mp4?raw=true) · [Local + Target 5초](../../media/videos/6e54175cbc726c2686e6fad44843bfa06f124d66b5dee41e6d1bd30b94464e7d.mp4) · [원실행 config](../../records/outputs/five_002_robot_head/prompt_control_seed42/P3/video_past/config.json)

참조: Oracle 영상 · 전체 프레임. Local clean prefix + 별도 clean 참조 token + Target noise

[이 조건의 참조 파일](../../media/videos/e15ae741c1e79a9d6f8026dbc0ec88969b744c7d050c4e98aa836f211d4aa5fe.mp4)

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands on its own on its display turntable, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. The model maintains its display pose for the rest of the shot. The robot model and its display turntable keep the same appearance as in the earlier view. The earlier view provides visual details of the robot and its display setting. The model's pose and the camera framing follow the freestanding display shot described here.
```

- 참조 모델 좌표: `[0.0000, 3.0417) s`
- Target 모델 좌표: `[6.0833, 9.0833) s`
- 원본 참조 구간: `[147.0000, 150.0000) s`
- 추가 참조 token: 1440
- 원실행: `outputs/five_002_robot_head/prompt_control_seed42/P3/video_past/config.json`

</details>
