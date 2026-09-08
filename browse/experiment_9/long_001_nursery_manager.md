# 32초 전체 / 선택 chunk · 보육원 직원 재등장 (새 구간)

[이 실험의 사례 목록](README.md) · [전체 실험](../README.md) · [입력 방식](../../docs/METHODS.md)

같은 연속 과거 32초의 Local / Native-Full / Full-reference / Oracle-sparse / Uniform-sparse입니다. 실제 참조 좌표를 보존했습니다. Sparse clip은 bank의 선택 위치를 보여주는 RGB 표시 영상입니다.

Oracle에서 필요한 직원 외관이 드러나지만 참조 구도를 따릅니다. 앞선 관리자 사례와 Target 시점 및 인물이 다릅니다.

**GIF는 축소 미리보기(8 FPS)입니다.** 모든 생성 Target은 원본 3초입니다. 미리보기 또는 MP4 링크를 클릭하면 저장소 파일을 열 수 있습니다. 재사용 표시는 같은 원실행을 다시 비교했다는 뜻입니다.

## 실제 입력과 평가용 후속

Local은 생성 조건입니다. 원본 후속은 입력에 넣지 않았습니다. Oracle/Uniform clip은 명목 구간 표시이며 독립 VAE 입력이 아닙니다.

### Local · 고정 생성 조건

[![Local · 고정 생성 조건](../../media/previews/44066acc0d0304e11efa0f4a4f5658a4cfd121a2e3a45ceda59896a4ff9917b4.gif)](../../media/videos/44066acc0d0304e11efa0f4a4f5658a4cfd121a2e3a45ceda59896a4ff9917b4.mp4)

RGB 표시 · 48 frames / 24 FPS · [MP4 파일](../../media/videos/44066acc0d0304e11efa0f4a4f5658a4cfd121a2e3a45ceda59896a4ff9917b4.mp4) · [원본 열기/다운로드](../../media/videos/44066acc0d0304e11efa0f4a4f5658a4cfd121a2e3a45ceda59896a4ff9917b4.mp4?raw=true)

### 연속 과거 32초 · 정지 미리보기

[![연속 과거 32초 · 정지 미리보기](../../media/posters/89bae05c6032692c091bf54c683c177ad4de6f827f0c1b5cc13ba12119356497.jpg)](../../media/videos/89bae05c6032692c091bf54c683c177ad4de6f827f0c1b5cc13ba12119356497.mp4)

RGB 표시 · 768 frames / 24 FPS · [MP4 파일](../../media/videos/89bae05c6032692c091bf54c683c177ad4de6f827f0c1b5cc13ba12119356497.mp4) · [원본 열기/다운로드](../../media/videos/89bae05c6032692c091bf54c683c177ad4de6f827f0c1b5cc13ba12119356497.mp4?raw=true)

### Oracle · 과거 증거

[![Oracle · 과거 증거](../../media/previews/0b4e5c2bf826d700fc92d87aff231498f1a46ee051c2cf957cd895442673fba7.gif)](../../media/videos/0b4e5c2bf826d700fc92d87aff231498f1a46ee051c2cf957cd895442673fba7.mp4)

RGB 표시 · 72 frames / 24 FPS · 실제 입력은 H bank의 latent 부분집합 · [MP4 파일](../../media/videos/0b4e5c2bf826d700fc92d87aff231498f1a46ee051c2cf957cd895442673fba7.mp4) · [원본 열기/다운로드](../../media/videos/0b4e5c2bf826d700fc92d87aff231498f1a46ee051c2cf957cd895442673fba7.mp4?raw=true)

### Uniform · 중앙 구간

[![Uniform · 중앙 구간](../../media/previews/3f2f6693cd8747108d19781dd264abfb61c5c78407eb53c646ce6689284589e8.gif)](../../media/videos/3f2f6693cd8747108d19781dd264abfb61c5c78407eb53c646ce6689284589e8.mp4)

RGB 표시 · 72 frames / 24 FPS · 실제 입력은 H bank의 latent 부분집합 · [MP4 파일](../../media/videos/3f2f6693cd8747108d19781dd264abfb61c5c78407eb53c646ce6689284589e8.mp4) · [원본 열기/다운로드](../../media/videos/3f2f6693cd8747108d19781dd264abfb61c5c78407eb53c646ce6689284589e8.mp4?raw=true)

### 원본 후속 · 생성 입력 제외

[![원본 후속 · 생성 입력 제외](../../media/previews/efe33c216da9b2d0ab445ab7a308fa038498d252cfc59c82830f6278cc1ff552.gif)](../../media/videos/efe33c216da9b2d0ab445ab7a308fa038498d252cfc59c82830f6278cc1ff552.mp4)

