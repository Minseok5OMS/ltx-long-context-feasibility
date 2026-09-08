# GitHub에서 입력·생성 결과 보기

[전체 요약](../README.md)

별도 서버나 GitHub Pages 설정 없이 이 Markdown 페이지에서 결과를 탐색합니다. 움직이는 미리보기는 **256×144, 8 FPS의 GIF**이며 원래 3초 길이를 유지합니다. 클릭하면 저장소의 원본 MP4 파일로 이동합니다. GIF에는 재생·정지 버튼이 없으며 미세한 외관·동작 평가는 512×288, 24 FPS MP4를 사용합니다.

정식 생성은 **120회**, 비교 표시는 **151개**입니다. 재사용 31개를 신규 생성에 더하지 않습니다. 각 사례에서 Local·참조·원본 후속과 실제 prompt/좌표를 확인할 수 있습니다.

| 실험 | 신규 생성 | 비교 표시 |
|---|---:|---:|
| [1. Local smoke](experiment_1/README.md) | 1 | 1 |
| [2. 초기 Local / Random / Oracle](experiment_2/README.md) | 9 | 9 |
| [3. 형식 × 시간 위치 · 3 seeds](experiment_3/README.md) | 10 | 12 |
| [4. 이미지 반복 / 시간 배치 분리](experiment_4/README.md) | 3 | 5 |
| [5. 동일 이미지 반복수](experiment_5/README.md) | 2 | 4 |
| [6. 5개 원본 Local / Image-Past](experiment_6/README.md) | 10 | 10 |
| [7. 5개 사례 전체 2×2](experiment_7/README.md) | 15 | 25 |
| [8. Prompt P0 / P1 / P2 / P3](experiment_8/README.md) | 45 | 60 |
| [9. 32초 전체 / 선택 chunk](experiment_9/README.md) | 25 | 25 |

[마지막 32초 비교의 5사례부터 보기](experiment_9/README.md)

## MP4를 README 안의 재생 플레이어로 넣고 싶다면

GitHub의 첨부 업로드가 반환한 영상 URL을 Markdown 본문에 넣는 경로가 있습니다. 저장소에 commit한 상대 MP4 링크를 첨부 URL과 동일하게 취급하지 않습니다. 이 저장소는 첨부 서비스 없이 Git에 보관되는 GIF 미리보기와 원본 MP4 링크를 기본으로 제공합니다. [GitHub 첨부 안내](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/attaching-files)
