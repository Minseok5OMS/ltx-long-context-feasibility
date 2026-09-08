# 저장 결과 확인과 원실험 재현

[처음](../README.md) · [GitHub 결과 페이지](../browse/README.md)

## GitHub에서 바로 확인

[전체 실험 페이지](../browse/README.md)를 열면 입력과 생성 결과의 GIF를 바로 볼 수 있습니다. 영상은 이미 저장소에 포함되어 있으며 MP4 링크로 원본을 열 수 있습니다. 페이지 탐색에 서버 실행은 필요 없습니다.

## 로컬 HTML 갤러리와 무결성 확인

저장소 루트에서 실행합니다. 갤러리와 HTML 문서는 네트워크 서비스나 GPU 없이 열 수 있습니다.

```bash
python3 scripts/verify_archive.py
python3 -m http.server 8766 --bind 127.0.0.1
```

검증기는 전체 archive file의 SHA256, 120회 실행 목록, 9개 묶음과 재사용 수, 미디어/문서 링크를 검사합니다. `--decode`를 추가하면 PyAV가 설치된 환경에서 모든 고유 MP4를 전체 decode하여 저장된 frame 수를 확인합니다. 이 검증은 영상 재생성이나 원래 GPU noise/latent 감사를 다시 수행하지 않습니다. 원래 감사 보고서는 `records/`에 보존했습니다.

## 원실행 환경

| 요소 | 기록된 값 |
|---|---|
| LTX commit | `a95ab856bf29407b6b066ede0abe1846050db56c` |
| Python | 3.13 |
| PyTorch / CUDA | `2.13.0+cu132` / `13.2` |
| GPU | NVIDIA RTX PRO 6000 Blackwell Server Edition |
| 실행 | 기존 LTX 환경의 `uv run --no-sync` |
| 모델 | LTX 2.5 22B distilled BF16 transformer, video VAE, Gemma4-12B with projection |

정확한 명령·cwd·물리 GPU·prompt·sampler·seed·모델 파일 크기·해시·출력 정보는 [실행 목록](../results/runs.csv)에서 각 원본 config로 연결됩니다. 모델 기록의 파일 크기/mtime를 전체 가중치의 암호학적 checksum으로 오해하지 않습니다. [환경 기록](../repro/environment.json)

## 코드·설정 보존

`repro/longcond/feasibility_long_context/`에 현재 실행 코드와 설정을 원래 바이트 그대로 보존했습니다. 하위 `outputs/.../source_snapshot/`은 각 batch 실행 시점의 동결 코드입니다. 기록된 script hash와 snapshot을 먼저 확인합니다. `repro/original_notes.tar.gz`는 원래 문서와 연구 개념을 수정 없이 보존한 역사 기록입니다. 문서의 “미실행”이나 “95회”는 작성 당시 상태일 수 있습니다.

원래 코드 중 일부는 `<LTX_ROOT>/longcond/feasibility_long_context` 배치나 당시 절대 경로와 입력 cache를 전제합니다. 이 archive를 clone하는 것만으로 GPU 재생성이 바로 되는 portable package는 아닙니다. 원본 전체 영상, 모델, RGB/latent/text/noise tensor cache는 별도 보관합니다. 새 환경에서 실행하려면 기록된 LTX revision과 의존성, 접근 가능한 FineVideo 원본, 로컬 모델 경로, 해당 코드가 요구하는 입력/캐시를 준비해야 합니다. archive 작업에서는 새 환경 GPU 재실행을 하지 않았습니다.

## 기존 연구 환경에서 마지막 비교를 실행했던 명령

기준 디렉터리: `/mnt/minu/minseok/LTX-2/longcond`. 아래 명령은 **기록된 실행 절차**이며, archive를 정리할 때 실행하지 않았습니다. 완료 job을 건너뛰는 batch의 동작을 고려해 신규 재현 결과는 별도 작업 공간에 둡니다.

```bash
uv --cache-dir /tmp/ltx-longcond-uv-cache run --no-sync --project .. python feasibility_long_context/prepare_long_input_data.py
uv --cache-dir /tmp/ltx-longcond-uv-cache run --no-sync --project .. python feasibility_long_context/run_long_input_batch.py --phase cache --gpu 0
uv --cache-dir /tmp/ltx-longcond-uv-cache run --no-sync --project .. python feasibility_long_context/run_long_input_batch.py --phase generate --gpu 0
uv --cache-dir /tmp/ltx-longcond-uv-cache run --no-sync --project .. python feasibility_long_context/verify_long_input.py
uv --cache-dir /tmp/ltx-longcond-uv-cache run --no-sync --project .. python feasibility_long_context/evaluate_long_input.py --gpu 2
```

마지막 25조건 비용 비교는 모두 GPU 0에서 완료했습니다. 이후 허용 GPU는 0–4이나 동결 설정을 소급 수정하지 않습니다. 모델/전체 FineVideo 재다운로드를 자동 시작하는 설치 스크립트는 두지 않았습니다.
