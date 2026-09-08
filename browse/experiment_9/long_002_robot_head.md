# 32초 전체 / 선택 chunk · 로봇 모형의 가려졌던 머리

[이 실험의 사례 목록](README.md) · [전체 실험](../README.md) · [입력 방식](../../docs/METHODS.md)

같은 연속 과거 32초의 Local / Native-Full / Full-reference / Oracle-sparse / Uniform-sparse입니다. 실제 참조 좌표를 보존했습니다. Sparse clip은 bank의 선택 위치를 보여주는 RGB 표시 영상입니다.

Oracle은 각진 helmet·금색 앞면을 손 없는 새 display와 결합합니다. 원본 후속은 요청 구도의 GT가 아닙니다.

**GIF는 축소 미리보기(8 FPS)입니다.** 모든 생성 Target은 원본 3초입니다. 미리보기 또는 MP4 링크를 클릭하면 저장소 파일을 열 수 있습니다. 재사용 표시는 같은 원실행을 다시 비교했다는 뜻입니다.

## 실제 입력과 평가용 후속

Local은 생성 조건입니다. 원본 후속은 입력에 넣지 않았습니다. Oracle/Uniform clip은 명목 구간 표시이며 독립 VAE 입력이 아닙니다.

### Local · 고정 생성 조건

[![Local · 고정 생성 조건](../../media/previews/53b4b6656a571bec0af8baf41078f5165b8c57ef8e9b79ee1421f3bdb54931c8.gif)](../../media/videos/53b4b6656a571bec0af8baf41078f5165b8c57ef8e9b79ee1421f3bdb54931c8.mp4)

RGB 표시 · 48 frames / 24 FPS · [MP4 파일](../../media/videos/53b4b6656a571bec0af8baf41078f5165b8c57ef8e9b79ee1421f3bdb54931c8.mp4) · [원본 열기/다운로드](../../media/videos/53b4b6656a571bec0af8baf41078f5165b8c57ef8e9b79ee1421f3bdb54931c8.mp4?raw=true)

### 연속 과거 32초 · 정지 미리보기

[![연속 과거 32초 · 정지 미리보기](../../media/posters/6537c0e59359edfd48c5d67a34cc71c72302a040c928b3954377b5c02e0d4920.jpg)](../../media/videos/6537c0e59359edfd48c5d67a34cc71c72302a040c928b3954377b5c02e0d4920.mp4)

RGB 표시 · 768 frames / 24 FPS · [MP4 파일](../../media/videos/6537c0e59359edfd48c5d67a34cc71c72302a040c928b3954377b5c02e0d4920.mp4) · [원본 열기/다운로드](../../media/videos/6537c0e59359edfd48c5d67a34cc71c72302a040c928b3954377b5c02e0d4920.mp4?raw=true)

### Oracle · 과거 증거

[![Oracle · 과거 증거](../../media/previews/ee1546f8e4fef7d6967b30dea840d6a0598de50d78646f30c7664039a1444337.gif)](../../media/videos/ee1546f8e4fef7d6967b30dea840d6a0598de50d78646f30c7664039a1444337.mp4)

RGB 표시 · 72 frames / 24 FPS · 실제 입력은 H bank의 latent 부분집합 · [MP4 파일](../../media/videos/ee1546f8e4fef7d6967b30dea840d6a0598de50d78646f30c7664039a1444337.mp4) · [원본 열기/다운로드](../../media/videos/ee1546f8e4fef7d6967b30dea840d6a0598de50d78646f30c7664039a1444337.mp4?raw=true)

### Uniform · 중앙 구간

[![Uniform · 중앙 구간](../../media/previews/2ed497a6b7e9d92f10fe3830500039b23dec80885df5af95be5b37d28b929e9e.gif)](../../media/videos/2ed497a6b7e9d92f10fe3830500039b23dec80885df5af95be5b37d28b929e9e.mp4)

RGB 표시 · 72 frames / 24 FPS · 실제 입력은 H bank의 latent 부분집합 · [MP4 파일](../../media/videos/2ed497a6b7e9d92f10fe3830500039b23dec80885df5af95be5b37d28b929e9e.mp4) · [원본 열기/다운로드](../../media/videos/2ed497a6b7e9d92f10fe3830500039b23dec80885df5af95be5b37d28b929e9e.mp4?raw=true)

### 원본 후속 · 생성 입력 제외

