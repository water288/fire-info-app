from fastapi import FastAPI, Query, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, List, Dict, Any
import io
import os
import csv
from datetime import datetime, timedelta

from app.models import FireRecord, SearchResponse, StatsSummary
from app.services.fire_service import (
    REGIONS,
    FIRE_CAUSES,
    LOCATIONS,
    SPECIFIC_EUPMYEONDONG,
    get_eupmyeondong_for_region,
    get_kst_now,
    get_all_real_records,
    set_real_fire_records,
    add_real_fire_records,
    filter_and_sort_real_records,
    calculate_real_statistics
)
from app.services.fire_api import (
    test_odcloud_connection,
    sync_all_odcloud_data,
    get_synced_fire_records,
    is_synced_with_official_api,
    ODCLOUD_FIRE_ENDPOINTS
)

app = FastAPI(
    title="소방청 화재발생 데이터 통합 검색 & 분석 포털",
    description="소방청 공공데이터포털 공식 API 연동 순수 실제 화재 정보 검색 및 분석 포털",
    version="2.0.0"
)

# CORS 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/meta")
def get_metadata():
    """대한민국 17개 시·도 및 250개 시·군·구, 발화원인, 발생장소 표준 메타데이터 반환"""
    years = list(range(2007, 2027))
    return {
        "years": sorted(years, reverse=True),
        "regions": REGIONS,
        "causes": list(FIRE_CAUSES.keys()),
        "causes_detail": FIRE_CAUSES,
        "locations": list(LOCATIONS.keys()),
        "locations_detail": LOCATIONS,
        "sort_options": [
            {"value": "fire_datetime", "label": "발생일시순"},
            {"value": "casualties", "label": "총 사상자순 (인명피해)"},
            {"value": "deaths", "label": "사망자 많은순"},
            {"value": "injuries", "label": "부상자 많은순"},
            {"value": "property_damage", "label": "재산피해액순"}
        ]
    }


@app.get("/api/fire-data", response_model=SearchResponse)
async def search_fire_data(
    keyword: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    sido: Optional[str] = None,
    sigungu: Optional[str] = None,
    cause_category: Optional[str] = None,
    location_category: Optional[str] = None,
    min_casualties: Optional[int] = None,
    min_damage: Optional[int] = None,
    has_deaths: Optional[bool] = None,
    sort_by: str = "fire_datetime",
    sort_order: str = "desc",
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200)
):
    """소방청 공식 실제 화재 데이터 검색 (가짜 생성 일절 없음)"""
    
    # 1. 실제 데이터 저장소에서 필터링 및 정렬 수행
    filtered = filter_and_sort_real_records(
        keyword=keyword,
        start_year=start_year,
        end_year=end_year,
        start_date=start_date,
        end_date=end_date,
        period=period,
        sido=sido,
        sigungu=sigungu,
        cause_category=cause_category,
        location_category=location_category,
        min_casualties=min_casualties,
        min_damage=min_damage,
        has_deaths=has_deaths,
        sort_by=sort_by,
        sort_order=sort_order
    )

    total_count = len(filtered)
    total_pages = max(1, (total_count + page_size - 1) // page_size)
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_items = filtered[start_idx:end_idx]

    # 전체 소스 데이터 기준 통계 산출
    all_real_records = get_all_real_records()
    real_stat = calculate_real_statistics(all_real_records, sido=sido, sigungu=sigungu)

    # 연도 범위 라벨
    if start_year == 2026 and end_year == 2026:
        year_scope_label = "2026년 실시간"
    elif start_year == 2007 and end_year == 2026:
        year_scope_label = "전체 20년 (2007~2026)"
    elif start_year and end_year and start_year == end_year:
        year_scope_label = f"{start_year}년"
    elif start_year and end_year:
        year_scope_label = f"{start_year}~{end_year}년"
    else:
        year_scope_label = "전체 기간"

    # 오늘 당일 실제 건수
    now_dt = get_kst_now().replace(tzinfo=None)
    today_str = now_dt.strftime("%Y-%m-%d")
    today_total = sum(1 for r in all_real_records if r.fire_date == today_str)

    # 점유율 계산 (실제 데이터 기준)
    nat_total = len(all_real_records)
    if sido and sido != "전체":
        s_total = sum(1 for r in all_real_records if (sido in r.sido or r.sido in sido))
    else:
        s_total = nat_total
    
    s_pct = round((s_total / max(1, nat_total)) * 100, 1) if nat_total > 0 else 0.0
    sgg_pct = round((total_count / max(1, s_total)) * 100, 1) if (sigungu and sigungu != "전체" and s_total > 0) else None

    return SearchResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=page_items,
        year_scope_total=nat_total,
        year_scope_label=year_scope_label,
        today_total=today_total,
        national_total_fires=nat_total,
        sido_total_fires=s_total,
        sido_percentage=s_pct if (sido and sido != "전체") else None,
        sigungu_percentage=sgg_pct,
        region_total_fires=s_total,
        cause_percentage=None,
        cause_category=cause_category,
        location_percentage=None,
        location_category=location_category,
        combined_percentage=None
    )


