from pydantic import BaseModel, Field
from typing import Optional, List

class FireRecord(BaseModel):
    id: str
    fire_date: str = Field(description="발생일자 (YYYY-MM-DD)")
    fire_time: str = Field(description="발생시각 (HH:MM)")
    fire_datetime: str = Field(description="발생일시 (YYYY-MM-DD HH:MM)")
    year: int = Field(description="발생연도")
    month: int = Field(description="발생월")
    sido: str = Field(description="시/도")
    sigungu: str = Field(description="시/군/구")
    eupmyeondong: str = Field(default="", description="읍/면/동")
    location_category: str = Field(description="장소 대분류")
    location_detail: str = Field(description="장소 세부")
    cause_category: str = Field(description="발화 원인 대분류")
    cause_detail: str = Field(description="발화 원인 세부")
    deaths: int = Field(default=0, description="사망자 수")
    injuries: int = Field(default=0, description="부상자 수")
    casualties: int = Field(default=0, description="총 인명피해 수 (사망+부상)")
    property_damage: int = Field(default=0, description="재산피해액 (천원)")
    suppression_minutes: int = Field(default=0, description="진압 소요 시간 (분)")
    dispatched_personnel: int = Field(default=0, description="동원 인력 수")
    dispatched_vehicles: int = Field(default=0, description="동원 차량 수")
    summary: Optional[str] = Field(default="", description="화재 개요 및 조치")
    is_realtime: Optional[bool] = Field(default=False, description="2026년 실시간 수신 사건 여부")

class SearchQuery(BaseModel):
    keyword: Optional[str] = None
    start_year: Optional[int] = 2017
    end_year: Optional[int] = 2026
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    sido: Optional[str] = None
    sigungu: Optional[str] = None
    cause_category: Optional[str] = None
    location_category: Optional[str] = None
    min_casualties: Optional[int] = None
    min_damage: Optional[int] = None
    has_deaths: Optional[bool] = None
    sort_by: Optional[str] = "fire_datetime"  # fire_datetime, deaths, injuries, casualties, property_damage, suppression_minutes
    sort_order: Optional[str] = "desc"  # asc, desc
    page: int = 1
    page_size: int = 20

class SearchResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    total_pages: int
    items: List[FireRecord]
    national_total_fires: Optional[int] = None
    sido_total_fires: Optional[int] = None
    sido_percentage: Optional[float] = None
    sigungu_percentage: Optional[float] = None
    region_total_fires: Optional[int] = None
    cause_percentage: Optional[float] = None
    cause_category: Optional[str] = None
    location_percentage: Optional[float] = None
    location_category: Optional[str] = None
    combined_percentage: Optional[float] = None

class StatsSummary(BaseModel):
    total_fires: int
    total_deaths: int
    total_injuries: int
    total_casualties: int
    total_property_damage_cheonwon: int
    national_total_fires: Optional[int] = None
    sido_total_fires: Optional[int] = None
    sido_percentage: Optional[float] = None
    sigungu_percentage: Optional[float] = None
    region_total_fires: Optional[int] = None
    cause_percentage: Optional[float] = None
    cause_category: Optional[str] = None
    location_percentage: Optional[float] = None
    location_category: Optional[str] = None
    combined_percentage: Optional[float] = None
    yearly_trend: List[dict]
    cause_breakdown: List[dict]
    sido_ranking: List[dict]
    location_breakdown: List[dict]
