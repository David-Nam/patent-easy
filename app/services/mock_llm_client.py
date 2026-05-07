from datetime import datetime, timezone

from app.schemas.patent import PatentDetail
from app.schemas.search import ExtractedQuery
from app.schemas.summary import SummaryResponse


class MockLLMClient:
    """Deterministic replacement for real LLM providers during the mock phase."""

    def extract_keywords(self, query: str) -> ExtractedQuery:
        normalized = query.replace(" ", "")
        if "음식" in normalized or "칼로리" in normalized or "식단" in normalized:
            return ExtractedQuery(
                keywords=["음식 이미지 인식", "칼로리 자동 계산", "맞춤형 식단 추천"],
                ipc_codes=["G06V", "G06N", "A23L"],
                expanded_terms={
                    "음식 이미지 인식": ["식품 영상 인식", "음식 사진 식별", "식품 객체 검출"],
                    "칼로리 자동 계산": ["열량 산출", "영양성분 분석", "식품 영양 추정"],
                    "맞춤형 식단 추천": ["개인화 식단", "건강 상태 기반 추천", "영양 관리"],
                },
            )

        if "전기차" in normalized or "충전소" in normalized:
            return ExtractedQuery(
                keywords=["전기차 충전소 예측", "충전 인프라 추천", "차량 위치 기반 안내"],
                ipc_codes=["B60L", "G06Q", "G06N"],
                expanded_terms={
                    "전기차 충전소 예측": ["충전 가능 여부 예측", "충전 대기 시간 산출", "충전소 혼잡도 예측"],
                    "충전 인프라 추천": ["충전소 매칭", "최적 충전 위치 추천", "충전 경로 안내"],
                    "차량 위치 기반 안내": ["위치 기반 서비스", "차량 내비게이션 연동", "운전자 안내"],
                },
            )

        if "중고차" in normalized or "수출" in normalized or "보험이력" in normalized:
            return ExtractedQuery(
                keywords=["중고차 상태 분석", "보험 이력 처리", "자동 상담 응답"],
                ipc_codes=["G06Q", "G06V", "G06F"],
                expanded_terms={
                    "중고차 상태 분석": ["차량 이미지 분석", "성능 점검표 처리", "차량 가치 평가"],
                    "보험 이력 처리": ["사고 이력 분석", "차량 이력 데이터", "보험 정보 매칭"],
                    "자동 상담 응답": ["챗봇 응답 생성", "문의 자동 처리", "수출 상담 지원"],
                },
            )

        if "운동" in normalized or "자세" in normalized or "홈트레이닝" in normalized:
            return ExtractedQuery(
                keywords=["운동 자세 인식", "동작 분석", "피드백 제공"],
                ipc_codes=["G06V", "G06N", "A63B"],
                expanded_terms={
                    "운동 자세 인식": ["인체 관절 검출", "포즈 추정", "자세 교정"],
                    "동작 분석": ["운동 동작 평가", "모션 분석", "동작 패턴 인식"],
                    "피드백 제공": ["실시간 코칭", "운동 가이드", "오류 자세 알림"],
                },
            )

        if "노인" in normalized or "넘어지" in normalized or "웨어러블" in normalized:
            return ExtractedQuery(
                keywords=["낙상 감지", "웨어러블 센서", "보호자 알림"],
                ipc_codes=["A61B", "G08B", "H04W"],
                expanded_terms={
                    "낙상 감지": ["이상 움직임 감지", "자세 변화 감지", "응급 상황 판단"],
                    "웨어러블 센서": ["가속도 센서", "생체 신호 측정", "착용형 단말"],
                    "보호자 알림": ["응급 알림 전송", "원격 보호자 통지", "위치 정보 공유"],
                },
            )

        if "앞유리" in normalized or "증강현실" in normalized or "위험정보" in normalized:
            return ExtractedQuery(
                keywords=["차량 증강현실 표시", "전방 표시 장치", "주행 위험 안내"],
                ipc_codes=["G02B", "B60K", "G08G"],
                expanded_terms={
                    "차량 증강현실 표시": ["헤드업 디스플레이", "AR 내비게이션", "주행 정보 중첩 표시"],
                    "전방 표시 장치": ["윈드실드 디스플레이", "운전자 시야 표시", "차량용 표시 시스템"],
                    "주행 위험 안내": ["위험 객체 경고", "차선 안내", "운전자 보조 정보"],
                },
            )

        if "약" in normalized or "복약" in normalized:
            return ExtractedQuery(
                keywords=["복약 일정 관리", "복약 알림", "보호자 공유"],
                ipc_codes=["G16H", "G06Q", "H04W"],
                expanded_terms={
                    "복약 일정 관리": ["투약 스케줄", "약물 복용 관리", "환자 일정 관리"],
                    "복약 알림": ["복용 시간 알림", "미복용 감지", "투약 리마인더"],
                    "보호자 공유": ["가족 알림", "원격 모니터링", "복약 상태 전송"],
                },
            )

        if "재활용" in normalized or "쓰레기" in normalized or "분리배출" in normalized:
            return ExtractedQuery(
                keywords=["폐기물 이미지 인식", "재활용품 분류", "분리배출 안내"],
                ipc_codes=["G06V", "B07C", "G06N"],
                expanded_terms={
                    "폐기물 이미지 인식": ["쓰레기 객체 검출", "폐기물 영상 분류", "재활용 이미지 분석"],
                    "재활용품 분류": ["분류 알고리즘", "소재 판별", "재활용 가능 여부 판단"],
                    "분리배출 안내": ["배출 방법 추천", "지역별 배출 규칙", "사용자 안내"],
                },
            )

        if "배송" in normalized or "배달" in normalized:
            return ExtractedQuery(
                keywords=["배달 플랫폼", "추천 시스템", "사용자 행동 분석"],
                ipc_codes=["G06Q", "G06N"],
                expanded_terms={
                    "배달 플랫폼": ["주문 중개", "물류 매칭"],
                    "추천 시스템": ["개인화 추천", "콘텐츠 랭킹"],
                },
            )

        return ExtractedQuery(
            keywords=["자연어 아이디어", "특허 검색", "비즈니스 적용"],
            ipc_codes=["G06F", "G06Q"],
            expanded_terms={
                "자연어 아이디어": ["사용자 입력", "아이디어 설명"],
                "특허 검색": ["선행기술 조사", "공보 검색"],
            },
        )

    def summarize_patent(self, patent: PatentDetail, user_query: str | None) -> SummaryResponse:
        perspective = "사용자 입력과의 관련성을 중심으로 " if user_query else ""
        return SummaryResponse(
            patent_id=patent.patent_id,
            core_summary=(
                f"{perspective}{patent.title}의 핵심은 {patent.abstract_preview} "
                "Mock 단계에서는 청구항 원문을 기반으로 한 간단 요약만 제공합니다."
            ),
            business_application=(
                "제품 기획자는 이 특허의 입력 데이터, 처리 로직, 추천 또는 분석 결과 제공 방식을 "
                "자사 서비스 기능과 비교해 침해 가능성과 회피 설계 포인트를 검토할 수 있습니다."
            ),
            key_tags=patent.tags,
            generated_at=datetime.now(timezone.utc),
            is_cached=False,
        )


mock_llm_client = MockLLMClient()