[![원본 후속 · 생성 입력 제외](../../media/previews/1be0b1aec988bc0ade7921e85eaed5eabb74d933ac8fb1825946ec7f02a48c3c.gif)](../../media/videos/1be0b1aec988bc0ade7921e85eaed5eabb74d933ac8fb1825946ec7f02a48c3c.mp4)

원본 후속 · 요청한 display의 GT 아님 · GT DINO 제외 · [MP4 파일](../../media/videos/1be0b1aec988bc0ade7921e85eaed5eabb74d933ac8fb1825946ec7f02a48c3c.mp4) · [원본 열기/다운로드](../../media/videos/1be0b1aec988bc0ade7921e85eaed5eabb74d933ac8fb1825946ec7f02a48c3c.mp4?raw=true)

원본: HG Obsidian Fury Review (Pacific Rim Uprising) · [구간·출처 metadata](../../records/data/long_input/long_002_robot_head/metadata.json)

## 생성 결과

###  Local-only · seed 42

**신규 실행 · run_077**

[![Local-only](../../media/previews/1bb8d7c2fb496ff1f9acd24f8d58a35a228c5107ce27666fbb0d6be9c1ac5bd7.gif)](../../media/videos/1bb8d7c2fb496ff1f9acd24f8d58a35a228c5107ce27666fbb0d6be9c1ac5bd7.mp4)