원본 후속 · 생성 입력 제외 · [MP4 파일](../../media/videos/efe33c216da9b2d0ab445ab7a308fa038498d252cfc59c82830f6278cc1ff552.mp4) · [원본 열기/다운로드](../../media/videos/efe33c216da9b2d0ab445ab7a308fa038498d252cfc59c82830f6278cc1ff552.mp4?raw=true)

원본: Kerry Mills | Trainer Assessor · [구간·출처 metadata](../../records/data/long_input/long_001_nursery_manager/metadata.json)

## 생성 결과

###  Local-only · seed 42

**신규 실행 · run_072**

[![Local-only](../../media/previews/c5e38ba3b1459df6ab0f3e0dd7296a7de7f52b47d3b159de2ecb269c76c45617.gif)](../../media/videos/c5e38ba3b1459df6ab0f3e0dd7296a7de7f52b47d3b159de2ecb269c76c45617.mp4)

[Target MP4](../../media/videos/c5e38ba3b1459df6ab0f3e0dd7296a7de7f52b47d3b159de2ecb269c76c45617.mp4) · [원본 열기/다운로드](../../media/videos/c5e38ba3b1459df6ab0f3e0dd7296a7de7f52b47d3b159de2ecb269c76c45617.mp4?raw=true) · [Local + Target 5초](../../media/videos/d994ec45029f05c216cf3d0e146eb6873fef148934f82313d38644d779183ee8.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_001_nursery_manager/local/config.json)

참조: 추가 참조 없음. Local clean prefix + Target noise

Denoising **2.718 s**, peak allocated **35.970 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
A hard cut switches from the visiting assessor to a three-quarter side-angle medium close-up of the same nursery staff member who was seated at the laptop earlier. Her face and shoulders remain fully visible as she speaks and makes a small hand gesture. The camera stays fixed on the staff member in the childcare room.
```

- 참조 모델 좌표: `원본 config 참조`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `원본 config 참조`
- 추가 참조 token: 0
- 원실행: `outputs/long_input/seed42/long_001_nursery_manager/local/config.json`

</details>

###  Native-Full · 연속 32초 · seed 42

**신규 실행 · run_073**

[![Native-Full · 연속 32초](../../media/previews/da9e1fb2f82a9e1028c7a37517e0b41aba7a9bac671866a12fb798c03e83099e.gif)](../../media/videos/da9e1fb2f82a9e1028c7a37517e0b41aba7a9bac671866a12fb798c03e83099e.mp4)

[Target MP4](../../media/videos/da9e1fb2f82a9e1028c7a37517e0b41aba7a9bac671866a12fb798c03e83099e.mp4) · [원본 열기/다운로드](../../media/videos/da9e1fb2f82a9e1028c7a37517e0b41aba7a9bac671866a12fb798c03e83099e.mp4?raw=true) · [Local + Target 5초](../../media/videos/ed9ec16d452325834e5025e4d15c7f59af5657d4bd0d6da482f2b9259686dbe0.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_001_nursery_manager/native_full/config.json)

참조: 연속 32초 · clean prefix. 연속 인코딩한 97 latent prefix + Target noise; 전체 video token 15,264

[이 조건의 참조 파일](../../media/videos/89bae05c6032692c091bf54c683c177ad4de6f827f0c1b5cc13ba12119356497.mp4)

Denoising **18.023 s**, peak allocated **39.016 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
A hard cut switches from the visiting assessor to a three-quarter side-angle medium close-up of the same nursery staff member who was seated at the laptop earlier. Her face and shoulders remain fully visible as she speaks and makes a small hand gesture. The camera stays fixed on the staff member in the childcare room.
```

- 참조 모델 좌표: `[0.0000, 32.0417) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[77.8431, 109.8431) s`
- 추가 참조 token: 0
- 원실행: `outputs/long_input/seed42/long_001_nursery_manager/native_full/config.json`

</details>

###  Full-reference · H 전체 · seed 42

**신규 실행 · run_071**

[![Full-reference · H 전체](../../media/previews/b3a9eafe5c703e27efc41626c9063c7e60636d4d39f331d83ddd57442c69678c.gif)](../../media/videos/b3a9eafe5c703e27efc41626c9063c7e60636d4d39f331d83ddd57442c69678c.mp4)

[Target MP4](../../media/videos/b3a9eafe5c703e27efc41626c9063c7e60636d4d39f331d83ddd57442c69678c.mp4) · [원본 열기/다운로드](../../media/videos/b3a9eafe5c703e27efc41626c9063c7e60636d4d39f331d83ddd57442c69678c.mp4?raw=true) · [Local + Target 5초](../../media/videos/2de5b9cbd57fc5ec86fdd29abdecd8277ea703a18a3b5eb77523e55c3a4769d2.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_001_nursery_manager/full_reference/config.json)

참조: 이 32초의 앞 H 30초 전체. H 91 latent를 별도 추가 + 독립 Local + Target; 전체 video token 15,408

