# 실제 입력 방식과 비교 통제

[GitHub 결과 페이지](../browse/README.md) · [처음](../README.md)

## Local은 생성 조건이다

독립 Local 2초의 첫 프레임을 한 번 padding해 49 RGB frame으로 VAE 인코딩하고, 7 latent frame을 생성 sequence의 clean prefix로 고정합니다. 뒤의 9 latent frame은 noise에서 denoising해 새 Target 72 RGB frame, 3초를 만듭니다. 고정 prefix도 생성 중 attention에 참여합니다. 단순히 출력 영상 앞에 붙이는 작업만 한 것이 아닙니다.

디코딩은 conditioning 7 + Target 9 latent에서 121 RGB frame을 얻고 `[49:121]`만 Target으로 평가합니다. 별도의 continuation 영상은 원본 Local 48 frame과 생성 Target 72 frame을 붙인 5초 표시 영상입니다. 갤러리의 기본 출력은 **새로 생성한 Target 3초**입니다.

## 추가 참조와 시간 좌표

초기 참조 경로는 `VideoConditionByKeyframeIndex`로 별도 clean reference token을 sequence 뒤에 추가합니다. `frame_idx`는 참조의 좌표를 지정하며, 생성 시작 latent를 참조 이미지로 덮어쓴다는 뜻은 아닙니다. 고정 Local prefix는 `VideoConditionByLatentIndex`로 별도 설정합니다. `VideoConditionByReferenceLatent`의 이름만으로 시간 좌표가 없다고 해석할 수 없으며 해당 경로도 위치를 구성합니다.

초기 인터뷰 및 5개 사례의 기본 배치는 다음과 같습니다. 정확한 조건별 값은 갤러리의 실행 기록에서 확인합니다.

| 요소 | 모델 시간 좌표 |
|---|---|
| Image-Past | `[0, 1/24)`초 |
| Video-Past | `[0, 73/24)`초 |
| Local | `[97/24, 146/24)`초 |
| Target | `[146/24, 218/24)`초 |
| Target 배치 참조 | 같은 과거 증거의 시작을 `146/24`초로 이동 |

이는 token 구간 경계입니다. 원본에서 60초 이상 떨어진 증거도 위 모델 배치로 입력했으므로 원본 의존 거리와 RoPE 거리는 다릅니다. 반복/동일 좌표 진단은 별도의 지정 배치를 사용합니다. 현재 경로는 위치 정보를 사용하며, 시간 좌표 0은 위치 인코딩 제거가 아닙니다.

**IC-LoRA, Ingredients adapter, 피사체 추출, 배경 제거는 이번 생성에 사용하지 않았습니다.** 참조 형식·양·좌표와 prompt를 frozen 모델에서 바꾼 실험입니다.

## 마지막 32초 비교

`[T−32,T)`를 H 30초와 Local 2초로 나눕니다. Target은 이후 3초입니다.

| 조건 | VAE / attention 구성 |
|---|---|
| Local-only | 독립 Local 7 latent + Target 9 latent |
| Native-Full | 연속 과거 32초를 인코딩한 97 latent prefix + Target 9 latent |
| Full-reference | H 전체 91 latent를 별도 참조로 추가 + 독립 Local + Target |
| Oracle-sparse | 같은 H bank 중 수동 선택한 연속 9 latent + 독립 Local + Target |
| Uniform-sparse | H bank 중앙 index 41–49의 9 latent + 독립 Local + Target |

전체 768 RGB frame을 실제로 읽었습니다. 첫 프레임 padding 뒤 Native/H/Local은 769/721/49 RGB frame이며, 공식 VAE temporal tiled encode(tile 80, overlap 24)를 사용했습니다. 긴 영상을 짧은 장면 반복으로 만들지 않았습니다. Transformer는 매 step 전체 Native/Full token을 받습니다.

Sparse의 latent와 좌표는 Full H bank의 정확한 부분집합입니다. 참조를 Target으로 옮기지 않습니다. 공통 Target 좌표는 `[769/24,841/24)`, Local은 `[30,769/24)`, H는 `[0,721/24)`초입니다. 첫 padding 때문에 H/Local 경계에 1/24초 겹침이 있습니다.

Native와 Full은 연속 인코딩 대 독립 Local의 경계 효과도 다릅니다. 따라서 Native/Oracle은 실제 방식 비교, Full/Oracle은 같은 bank에서 선택의 효과를 비교하는 짝입니다. Sparse 9 latent에는 VAE temporal receptive field에 따른 주변 정보가 있을 수 있어 RGB 3초만 독립 인코딩한 조건과 같지 않습니다. 갤러리의 Oracle/Uniform RGB clip은 선택 위치를 보여 주는 영상이며 실제 모델 입력은 bank의 latent입니다.

## 실행 설정과 검증

LTX 2.5 22B distilled BF16, 512×288, 24 FPS, Target 72 frame, 8-step Euler ancestral, eta=1, s_noise=1, SimpleDenoiser입니다. CFG/STG, prompt enhancement, LoRA, 추가 refinement는 없습니다. 공통 audio를 함께 생성하지만 입력 audio와 출력 audio decode/평가는 사용하지 않았습니다. 마지막 실험의 audio 크기는 5.0417초이며 긴 입력 baseline에 35초 audio 생성을 추가하지 않았습니다.

각 비교의 prompt, 모델, 해상도, 길이, sampler, seed, Target 초기 noise와 7회 step noise를 통제했습니다. GT Target은 조건에 넣지 않았습니다. 실제 clean token 고정 오차와 Target/audio 좌표를 검사했습니다. 마지막 25조건은 입력·좌표·noise·부분집합·75개 출력 영상의 7,825 frame decode 감사를 통과했습니다. CPU 이론좌표 재계산의 1 ULP 허용과 실제 GPU 조건 간 bit 단위 일치를 구분합니다.

[마지막 동결 설정](../repro/longcond/feasibility_long_context/configs/long_input_cases.json) · [원감사](../records/reports/long_input/artifact_verification.json) · [전체 실행 목록](../results/runs.csv)
