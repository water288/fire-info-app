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
    calculate_real_statistics,
    query_real_fire_data,
    get_db_latest_date
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
    latest_date = get_db_latest_date()
    return {
        "years": sorted(years, reverse=True),
        "latest_date": latest_date,
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
    items, total_count, year_scope_total, today_total, sido_total = query_real_fire_data(
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
        sort_order=sort_order,
        page=page,
        page_size=page_size
    )

    total_pages = max(1, (total_count + page_size - 1) // page_size)

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

    s_pct = round((sido_total / max(1, year_scope_total)) * 100, 1) if year_scope_total > 0 else 0.0
    sgg_pct = round((total_count / max(1, sido_total)) * 100, 1) if (sigungu and sigungu != "전체" and sido_total > 0) else None

    return SearchResponse(
        total_count=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        items=items,
        year_scope_total=year_scope_total,
        year_scope_label=year_scope_label,
        today_total=today_total,
        latest_date=get_db_latest_date(),
        national_total_fires=year_scope_total,
        sido_total_fires=sido_total,
        sido_percentage=s_pct if (sido and sido != "전체") else None,
        sigungu_percentage=sgg_pct,
        region_total_fires=sido_total,
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
    stats = calculate_real_statistics(
        sido=sido,
        sigungu=sigungu,
        keyword=keyword,
        start_year=start_year,
        end_year=end_year,
        start_date=start_date,
        end_date=end_date,
        period=period,
        cause_category=cause_category,
        location_category=location_category,
        min_casualties=min_casualties,
        min_damage=min_damage,
        has_deaths=has_deaths
    )

    total_cnt = stats["total_fires"]

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


@app.get("/api/download-excel")
async def download_excel():
    """2007~2026년 소방청 화재발생 데이터 전체 엑셀 다운로드"""
    base_dir = os.path.dirname(os.path.dirname(__file__))
    xlsx_path = os.path.join(base_dir, "korea_fire_data_2007_2026_826683.xlsx")
    if not os.path.exists(xlsx_path):
        xlsx_path = os.path.join(base_dir, "2026-08-31_소방청 화재발생 상세-korea_fire_data_2007_2026_(826683건).xlsx")
    
    if os.path.exists(xlsx_path):
        return FileResponse(
            path=xlsx_path,
            filename="korea_fire_data_2007_2026_826683.xlsx",
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    else:
        # 엑셀 원본이 없을 경우 최신 DB 기준 CSV 스트리밍 다운로드
        return await export_csv(start_year=2007, end_year=2026)


@app.get("/api/test-api-key")
@app.post("/api/test-connection")
async def test_api_key_endpoint(
    api_key: Optional[str] = Query(None, description="공공데이터포털 소방청 일반 인증키"),
    body: Optional[Dict[str, Any]] = None
):
    """사용자가 입력한 공공데이터포털(data.go.kr) 소방청 인증키 진단 (GET/POST 지원)"""
    key = api_key or (body.get("api_key") if body else None)
    if not key:
        raise HTTPException(status_code=400, detail="API 인증키를 입력해주세요.")
    result = await test_odcloud_connection(key)
    return result


@app.post("/api/sync-odcloud")
@app.post("/api/sync-official-api")
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
@app.get("/api/export-csv")
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
