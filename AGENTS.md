# Feasibility archive 작업 지침

한국어 또는 영어를 사용한다. 기본 설명은 한국어다.

이 저장소는 Addressable Global Memory for Long-Context Video Generation 연구의 **Stage 1 완료 기록**이다. 먼저 README.md와 docs/STAGE2_HANDOFF.md를 읽는다. 정식 120회는 9개 실험 묶음의 완료 실행 수이며 재사용 비교를 중복 집계하지 않는다.

원실험 `records/`, `repro/longcond/feasibility_long_context/configs/`, 실행 snapshot은 역사 기록이다. 문서 정리 중 실험 설정이나 원본 측정값을 소급 수정하지 않는다. 새 실험·학습은 사용자의 별도 작업 요청을 따른다. 현재 Stage 2는 초기 설계만 있다.

메모리는 직접 전역 생성 조건과 원본 증거 선택 두 역할을 갖는다. 검색이나 외관 유지로 목표를 축소하지 않는다. 배경·물체·사람 정보를 사전 제거하지 않는다. 상태·사건·복수 증거 검증은 미완료다.

생성 성공·실패, 설계 제안, 실제 측정을 구분한다. 약 4.7배는 denoising 이점이며 전체 pipeline이나 학습 속도 향상으로 바꾸어 쓰지 않는다. 외관 노출 개선을 과제 완전 성공으로 집계하지 않는다.

갤러리 수정 후 `python3 scripts/verify_archive.py`로 링크·목록·해시를 확인한다. 파일 변경 후에는 `scripts/refresh_manifest.py`를 실행해 archive의 체크섬을 갱신한 다음 검증한다. 원본 실험 해시는 변경하지 않는다.
