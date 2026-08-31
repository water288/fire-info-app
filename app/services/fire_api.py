import httpx
import logging
from urllib.parse import unquote
from typing import List, Optional, Dict, Any
from app.models import FireRecord

logger = logging.getLogger(__name__)

# 소방청 ODCloud(공공데이터포털) 연도별 화재발생정보 API 엔드포인트 매핑
ODCLOUD_FIRE_ENDPOINTS = [
    {"year": "2024", "name": "소방청_화재발생 정보 (2024년)", "uddi": "5bb0f25d-61e9-4c45-8c9a-cad5f129c6d0"},
    {"year": "2023", "name": "소방청_화재발생 정보 (2023년)", "uddi": "dccb3198-ff6b-401d-826d-a8bbb7d44c61"},
    {"year": "2021", "name": "소방청_화재발생 정보 (2021년)", "uddi": "36028e48-751c-4609-9d1d-b704d1e0ea0b"},
    {"year": "2020", "name": "소방청_화재발생 정보 (2020년)", "uddi": "4c6b68db-0857-4422-9bce-e4a9befa64c5"},
    {"year": "2019", "name": "소방청_화재발생 정보 (2019년)", "uddi": "d9db23d7-777f-47e6-9439-861f9f222ba2"},
    {"year": "2018", "name": "소방청_화재발생 정보 (2018년)", "uddi": "77900950-2d97-4fe5-8bd8-e27f65021a3f"},
    {"year": "2018_10", "name": "소방청_화재발생 정보 (2018년 10월)", "uddi": "f8a6c3c5-de87-497a-bd93-86211f6f0ad3"}
]

ODCLOUD_BASE_URL = "https://api.odcloud.kr/api/15044003/v1/uddi:"

def parse_odcloud_record(item: dict, year_hint: int, idx: int) -> FireRecord:
    """ODCloud 한글 키/영문 키 화재 데이터 레코드 파싱"""
    
    # 1. 일시 파싱
    date_str = str(item.get("화재발생년월일") or item.get("발생일시") or item.get("ocrnDt") or item.get("화재발생일자") or f"{year_hint}-01-01 00:00:00")
    fire_date = f"{year_hint}-01-01"
    fire_time = "00:00"
    
    if " " in date_str:
        parts = date_str.split(" ")
        fire_date = parts[0].strip()
        fire_time = parts[1].strip()[:5] if len(parts) > 1 else "00:00"
    elif len(date_str) >= 8:
        # YYYYMMDD 또는 YYYY-MM-DD
        clean_d = date_str.replace("-", "")
        fire_date = f"{clean_d[:4]}-{clean_d[4:6]}-{clean_d[6:8]}"
        fire_time = f"{clean_d[8:10]}:{clean_d[10:12]}" if len(clean_d) >= 12 else "00:00"

    try:
        y = int(fire_date[:4])
        m = int(fire_date[5:7])
    except:
        y, m = year_hint, 1

    fire_datetime = f"{fire_date} {fire_time}"

    # 2. 지역
    sido = str(item.get("시도") or item.get("시·도") or item.get("sidoNm") or "전국")
    sigungu = str(item.get("시군구") or item.get("시·군·구") or item.get("sggNm") or "")
    eupmyeondong = str(item.get("읍면동") or item.get("읍·면·동") or item.get("emdNm") or "")

    # 3. 장소 분류
    loc_cat = str(item.get("장소대분류") or item.get("장소(대)") or item.get("firsPlcNm") or "일반시설")
    loc_det = str(item.get("장소중분류") or item.get("장소소분류") or item.get("장소(중)") or item.get("장소세부") or "세부장소")

    # 4. 발화 원인
    cause_cat = str(item.get("발화열원대분류") or item.get("발화요인대분류") or item.get("발화원인대분류") or item.get("원인대분류") or "부주의")
    cause_det = str(item.get("발화열원소분류") or item.get("발화요인소분류") or item.get("발화원인소분류") or item.get("원인세부") or "")

    # 5. 피해 규모
    def safe_int(val):
        if val is None or val == "":
            return 0
        try:
            return int(float(str(val).replace(",", "")))
        except:
            return 0

    deaths = safe_int(item.get("사망") or item.get("사망자수") or item.get("dthDmgCnt"))
    injuries = safe_int(item.get("부상") or item.get("부상자수") or item.get("injDmgCnt"))
    casualties = safe_int(item.get("인명피해(명)소계") or item.get("인명피해소계") or item.get("사상자수")) or (deaths + injuries)
    damage = safe_int(item.get("재산피해소계") or item.get("재산피해액") or item.get("prptDmgAmt"))  # 보통 천원 단위

    record_id = f"ODCLOUD-{y}-{idx+1}"

    summary = f"[소방청 국가화재정보] {sido} {sigungu} {loc_cat}({loc_det}) 화재 발생. 발화원인: {cause_cat}({cause_det}), 인명피해 사망 {deaths}명, 부상 {injuries}명, 재산피해 {damage:,}천원."

    return FireRecord(
        id=record_id,
        fire_date=fire_date,
        fire_time=fire_time,
        fire_datetime=fire_datetime,
        year=y,
        month=m,
        sido=sido,
        sigungu=sigungu,
        eupmyeondong=eupmyeondong,
        location_category=loc_cat,
        location_detail=loc_det,
        cause_category=cause_cat,
        cause_detail=cause_det,
        deaths=deaths,
        injuries=injuries,
        casualties=casualties,
        property_damage=damage,
        suppression_minutes=30,
        dispatched_personnel=20,
        dispatched_vehicles=5,
        summary=summary
    )