[이 조건의 참조 파일](../../media/videos/89bae05c6032692c091bf54c683c177ad4de6f827f0c1b5cc13ba12119356497.mp4)

Denoising **18.181 s**, peak allocated **39.049 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
A hard cut switches from the visiting assessor to a three-quarter side-angle medium close-up of the same nursery staff member who was seated at the laptop earlier. Her face and shoulders remain fully visible as she speaks and makes a small hand gesture. The camera stays fixed on the staff member in the childcare room.
```

- 참조 모델 좌표: `[0.0000, 30.0417) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[77.8431, 107.8431) s`
- 추가 참조 token: 13104
- 원실행: `outputs/long_input/seed42/long_001_nursery_manager/full_reference/config.json`

</details>

###  Oracle-sparse · 선택 chunk · seed 42

**신규 실행 · run_074**

[![Oracle-sparse · 선택 chunk](../../media/previews/3530d812f9ca4fa7069095fd51022f43057736481d94e413c430a05031a2b4a9.gif)](../../media/videos/3530d812f9ca4fa7069095fd51022f43057736481d94e413c430a05031a2b4a9.mp4)

[Target MP4](../../media/videos/3530d812f9ca4fa7069095fd51022f43057736481d94e413c430a05031a2b4a9.mp4) · [원본 열기/다운로드](../../media/videos/3530d812f9ca4fa7069095fd51022f43057736481d94e413c430a05031a2b4a9.mp4?raw=true) · [Local + Target 5초](../../media/videos/76680350fec3174c06437f53ab979eea63d3c94c5362a455796eab1b18064ad6.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_001_nursery_manager/oracle_sparse/config.json)

참조: Oracle 명목 RGB 구간 · 실제 입력은 H bank의 9 latent. Full H bank의 정확한 부분집합 + 독립 Local + Target; 전체 video token 3,600

[이 조건의 참조 파일](../../media/videos/0b4e5c2bf826d700fc92d87aff231498f1a46ee051c2cf957cd895442673fba7.mp4)

Denoising **3.865 s**, peak allocated **36.276 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
A hard cut switches from the visiting assessor to a three-quarter side-angle medium close-up of the same nursery staff member who was seated at the laptop earlier. Her face and shoulders remain fully visible as she speaks and makes a small hand gesture. The camera stays fixed on the staff member in the childcare room.
```

- 참조 모델 좌표: `[5.3750, 8.3750) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[83.1764, 86.1764) s`
- 추가 참조 token: 1296
- 원실행: `outputs/long_input/seed42/long_001_nursery_manager/oracle_sparse/config.json`

</details>

###  Uniform-sparse · 중앙 chunk · seed 42

**신규 실행 · run_075**

[![Uniform-sparse · 중앙 chunk](../../media/previews/4279c83aef10ca0c64dcb0b9a7f11d0fc4f37f6c2b21991f920c79243724d8cf.gif)](../../media/videos/4279c83aef10ca0c64dcb0b9a7f11d0fc4f37f6c2b21991f920c79243724d8cf.mp4)

[Target MP4](../../media/videos/4279c83aef10ca0c64dcb0b9a7f11d0fc4f37f6c2b21991f920c79243724d8cf.mp4) · [원본 열기/다운로드](../../media/videos/4279c83aef10ca0c64dcb0b9a7f11d0fc4f37f6c2b21991f920c79243724d8cf.mp4?raw=true) · [Local + Target 5초](../../media/videos/99c561d776a9546c187de08aa973e2da8ad65e8f97db16282e29de4ade12486d.mp4) · [원실행 config](../../records/outputs/long_input/seed42/long_001_nursery_manager/uniform_sparse/config.json)

참조: Uniform 명목 RGB 구간 · 실제 입력은 H bank의 9 latent. Full H bank의 정확한 부분집합 + 독립 Local + Target; 전체 video token 3,600

[이 조건의 참조 파일](../../media/videos/3f2f6693cd8747108d19781dd264abfb61c5c78407eb53c646ce6689284589e8.mp4)

Denoising **3.877 s**, peak allocated **36.276 GiB**.

<details>
<summary>Prompt · 시간 좌표 · 원실행</summary>

```text
A hard cut switches from the visiting assessor to a three-quarter side-angle medium close-up of the same nursery staff member who was seated at the laptop earlier. Her face and shoulders remain fully visible as she speaks and makes a small hand gesture. The camera stays fixed on the staff member in the childcare room.
```

- 참조 모델 좌표: `[13.3750, 16.3750) s`
- Target 모델 좌표: `[32.0417, 35.0417) s`
- 원본 참조 구간: `[91.1764, 94.1764) s`
- 추가 참조 token: 1296
- 원실행: `outputs/long_input/seed42/long_001_nursery_manager/uniform_sparse/config.json`

</details>