@app.get("/api/stats", response_model=StatsSummary)
def get_fire_stats(
    keyword: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    sido: Optional[str] = None,
    sigungu: Optional[str] = None,
    cause_category: Optional[str] = None,
    location_category: Optional[str] = None,
    min_casualties: Optional[int] = None,
    min_damage: Optional[int] = None,
    has_deaths: Optional[bool] = None
):
    """현재 필터링 조건에 따른 소방청 실제 통계 요약 및 차트 데이터 산출"""
    
    # 1. 실제 조건에 맞는 레코드 필터링
    filtered = filter_and_sort_real_records(
        keyword=keyword,
        start_year=start_year,
        end_year=end_year,
        start_date=start_date,
        end_date=end_date,
        period=period,
        sido=sido,
        sigungu=sigungu,
        cause_category=cause_category,
        location_category=location_category,
        min_casualties=min_casualties,
        min_damage=min_damage,
        has_deaths=has_deaths
    )

    stats = calculate_real_statistics(filtered, sido=sido, sigungu=sigungu)
    total_cnt = stats["total_fires"]

    # 세부 비중 계산
    cause_breakdown = [
        {"cause": item["cause"], "count": item["count"], "percentage": round((item["count"] / max(1, total_cnt)) * 100, 1)}
        for item in stats["cause_stats"]
    ]

    location_breakdown = [
        {"location": item["location"], "count": item["count"], "percentage": round((item["count"] / max(1, total_cnt)) * 100, 1)}
        for item in stats["location_stats"]
    ]

    sido_ranking = [
        {"sido": item["sido"], "count": item["count"], "percentage": round((item["count"] / max(1, total_cnt)) * 100, 1)}
        for item in stats["sido_stats"]
    ]

    return StatsSummary(
        total_fires=stats["total_fires"],
        total_deaths=stats["total_deaths"],
        total_injuries=stats["total_injuries"],
        total_casualties=stats["total_casualties"],
        total_property_damage_cheonwon=stats["total_property_damage_cheonwon"],
        national_total_fires=stats["national_total_fires"],
        sido_total_fires=stats["sido_total_fires"],
        sido_percentage=stats["sido_percentage"],
        sigungu_percentage=stats["sigungu_percentage"],
        region_total_fires=stats["sido_total_fires"],
        cause_percentage=None,
        cause_category=cause_category,
        location_percentage=None,
        location_category=location_category,
        combined_percentage=None,
        yearly_trend=stats["yearly_stats"],
        cause_breakdown=cause_breakdown,
        location_breakdown=location_breakdown,
        sido_ranking=sido_ranking
    )


@app.get("/api/test-api-key")
async def test_api_key_endpoint(api_key: str = Query(..., description="공공데이터포털 소방청 일반 인증키")):
    """사용자가 입력한 공공데이터포털(data.go.kr) 소방청 인증키 진단"""
    if not api_key:
        raise HTTPException(status_code=400, detail="API 인증키를 입력해주세요.")
    result = await test_odcloud_connection(api_key)
    return result


@app.post("/api/sync-odcloud")
async def sync_odcloud_endpoint(
    api_key: str = Query(..., description="공공데이터포털 소방청 인증키"),
    per_page: int = Query(500, ge=10, le=1000)
):
    """소방청 공공데이터포털(ODCloud)로부터 순수 실제 화재 데이터를 일괄 동기화"""
    if not api_key:
        raise HTTPException(status_code=400, detail="API 인증키가 필요합니다.")
    result = await sync_all_odcloud_data(api_key=api_key, max_records_per_endpoint=per_page)
    return result


@app.get("/api/export/csv")
async def export_csv(
    keyword: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    sido: Optional[str] = None,
    sigungu: Optional[str] = None,
    cause_category: Optional[str] = None,
    location_category: Optional[str] = None,
    min_casualties: Optional[int] = None,
    min_damage: Optional[int] = None,
    has_deaths: Optional[bool] = None,
    sort_by: str = "fire_datetime",
    sort_order: str = "desc"
):
    """실제 화재 데이터 검색 결과 CSV 내보내기"""
    records = filter_and_sort_real_records(
        keyword=keyword,
        start_year=start_year,
        end_year=end_year,
        start_date=start_date,
        end_date=end_date,
        period=period,
        sido=sido,
        sigungu=sigungu,
        cause_category=cause_category,
        location_category=location_category,
        min_casualties=min_casualties,
        min_damage=min_damage,
        has_deaths=has_deaths,
        sort_by=sort_by,
        sort_order=sort_order
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "사건번호", "발생일시", "시도", "시군구", "읍면동",
        "장소분류(대)", "장소상세(소)", "발화원인(대)", "발화원인(소)",
        "사망자(명)", "부상자(명)", "사상자(명)", "재산피해(천원)",
        "진압소요시간(분)", "출동차량수", "동원인원수", "사건개요"
    ])

    for r in records:
        writer.writerow([
            r.id, r.fire_datetime, r.sido, r.sigungu, r.eupmyeondong,
            r.location_category, r.location_detail, r.cause_category, r.cause_detail,
            r.deaths, r.injuries, r.casualties, r.property_damage,
            r.suppression_minutes, r.dispatched_vehicles, r.dispatched_personnel, r.summary
        ])

    csv_data = "\ufeff" + output.getvalue()
    return Response(
        content=csv_data.encode("utf-8-sig"),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=fire_data_real.csv"}
    )


# 정적 파일 서빙
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