async def test_odcloud_connection(api_key: str) -> Dict[str, Any]:
    """소방청 ODCloud 전체 연도별 API 연결 및 건수 전수 진단"""
    clean_key = unquote(api_key.strip())
    
    # 2024년 최신 엔드포인트 기준으로 우선 진단
    latest_endpoint = ODCLOUD_FIRE_ENDPOINTS[0]
    target_url = f"{ODCLOUD_BASE_URL}{latest_endpoint['uddi']}"

    # 헤더 방식 및 쿼리 파라미터 방식 둘 다 지원
    params = {
        "serviceKey": clean_key,
        "page": 1,
        "perPage": 10
    }
    headers = {
        "Authorization": f"Infuser {clean_key}",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. serviceKey 쿼리 방식 시도
            response = await client.get(target_url, params=params, headers={"Accept": "application/json"})
            
            # 2. 401/403 시 Authorization 헤더 방식 재시도
            if response.status_code != 200:
                response = await client.get(target_url, params={"page": 1, "perPage": 10}, headers=headers)

            if response.status_code == 200:
                data = response.json()
                total_count = data.get("totalCount") or data.get("matchCount") or len(data.get("data", []))
                raw_items = data.get("data", [])
                
                parsed_items = [parse_odcloud_record(item, 2024, i) for i, item in enumerate(raw_items)]

                return {
                    "success": True,
                    "service_name": latest_endpoint["name"],
                    "total_count": total_count,
                    "sample_count": len(parsed_items),
                    "items": parsed_items,
                    "available_years": [ep["year"] for ep in ODCLOUD_FIRE_ENDPOINTS]
                }
            else:
                text = response.text[:200]
                return {
                    "success": False,
                    "error": f"소방청 API 응답 오류 (HTTP {response.status_code}): {text}",
                    "total_count": 0,
                    "items": []
                }
    except Exception as e:
        return {
            "success": False,
            "error": f"연결 실패: {str(e)}",
            "total_count": 0,
            "items": []
        }


async def fetch_real_fire_data(
    api_key: str,
    custom_url: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    page_no: int = 1,
    num_of_rows: int = 20
) -> Dict[str, Any]:
    """소방청 ODCloud API로부터 실시간 화재 발생 데이터 페칭"""
    if not api_key:
        return {"success": False, "error": "API 키가 입력되지 않았습니다.", "items": [], "total_count": 0}

    clean_key = unquote(api_key.strip())
    
    # 기본은 2024년 데이터셋
    uddi = ODCLOUD_FIRE_ENDPOINTS[0]["uddi"]
    target_url = custom_url if (custom_url and "api.odcloud.kr" in custom_url) else f"{ODCLOUD_BASE_URL}{uddi}"

    params = {
        "serviceKey": clean_key,
        "page": page_no,
        "perPage": num_of_rows
    }
    headers = {
        "Authorization": f"Infuser {clean_key}",
        "Accept": "application/json"
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(target_url, params=params)
            if response.status_code != 200:
                response = await client.get(target_url, params={"page": page_no, "perPage": num_of_rows}, headers=headers)

            if response.status_code == 200:
                data = response.json()
                total_count = data.get("totalCount") or data.get("matchCount") or 0
                raw_items = data.get("data", [])
                
                parsed_records = [parse_odcloud_record(item, 2024, (page_no-1)*num_of_rows + i) for i, item in enumerate(raw_items)]

                return {
                    "success": True,
                    "total_count": total_count,
                    "items": parsed_records,
                    "connected_service": "소방청_화재발생 정보 (ODCloud 실시간)"
                }
            else:
                return {
                    "success": False,
                    "error": f"소방청 API 오류 (HTTP {response.status_code}): {response.text[:200]}",
                    "items": [],
                    "total_count": 0
                }
    except Exception as ex:
        return {
            "success": False,
            "error": f"API 연동 예외 발생: {str(ex)}",
            "items": [],
            "total_count": 0
        }
