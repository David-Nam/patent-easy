from datetime import datetime, timezone

from app.schemas.patent import PatentDetail
from app.schemas.search import ExtractedQuery
from app.schemas.summary import SummaryResponse


class MockLLMClient:
    """Deterministic replacement for OpenAI during the mock-first phase."""

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
