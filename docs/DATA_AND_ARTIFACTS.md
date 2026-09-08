# 데이터와 산출물

[처음](../README.md) · [GitHub 결과 페이지](../browse/README.md)

FineVideo `HuggingFaceFV/finevideo` revision `84c74091e1c6ee7a5dffabfafb5c9033e4718883`에서 선택한 원본을 사용했습니다. 두 초기 인터뷰는 같은 원본이며 마지막 5개 사례는 앞선 5개 원본을 다시 사용했습니다. [사례 metadata](../results/cases.json)에 원본 제목, shard/row, source hash, 구간, 실제 사용한 prompt 및 기존 진단의 제한을 연결했습니다.

## 갤러리에서 무엇을 보는가

- **Local:** 생성 중 clean prefix로 고정한 최근 구간의 RGB 표시 영상.
- **Oracle/Random 이미지:** 짧은 참조 clip의 정확한 중간 frame. 갤러리에 frame index와 표시 영상을 구분합니다. 반복 실험은 같은 이미지 latent를 복제했습니다.
- **Oracle/Random 영상:** 초기 실험에서 VAE로 인코딩한 원본 전체 프레임의 짧은 clip.
- **History 32초:** 긴 입력 비교의 실제 연속 과거를 표시하는 영상. 전체 원본 파일은 별도입니다.
- **긴 입력 Oracle/Uniform clip:** bank에서 선택한 latent 위치에 대응하는 명목 RGB 구간. 이 clip을 독립 VAE 인코딩해 넣은 것이 아닙니다.
- **원본 후속 / GT:** 평가 또는 시간 후속 확인용이며 생성 입력이 아닙니다. 긴 입력 로봇은 요청한 display의 유효한 GT가 아닙니다.
- **생성 Target:** 새로 생성한 3초, 72 frame. **Local + Target 보기**의 앞 2초는 원본 Local입니다.

## 저장소 구성

| 경로 | 내용 |
|---|---|
| `browse/`, `media/previews/` | GitHub용 실험·사례별 Markdown과 움직이는 축소 GIF |
| `index.html`, `site/` | 실제 조건명과 재사용 표시를 갖춘 정적 갤러리 |
| `docs/`, `README.md` | 현재 결론과 읽기 순서; HTML 읽기 버전 포함 |
| `media/` | 120회 Target·continuation, 짧은 실제 참조/Local/후속, 32초 표시 영상, 미리보기 |
| `results/` | 실행·사례 목록과 archive integrity manifest |
| `records/` | 원본 config/metadata, CSV, 평가·감사 JSON |
| `repro/` | 실행 코드·설정·동결 snapshot, 환경 기록, 문서 원본 묶음 |

같은 바이트의 출력은 content hash로 media 파일을 공유하더라도 정식 실행 ID는 유지합니다. 원래 실행 config와 평가 JSON/CSV는 수정하지 않고 복사하여 당시 절대 경로가 남아 있습니다. 이 경로들은 역사 기록이며 이 archive의 활성 링크가 아닙니다. 갤러리와 실행 목록에서 archive의 상대 경로를 별도로 제공합니다.

전체 FineVideo 원본, dataset shard, 모델 가중치, RGB 배열, VAE/text/denoising cache, 실제 noise/좌표 tensor, 대형 중간 결과는 원작업 공간에 보관합니다. 해시와 감사 결과가 실제 tensor 자체를 대체하지는 않으므로 clone만으로 원래 tensor 감사를 모두 재실행할 수는 없습니다. 포함 파일 목록과 SHA256은 [manifest](../results/archive_manifest.json)에 있습니다.

원본 metadata의 `generation_completed: false`, `review_status: unreviewed` 같은 ingest 당시 필드는 수정하지 않았습니다. 최신 완료 판정은 120개의 완료 config와 최종 보고서를 따릅니다.