[Target MP4](../../media/videos/1bb8d7c2fb496ff1f9acd24f8d58a35a228c5107ce27666fbb0d6be9c1ac5bd7.mp4) · [원본 열기/다운로드](../../media/videos/1bb8d7c2fb496ff1f9acd24f8d58a35a228c5107ce27666fbb0d6be9c1ac5bd7.mp4?raw=true) · [Local + Target 5초](../../media/videos/171087f24ba6c01c57766d51435110e9c74c439a9a519b813aa25cec4fad8e1f.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_002_robot_head/local/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

Denoising **2.727 s**, peak allocated **35.970 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands upright on its own, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. Its helmet and face retain their appearance from the earlier view. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `원본 config 참조`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/long_input/seed42/long_002_robot_head/local/config.json`

</details>

###  Native-Full · 연속 32초 · seed 42

**신규 실행 · run_078**

[![Native-Full · 연속 32초](../../media/previews/7353b0ff45c64fd43769e5d85bf34e0e741006d556a8ee9a81cc33abfe94755b.gif)](../../media/videos/7353b0ff45c64fd43769e5d85bf34e0e741006d556a8ee9a81cc33abfe94755b.mp4)

[Target MP4](../../media/videos/7353b0ff45c64fd43769e5d85bf34e0e741006d556a8ee9a81cc33abfe94755b.mp4) · [원본 열기/다운로드](../../media/videos/7353b0ff45c64fd43769e5d85bf34e0e741006d556a8ee9a81cc33abfe94755b.mp4?raw=true) · [Local + Target 5초](../../media/videos/642978c96b4905d66270b7502d62def6841cac54330957a4cba3eb8d226b8844.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_002_robot_head/native_full/config.json)

참조: 연속 32초 · clean prefix. 연속 인코딩한 97 latent prefix + Target noise; 전체 video token 15,264

[이 조건의 참조 파일](../../media/videos/6537c0e59359edfd48c5d67a34cc71c72302a040c928b3954377b5c02e0d4920.mp4)

Denoising **18.046 s**, peak allocated **39.016 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands upright on its own, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. Its helmet and face retain their appearance from the earlier view. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[0.0000, 32.0417) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[228.0000, 260.0000) s`
- 추가 참조 token: 0
- 원실행: `outputs/long_input/seed42/long_002_robot_head/native_full/config.json`

</details>

###  Full-reference · H 전체 · seed 42

**신규 실행 · run_076**

[![Full-reference · H 전체](../../media/previews/df1d9cead6f31074416a7bc6c2a0d4a33537cd97046cc911dbaf910f7a6c5fb3.gif)](../../media/videos/df1d9cead6f31074416a7bc6c2a0d4a33537cd97046cc911dbaf910f7a6c5fb3.mp4)

[Target MP4](../../media/videos/df1d9cead6f31074416a7bc6c2a0d4a33537cd97046cc911dbaf910f7a6c5fb3.mp4) · [원본 열기/다운로드](../../media/videos/df1d9cead6f31074416a7bc6c2a0d4a33537cd97046cc911dbaf910f7a6c5fb3.mp4?raw=true) · [Local + Target 5초](../../media/videos/8188fe0e7b01b25ba566c75c69bc558d02f7aaa8379666708d039d36cf5563d3.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_002_robot_head/full_reference/config.json)

참조: 이 32초의 앞 H 30초 전체. H 91 latent를 별도 추가 + 독립 Local + Target; 전체 video token 15,408

[이 조건의 참조 파일](../../media/videos/6537c0e59359edfd48c5d67a34cc71c72302a040c928b3954377b5c02e0d4920.mp4)

Denoising **18.199 s**, peak allocated **39.049 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands upright on its own, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. Its helmet and face retain their appearance from the earlier view. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[0.0000, 30.0417) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[228.0000, 258.0000) s`
- 추가 참조 token: 13104
- 원실행: `outputs/long_input/seed42/long_002_robot_head/full_reference/config.json`

</details>

###  Oracle-sparse · 선택 chunk · seed 42

**신규 실행 · run_079**

[![Oracle-sparse · 선택 chunk](../../media/previews/2998f4e5a180f41f7e771b39eb7109ee7d658904b2192d2b5d872ea8e03aeed9.gif)](../../media/videos/2998f4e5a180f41f7e771b39eb7109ee7d658904b2192d2b5d872ea8e03aeed9.mp4)

[Target MP4](../../media/videos/2998f4e5a180f41f7e771b39eb7109ee7d658904b2192d2b5d872ea8e03aeed9.mp4) · [원본 열기/다운로드](../../media/videos/2998f4e5a180f41f7e771b39eb7109ee7d658904b2192d2b5d872ea8e03aeed9.mp4?raw=true) · [Local + Target 5초](../../media/videos/c599e60269634a58fc9b4dc3cd8313fb3fd62bd5c0f6df71645e3e9bc89c956c.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_002_robot_head/oracle_sparse/config.json)

참조: Oracle 명목 RGB 구간 · 실제 입력은 H bank의 9 latent. Full H bank의 정확한 부분집합 + 독립 Local + Target; 전체 video token 3,600

[이 조건의 참조 파일](../../media/videos/ee1546f8e4fef7d6967b30dea840d6a0598de50d78646f30c7664039a1444337.mp4)

Denoising **3.870 s**, peak allocated **36.276 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands upright on its own, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. Its helmet and face retain their appearance from the earlier view. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[9.3750, 12.3750) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[237.3333, 240.3333) s`
- 추가 참조 token: 1296
- 원실행: `outputs/long_input/seed42/long_002_robot_head/oracle_sparse/config.json`

</details>

###  Uniform-sparse · 중앙 chunk · seed 42

**신규 실행 · run_080**

[![Uniform-sparse · 중앙 chunk](../../media/previews/0872125833f7b095c41191be8da29e5734a93227bdebfc1d337d3c320ebb72cf.gif)](../../media/videos/0872125833f7b095c41191be8da29e5734a93227bdebfc1d337d3c320ebb72cf.mp4)

[Target MP4](../../media/videos/0872125833f7b095c41191be8da29e5734a93227bdebfc1d337d3c320ebb72cf.mp4) · [원본 열기/다운로드](../../media/videos/0872125833f7b095c41191be8da29e5734a93227bdebfc1d337d3c320ebb72cf.mp4?raw=true) · [Local + Target 5초](../../media/videos/742dab6d556cdbed8864f337cc434ac2c8d288077198a1fba9ff9f2e51d24ee7.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_002_robot_head/uniform_sparse/config.json)

참조: Uniform 명목 RGB 구간 · 실제 입력은 H bank의 9 latent. Full H bank의 정확한 부분집합 + 독립 Local + Target; 전체 video token 3,600

[이 조건의 참조 파일](../../media/videos/2ed497a6b7e9d92f10fe3830500039b23dec80885df5af95be5b37d28b929e9e.mp4)

Denoising **3.868 s**, peak allocated **36.276 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
The close-up of the robot's lower body ends with a hard cut to a wider display shot. The same robot model stands upright on its own, with its entire head, both shoulders and upper torso comfortably inside the frame. The camera is fixed at the model's head height. Its helmet and face retain their appearance from the earlier view. The model maintains its display pose for the rest of the shot.
```

- 참조 모델 좌표: `[13.3750, 16.3750) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[241.3333, 244.3333) s`
- 추가 참조 token: 1296
- 원실행: `outputs/long_input/seed42/long_002_robot_head/uniform_sparse/config.json`

</details>
