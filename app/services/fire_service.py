import os
import sqlite3
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any, Tuple
from app.models import FireRecord, StatsSummary

# 한국 표준시 (KST, UTC+9)
KST = timezone(timedelta(hours=9))

def get_kst_now() -> datetime:
    """정확한 한국 표준시(KST) 반환"""
    return datetime.now(timezone.utc).astimezone(KST)

# 대한민국 17개 시·도 및 250개 시·군·구 표준 행정구역 목록
REGIONS = {
    "서울특별시": ["강남구", "강동구", "강북구", "강서구", "관악구", "광진구", "구로구", "금천구", "노원구", "도봉구", "동대문구", "동작구", "마포구", "서대문구", "서초구", "성동구", "성북구", "송파구", "양천구", "영등포구", "용산구", "은평구", "종로구", "중구", "중랑구"],
    "경기도": ["수원시", "성남시", "고양시", "용인시", "부천시", "안산시", "안양시", "남양주시", "화성시", "평택시", "의정부시", "파주시", "시흥시", "김포시", "광명시", "광주시", "군포시", "이천시", "오산시", "하남시", "양주시", "구리시", "안성시", "포천시", "의왕시", "여주시", "양평군", "동두천시", "과천시", "가평군", "연천군"],
    "부산광역시": ["해운대구", "부산진구", "동래구", "남구", "북구", "사하구", "금정구", "연제구", "수영구", "사상구", "기장군", "중구", "서구", "동구", "영도구", "강서구"],
    "대구광역시": ["수성구", "달서구", "북구", "동구", "서구", "남구", "중구", "달성군", "군위군"],
    "인천광역시": ["남동구", "부평구", "서구", "미추홀구", "연수구", "계양구", "중구", "동구", "강화군", "옹진군"],
    "광주광역시": ["북구", "광산구", "서구", "남구", "동구"],
    "대전광역시": ["서구", "유성구", "중구", "동구", "대덕구"],
    "울산광역시": ["남구", "중구", "북구", "동구", "울주군"],
    "세종특별자치시": ["세종시"],
    "강원특별자치도": ["춘천시", "원주시", "강릉시", "동해시", "태백시", "속초시", "삼척시", "홍천군", "횡성군", "영월군", "평창군", "정선군", "철원군", "화천군", "양구군", "인제군", "고성군", "양양군"],
    "충청북도": ["청주시", "충주시", "제천시", "보은군", "옥천군", "영동군", "증평군", "진천군", "괴산군", "음성군", "단양군"],
    "충청남도": ["천안시", "공주시", "보령시", "아산시", "서산시", "논산시", "계룡시", "당진시", "금산군", "부여군", "서천군", "청양군", "홍성군", "예산군", "태안군"],
    "전북특별자치도": ["전주시", "익산시", "군산시", "정읍시", "남원시", "김제시", "완주군", "진안군", "무주군", "장수군", "임실군", "순창군", "고창군", "부안군"],
    "전라남도": ["목포시", "여수시", "순천시", "나주시", "광양시", "담양군", "곡성군", "구례군", "고흥군", "보성군", "화순군", "장흥군", "강진군", "해남군", "영암군", "무안군", "함평군", "영광군", "장성군", "완도군", "진도군", "신안군"],
    "경상북도": ["포항시", "경주시", "김천시", "안동시", "구미시", "영주시", "영천시", "상주시", "문경시", "경산시", "의성군", "청송군", "영양군", "영덕군", "청도군", "고령군", "성주군", "칠곡군", "예천군", "봉화군", "울진군", "울릉군"],
    "경상남도": ["창원시", "진주시", "통영시", "사천시", "김해시", "밀양시", "거제시", "양산시", "의령군", "함안군", "창녕군", "고성군", "남해군", "하동군", "산청군", "함양군", "거창군", "합천군"],
    "제주특별자치도": ["제주시", "서귀포시"]
}

# 발화 원인 표준 분류
FIRE_CAUSES = {
    "부주의": ["담배꽁초 방치", "음식물 조리 중 방치", "쓰레기/논밭두렁 소각", "용접/절단 작업 불티", "촛불/향초 취급 부주의", "화원 방치", "불장난"],
    "전기적 요인": ["절연열화에 의한 단락", "과부하/과전류", "접촉불량에 의한 단락", "트래킹에 의한 단락", "누전/지락", "압착/손상에 의한 단락"],
    "기계적 요인": ["과열/과부하", "기계 마찰열", "연통/덕트 과열", "오일 누유 및 발화", "노후 및 정비 불량"],
    "화학적 요인": ["자연발화", "화학반응열", "인화성 액체 유증기 폭발", "가연물 혼합 발열"],
    "방화/방화의심": ["원한/비관 등에 의한 방화", "정신이상 방화", "방화 의심"],
    "가스누출": ["LPG 누출 폭발", "LNG 누출 폭발", "배관 부식 누출"],
    "교통사고": ["차량 충돌 후 발화", "엔진룸 이상 과열 발화"],
    "자연적 요인": ["낙뢰(번개)", "태양광 집열", "가뭄/건조 산불"],
    "기타/미상": ["원인 미상", "조사 중"]
}

# 장소 표준 분류
LOCATIONS = {
    "주거시설": ["아파트", "단독주택", "다세대/연립주택", "오피스텔(주거용)", "원룸/고시원"],
    "산업시설": ["일반공장", "물류창고", "자재보관소", "작업장/가내수공업", "발전시설"],
    "상업/업무시설": ["일반음식점", "복합쇼핑몰/백화점", "숙박시설(호텔/모텔)", "단란/유흥주점", "사무실/빌딩"],
    "자동차/운송수단": ["승용차", "화물차/트럭", "승합차/버스", "건설기계/중장비", "선박/어선"],
    "야외/임야": ["산림/임야", "들판/공터", "야외 쓰레기장", "도로변/하천변"],
    "교육/의료/복지": ["초/중/고등학교", "종합병원/의원", "요양병원/요양원", "어린이집/유치원"],
    "위험물/저장시설": ["주유소/충전소", "가스저장소", "화학물질 저장소"]
}

SPECIFIC_EUPMYEONDONG = {
    "금천구": ["가산동", "독산동", "시흥동"],
    "강남구": ["역삼동", "개포동", "청담동", "삼성동", "대치동", "신사동", "논현동", "압구정동"],
    "청주시": ["오창읍", "오송읍", "내수읍", "옥산면", "가경동", "복대동", "봉명동", "율량동", "용암동", "금천동", "산남동", "분평동", "수곡동"]
}

def get_eupmyeondong_for_region(sido: str, sigungu: str, seed_index: int = 0) -> str:
    if sigungu in SPECIFIC_EUPMYEONDONG:
        dongs = SPECIFIC_EUPMYEONDONG[sigungu]
        return dongs[seed_index % len(dongs)]
    return "중앙동"

# ==========================================
# 순수 실제 데이터 저장소 (SQLite & Memory)
# ==========================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
DB_PATH = os.path.join(BASE_DIR, "fire_records.db")
GZ_PATH = os.path.join(BASE_DIR, "fire_records.db.gz")

if not os.path.exists(DB_PATH) and not os.path.exists(GZ_PATH):
    DB_PATH = "fire_records.db"
    GZ_PATH = "fire_records.db.gz"

def ensure_sqlite_db():
    """서버 시작 및 호출 시 압축된 db.gz가 최신이거나 db가 없으면 자동으로 복원"""
    if os.path.exists(GZ_PATH):
        need_decompress = False
        if not os.path.exists(DB_PATH):
            need_decompress = True
        elif os.path.getsize(DB_PATH) < 1000000:
            need_decompress = True
        elif os.path.getmtime(GZ_PATH) > os.path.getmtime(DB_PATH):
            need_decompress = True

        if need_decompress:
            import gzip
            import shutil
            print(f"Decompressing {GZ_PATH} to {DB_PATH}...")
            with gzip.open(GZ_PATH, 'rb') as f_in:
                with open(DB_PATH, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print("SQLite database restored successfully.")

_REAL_FIRE_STORE: List[FireRecord] = []

def get_db_connection():
    """SQLite 데이터베이스 연결"""
    ensure_sqlite_db()
    if os.path.exists(DB_PATH):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn
    return None

REGION_COORDINATES = {
    "서울특별시": (37.5665, 126.9780),
    "경기도": (37.4138, 127.5183),
    "인천광역시": (37.4563, 126.7052),
    "강원특별자치도": (37.8228, 128.1555),
    "강원도": (37.8228, 128.1555),
    "충청북도": (36.6357, 127.4917),
    "충청남도": (36.5184, 126.8000),
    "대전광역시": (36.3504, 127.3845),
    "세종특별자치시": (36.4800, 127.2890),
    "전북특별자치도": (35.7175, 127.1530),
    "전라북도": (35.7175, 127.1530),
    "전라남도": (34.8679, 126.9910),
    "광주광역시": (35.1595, 126.8526),
    "경상북도": (36.5760, 128.5056),
    "경상남도": (35.4606, 128.2132),
    "대구광역시": (35.8714, 128.6014),
    "울산광역시": (35.5384, 129.3114),
    "부산광역시": (35.1796, 129.0756),
    "제주특별자치도": (33.4996, 126.5312)
}

def generate_dedup_key(record: Any) -> str:
    """화재 사건 중복 식별용 복합 고유 키 생성 (발생일자_시도_발생시각_발화원인_장소)"""
    if isinstance(record, dict):
        d = record.get("fire_date") or record.get("occurDate", "")[:10]
        s = record.get("sido") or record.get("region", "")
        t = (record.get("fire_time") or record.get("occurTime", ""))[:5]
        c = record.get("cause_category") or record.get("fireCause", "")
        l = record.get("location_category") or record.get("placeCategory", "")
    else:
        d = getattr(record, "fire_date", "")
        s = getattr(record, "sido", "")
        t = getattr(record, "fire_time", "")[:5]
        c = getattr(record, "cause_category", "")
        l = getattr(record, "location_category", "")
    return f"{d}_{s}_{t}_{c}_{l}"

def set_real_fire_records(records: List[FireRecord]):
    global _REAL_FIRE_STORE
    records.sort(key=lambda x: x.fire_datetime, reverse=True)
    _REAL_FIRE_STORE = records

def add_real_fire_records(records: List[FireRecord]):
    """중복 방지(Deduplication)가 적용된 실제 레코드 추가"""
    global _REAL_FIRE_STORE
    existing_ids = {r.id for r in _REAL_FIRE_STORE}
    existing_dedup_keys = {r.dedup_key or generate_dedup_key(r) for r in _REAL_FIRE_STORE}
    
    new_items = []
    for r in records:
        dkey = r.dedup_key or generate_dedup_key(r)
        if r.id not in existing_ids and dkey not in existing_dedup_keys:
            r.dedup_key = dkey
            new_items.append(r)
            existing_ids.add(r.id)
            existing_dedup_keys.add(dkey)
            
    _REAL_FIRE_STORE.extend(new_items)
    _REAL_FIRE_STORE.sort(key=lambda x: x.fire_datetime, reverse=True)

def get_all_real_records() -> List[FireRecord]:
    global _REAL_FIRE_STORE
    return _REAL_FIRE_STORE

def has_sqlite_db() -> bool:
    return os.path.exists(DB_PATH) and os.path.getsize(DB_PATH) > 10000

from app.services.geo_coordinates import get_precise_coordinates, SIGUNGU_COORDINATES, SIDO_COORDINATES

def row_to_fire_record(row: Any) -> FireRecord:
    keys = row.keys() if hasattr(row, 'keys') else []
    
    sido_val = str(row["sido"] or "")
    sigungu_val = str(row["sigungu"] or "")
    eupmyeondong_val = str(row["eupmyeondong"] or "") if "eupmyeondong" in keys and row["eupmyeondong"] is not None else ""
    loc_det_val = str(row["location_detail"] or "") if "location_detail" in keys and row["location_detail"] is not None else ""
    
    lat_val = float(row["lat"]) if "lat" in keys and row["lat"] is not None else None
    lng_val = float(row["lng"]) if "lng" in keys and row["lng"] is not None else None
    
    # 만약 좌표가 없거나 충북도청/시도청 중심 등으로 잘못 편중된 경우 정밀 좌표로 재계산
    if lat_val is None or lng_val is None or (lat_val == 0 and lng_val == 0):
        lat_val, lng_val = get_precise_coordinates(sido_val, sigungu_val, eupmyeondong_val, loc_det_val)
    elif sigungu_val and sigungu_val != sido_val:
        # 단양군 등 시군구가 명확한데 충북도청(청주) 등의 중심좌표로 잘못 들어가 있는 경우 보정
        if sigungu_val == "단양군" and (lat_val < 36.8 or lng_val < 128.0):
            lat_val, lng_val = get_precise_coordinates(sido_val, sigungu_val, eupmyeondong_val, loc_det_val)


    return FireRecord(
        id=str(row["id"]),
        fire_datetime=str(row["fire_datetime"]),
        fire_date=str(row["fire_date"]),
        fire_time=str(row["fire_time"]),
        year=int(row["year"]),
        month=int(row["month"]),
        sido=sido_val,
        sigungu=str(row["sigungu"]),
        eupmyeondong=str(row["eupmyeondong"]) if row["eupmyeondong"] is not None else "",
        location_category=str(row["location_category"]),
        location_detail=str(row["location_detail"]),
        cause_category=str(row["cause_category"]),
        cause_detail=str(row["cause_detail"]),
        deaths=int(row["deaths"] or 0),
        injuries=int(row["injuries"] or 0),
        casualties=int(row["casualties"] or 0),
        property_damage=int(row["property_damage"] or 0),
        suppression_minutes=int(row["suppression_minutes"] or 0),
        dispatched_personnel=int(row["dispatched_personnel"] or 0),
        dispatched_vehicles=int(row["dispatched_vehicles"] or 0),
        summary=str(row["summary"] or ""),
        is_realtime=bool(row["is_realtime"]),
        lat=lat_val,
        lng=lng_val,
        source=str(row["source"]) if "source" in keys and row["source"] is not None else "소방청 공식 데이터",
        juris_station=str(row["juris_station"]) if "juris_station" in keys and row["juris_station"] is not None else None,
        status=str(row["status"]) if "status" in keys and row["status"] is not None else "EXTINGUISHED",
        status_text=str(row["status_text"]) if "status_text" in keys and row["status_text"] is not None else "완진",
        is_verified=bool(row["is_verified"]) if "is_verified" in keys and row["is_verified"] is not None else False,
        dedup_key=str(row["dedup_key"]) if "dedup_key" in keys and row["dedup_key"] is not None else None
    )

def get_db_latest_date() -> str:
    """데이터베이스 내 최신 화재 발생 일자 반환"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("SELECT MAX(fire_date) FROM fire_records")
            row = cur.fetchone()
            conn.close()
            if row and row[0]:
                return row[0]
        except Exception:
            if conn:
                conn.close()
    return get_kst_now().strftime("%Y-%m-%d")

def get_breaking_news_items(limit: int = 30) -> List[Dict[str, Any]]:
    """실시간 속보 배너용 최신 공식 화재 기록 목록 반환 (발생일시 최신순)"""
    conn = get_db_connection()
    items = []
    if conn:
        try:
            cur = conn.cursor()
            # 최신 발생일시(fire_date DESC, fire_time DESC) 기준으로 순수 최신 실제 화재 사건들을 추출
            cur.execute("""
                SELECT * FROM fire_records 
                ORDER BY fire_date DESC, fire_time DESC, fire_datetime DESC 
                LIMIT ?
            """, [limit])
            rows = cur.fetchall()
            for r in rows:
                rec = row_to_fire_record(r)
                is_ver = bool(rec.is_verified)
                status_txt = rec.status_text or "완진"
                location_str = f"{rec.sido} {rec.sigungu} {rec.location_detail or rec.location_category}".strip()
                cause_str = rec.cause_detail or rec.cause_category
                
                items.append({
                    "id": rec.id,
                    "datetime": rec.fire_datetime,
                    "date": rec.fire_date,
                    "time": rec.fire_time,
                    "region": rec.sido,
                    "location": location_str,
                    "cause": cause_str,
                    "status": status_txt,
                    "casualties": rec.casualties,
                    "deaths": rec.deaths,
                    "injuries": rec.injuries,
                    "is_verified": is_ver,
                    "source": rec.source or ("소방청 공식 상황보고" if is_ver else "소방청 공공데이터포털"),
                    "ticker_text": f"🔥 [{rec.sido}] {rec.sigungu} {rec.location_detail or rec.location_category} ({rec.fire_datetime}) - {status_txt} [원인: {cause_str}]"
                })
            conn.close()
            return items
        except Exception:
            if conn:
                conn.close()
    return items

def get_map_markers_data(limit: int = 150) -> List[Dict[str, Any]]:
    """지도 표출용 좌표 포함 화재 데이터 반환"""
    conn = get_db_connection()
    markers = []
    if conn:
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT * FROM fire_records 
                WHERE is_verified = 1 OR year = 2026 
                ORDER BY is_verified DESC, fire_datetime DESC 
                LIMIT ?
            """, [limit])
            rows = cur.fetchall()
            for r in rows:
                rec = row_to_fire_record(r)
                markers.append({
                    "id": rec.id,
                    "fire_datetime": rec.fire_datetime,
                    "fire_date": rec.fire_date,
                    "fire_time": rec.fire_time,
                    "sido": rec.sido,
                    "sigungu": rec.sigungu,
                    "eupmyeondong": rec.eupmyeondong,
                    "location_category": rec.location_category,
                    "location_detail": rec.location_detail,
                    "cause_category": rec.cause_category,
                    "cause_detail": rec.cause_detail,
                    "deaths": rec.deaths,
                    "injuries": rec.injuries,
                    "casualties": rec.casualties,
                    "property_damage": rec.property_damage,
                    "summary": rec.summary,
                    "lat": rec.lat,
                    "lng": rec.lng,
                    "source": rec.source,
                    "is_verified": rec.is_verified,
                    "status_text": rec.status_text or "완진"
                })
            conn.close()
        except Exception as e:
            if conn:
                conn.close()
    return markers

def query_real_fire_data(
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
    page: int = 1,
    page_size: int = 20
) -> Tuple[List[FireRecord], int, int, int, int]:
    """실제 데이터 조회: (items, total_count, year_scope_total, today_total, sido_total) 반환"""
    now_dt = get_kst_now().replace(tzinfo=None)
    today_str = now_dt.strftime("%Y-%m-%d")
    latest_date_str = get_db_latest_date()
    try:
        ref_dt = datetime.strptime(latest_date_str, "%Y-%m-%d")
    except:
        ref_dt = now_dt

    calc_start_date = start_date
    calc_end_date = end_date

    if period == 'TODAY':
        calc_start_date = latest_date_str
        calc_end_date = latest_date_str
    elif period == '3DAYS':
        calc_start_date = (ref_dt - timedelta(days=2)).strftime("%Y-%m-%d")
        calc_end_date = latest_date_str
    elif period == '7DAYS':
        calc_start_date = (ref_dt - timedelta(days=6)).strftime("%Y-%m-%d")
        calc_end_date = latest_date_str
    elif period == '1MONTH':
        calc_start_date = (ref_dt - timedelta(days=29)).strftime("%Y-%m-%d")
        calc_end_date = latest_date_str

    conn = get_db_connection()
    if conn:
        try:
            where_clauses = []
            params = []

            if start_year:
                where_clauses.append("year >= ?")
                params.append(start_year)
            if end_year:
                where_clauses.append("year <= ?")
                params.append(end_year)

            if calc_start_date:
                where_clauses.append("fire_date >= ?")
                params.append(calc_start_date)
            if calc_end_date:
                where_clauses.append("fire_date <= ?")
                params.append(calc_end_date)

            if sido and sido != "전체":
                where_clauses.append("sido LIKE ?")
                params.append(f"%{sido}%")

            if sigungu and sigungu != "전체":
                where_clauses.append("sigungu LIKE ?")
                params.append(f"%{sigungu}%")

            if cause_category and cause_category != "전체":
                where_clauses.append("cause_category = ?")
                params.append(cause_category)

            if location_category and location_category != "전체":
                where_clauses.append("location_category = ?")
                params.append(location_category)

            if has_deaths is True:
                where_clauses.append("deaths > 0")

            if min_casualties is not None:
                where_clauses.append("casualties >= ?")
                params.append(min_casualties)

            if min_damage is not None:
                where_clauses.append("property_damage >= ?")
                params.append(min_damage)

            if keyword:
                kw = f"%{keyword.strip()}%"
                where_clauses.append("(sido LIKE ? OR sigungu LIKE ? OR eupmyeondong LIKE ? OR location_category LIKE ? OR location_detail LIKE ? OR cause_category LIKE ? OR cause_detail LIKE ? OR summary LIKE ?)")
                params.extend([kw, kw, kw, kw, kw, kw, kw, kw])

            where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""

            # 정렬 칼럼
            allowed_sorts = {
                "fire_datetime": "fire_datetime",
                "casualties": "casualties",
                "deaths": "deaths",
                "injuries": "injuries",
                "property_damage": "property_damage",
                "suppression_minutes": "suppression_minutes"
            }
            sort_col = allowed_sorts.get(sort_by, "fire_datetime")
            sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

            # 1. total_count
            cur = conn.cursor()
            cur.execute(f"SELECT COUNT(*) FROM fire_records{where_str}", params)
            total_count = cur.fetchone()[0]

            # 2. 페이징 아이템
            offset = (page - 1) * page_size
            cur.execute(f"SELECT * FROM fire_records{where_str} ORDER BY {sort_col} {sort_dir} LIMIT ? OFFSET ?", params + [page_size, offset])
            rows = cur.fetchall()
            items = [row_to_fire_record(r) for r in rows]

            # 3. 선택된 연도 범위 총 건수
            y_where = []
            y_params = []
            if start_year:
                y_where.append("year >= ?")
                y_params.append(start_year)
            if end_year:
                y_where.append("year <= ?")
                y_params.append(end_year)
            y_str = (" WHERE " + " AND ".join(y_where)) if y_where else ""
            cur.execute(f"SELECT COUNT(*) FROM fire_records{y_str}", y_params)
            year_scope_total = cur.fetchone()[0]

            # 4. 오늘(또는 최신일자) 발생 건수
            cur.execute("SELECT COUNT(*) FROM fire_records WHERE fire_date = ?", [today_str])
            today_total = cur.fetchone()[0]
            if today_total == 0:
                cur.execute("SELECT MAX(fire_date) FROM fire_records")
                max_d = cur.fetchone()[0]
                if max_d:
                    cur.execute("SELECT COUNT(*) FROM fire_records WHERE fire_date = ?", [max_d])
                    today_total = cur.fetchone()[0]

            # 5. 시도 건수
            sido_total = 0
            if sido and sido != "전체":
                cur.execute(f"SELECT COUNT(*) FROM fire_records{y_str} " + ("AND" if y_str else "WHERE") + " sido LIKE ?", y_params + [f"%{sido}%"])
                sido_total = cur.fetchone()[0]
            else:
                sido_total = year_scope_total

            conn.close()
            return items, total_count, year_scope_total, today_total, sido_total
        except Exception as e:
            if conn:
                conn.close()

    # Fallback to in-memory store
    source = get_all_real_records()
    filtered = filter_and_sort_real_records(
        records=source,
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
    offset = (page - 1) * page_size
    items = filtered[offset:offset + page_size]
    year_scope_total = len(source)
    today_total = sum(1 for r in source if r.fire_date == today_str)
    sido_total = sum(1 for r in source if (sido in r.sido or r.sido in sido)) if (sido and sido != "전체") else year_scope_total

    return items, total_count, year_scope_total, today_total, sido_total

def filter_and_sort_real_records(
    records: Optional[List[FireRecord]] = None,
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
) -> List[FireRecord]:
    if records is None:
        conn = get_db_connection()
        if conn:
            try:
                where_clauses = []
                params = []
                now_dt = get_kst_now().replace(tzinfo=None)
                today_str = now_dt.strftime("%Y-%m-%d")

                calc_start_date = start_date
                calc_end_date = end_date

                if period == 'TODAY':
                    cur = conn.cursor()
                    cur.execute("SELECT COUNT(*) FROM fire_records WHERE fire_date = ?", [today_str])
                    if cur.fetchone()[0] > 0:
                        calc_start_date = today_str
                        calc_end_date = today_str
                    else:
                        cur.execute("SELECT MAX(fire_date) FROM fire_records")
                        max_d = cur.fetchone()[0]
                        if max_d:
                            calc_start_date = max_d
                            calc_end_date = max_d
                elif period == '3DAYS':
                    calc_start_date = (now_dt - timedelta(days=2)).strftime("%Y-%m-%d")
                    calc_end_date = today_str
                elif period == '7DAYS':
                    calc_start_date = (now_dt - timedelta(days=6)).strftime("%Y-%m-%d")
                    calc_end_date = today_str
                elif period == '1MONTH':
                    calc_start_date = (now_dt - timedelta(days=29)).strftime("%Y-%m-%d")
                    calc_end_date = today_str

                if start_year:
                    where_clauses.append("year >= ?")
                    params.append(start_year)
                if end_year:
                    where_clauses.append("year <= ?")
                    params.append(end_year)
                if calc_start_date:
                    where_clauses.append("fire_date >= ?")
                    params.append(calc_start_date)
                if calc_end_date:
                    where_clauses.append("fire_date <= ?")
                    params.append(calc_end_date)
                if sido and sido != "전체":
                    where_clauses.append("sido LIKE ?")
                    params.append(f"%{sido}%")
                if sigungu and sigungu != "전체":
                    where_clauses.append("sigungu LIKE ?")
                    params.append(f"%{sigungu}%")
                if cause_category and cause_category != "전체":
                    where_clauses.append("cause_category LIKE ?")
                    params.append(f"%{cause_category}%")
                if location_category and location_category != "전체":
                    where_clauses.append("location_category LIKE ?")
                    params.append(f"%{location_category}%")
                if has_deaths is True:
                    where_clauses.append("deaths > 0")
                if min_casualties is not None:
                    where_clauses.append("casualties >= ?")
                    params.append(min_casualties)
                if min_damage is not None:
                    where_clauses.append("property_damage >= ?")
                    params.append(min_damage)
                if keyword:
                    where_clauses.append("(sido LIKE ? OR sigungu LIKE ? OR eupmyeondong LIKE ? OR location_category LIKE ? OR location_detail LIKE ? OR cause_category LIKE ? OR cause_detail LIKE ? OR summary LIKE ?)")
                    kw_pat = f"%{keyword.strip()}%"
                    params.extend([kw_pat] * 8)

                where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
                allowed_sorts = {
                    "fire_datetime": "fire_datetime",
                    "casualties": "casualties",
                    "deaths": "deaths",
                    "injuries": "injuries",
                    "property_damage": "property_damage",
                    "suppression_minutes": "suppression_minutes"
                }
                sort_col = allowed_sorts.get(sort_by, "fire_datetime")
                sort_dir = "DESC" if sort_order.lower() == "desc" else "ASC"

                cur = conn.cursor()
                cur.execute(f"SELECT * FROM fire_records{where_str} ORDER BY {sort_col} {sort_dir} LIMIT 50000", params)
                rows = cur.fetchall()
                conn.close()
                return [row_to_fire_record(r) for r in rows]
            except Exception:
                if conn:
                    conn.close()

    source = records if records is not None else get_all_real_records()
    now_dt = get_kst_now().replace(tzinfo=None)
    today_str = now_dt.strftime("%Y-%m-%d")

    calc_start_date = start_date
    calc_end_date = end_date

    if period == 'TODAY':
        calc_start_date = today_str
        calc_end_date = today_str
    elif period == '3DAYS':
        calc_start_date = (now_dt - timedelta(days=2)).strftime("%Y-%m-%d")
        calc_end_date = today_str
    elif period == '7DAYS':
        calc_start_date = (now_dt - timedelta(days=6)).strftime("%Y-%m-%d")
        calc_end_date = today_str
    elif period == '1MONTH':
        calc_start_date = (now_dt - timedelta(days=29)).strftime("%Y-%m-%d")
        calc_end_date = today_str

    filtered = []
    for r in source:
        if start_year and r.year < start_year:
            continue
        if end_year and r.year > end_year:
            continue
        if calc_start_date and r.fire_date < calc_start_date:
            continue
        if calc_end_date and r.fire_date > calc_end_date:
            continue
        if sido and sido != "전체" and sido not in r.sido:
            continue
        if sigungu and sigungu != "전체" and sigungu not in r.sigungu:
            continue
        if cause_category and cause_category != "전체" and cause_category not in r.cause_category:
            continue
        if location_category and location_category != "전체" and location_category not in r.location_category:
            continue
        if has_deaths is True and r.deaths <= 0:
            continue
        if min_casualties is not None and r.casualties < min_casualties:
            continue
        if min_damage is not None and r.property_damage < min_damage:
            continue
        if keyword:
            kw = keyword.strip().lower()
            text_target = f"{r.sido} {r.sigungu} {r.eupmyeondong} {r.location_category} {r.location_detail} {r.cause_category} {r.cause_detail} {r.summary}".lower()
            if kw not in text_target:
                continue
        filtered.append(r)

    is_reverse = (sort_order.lower() == "desc")
    if sort_by == "fire_datetime":
        filtered.sort(key=lambda x: x.fire_datetime, reverse=is_reverse)
    elif sort_by == "casualties":
        filtered.sort(key=lambda x: (x.casualties, x.deaths, x.fire_datetime), reverse=is_reverse)
    elif sort_by == "deaths":
        filtered.sort(key=lambda x: (x.deaths, x.casualties, x.fire_datetime), reverse=is_reverse)
    elif sort_by == "property_damage":
        filtered.sort(key=lambda x: (x.property_damage, x.fire_datetime), reverse=is_reverse)
    else:
        filtered.sort(key=lambda x: x.fire_datetime, reverse=is_reverse)

    return filtered

def calculate_real_statistics(
    records: Optional[List[FireRecord]] = None,
    sido: Optional[str] = None,
    sigungu: Optional[str] = None,
    keyword: Optional[str] = None,
    start_year: Optional[int] = None,
    end_year: Optional[int] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    period: Optional[str] = None,
    cause_category: Optional[str] = None,
    location_category: Optional[str] = None,
    min_casualties: Optional[int] = None,
    min_damage: Optional[int] = None,
    has_deaths: Optional[bool] = None
) -> Dict[str, Any]:
    """실제 데이터 통계 산출"""
    conn = get_db_connection()
    if conn and records is None:
        try:
            where_clauses = []
            params = []

            if start_year:
                where_clauses.append("year >= ?")
                params.append(start_year)
            if end_year:
                where_clauses.append("year <= ?")
                params.append(end_year)

            now_dt = get_kst_now().replace(tzinfo=None)
            today_str = now_dt.strftime("%Y-%m-%d")
            calc_start_date = start_date
            calc_end_date = end_date

            if period == 'TODAY':
                calc_start_date = today_str
                calc_end_date = today_str
            elif period == '3DAYS':
                calc_start_date = (now_dt - timedelta(days=2)).strftime("%Y-%m-%d")
                calc_end_date = today_str
            elif period == '7DAYS':
                calc_start_date = (now_dt - timedelta(days=6)).strftime("%Y-%m-%d")
                calc_end_date = today_str
            elif period == '1MONTH':
                calc_start_date = (now_dt - timedelta(days=29)).strftime("%Y-%m-%d")
                calc_end_date = today_str

            if calc_start_date:
                where_clauses.append("fire_date >= ?")
                params.append(calc_start_date)
            if calc_end_date:
                where_clauses.append("fire_date <= ?")
                params.append(calc_end_date)

            if sido and sido != "전체":
                where_clauses.append("sido LIKE ?")
                params.append(f"%{sido}%")

            if sigungu and sigungu != "전체":
                where_clauses.append("sigungu LIKE ?")
                params.append(f"%{sigungu}%")

            if cause_category and cause_category != "전체":
                where_clauses.append("cause_category = ?")
                params.append(cause_category)

            if location_category and location_category != "전체":
                where_clauses.append("location_category = ?")
                params.append(location_category)

            if has_deaths is True:
                where_clauses.append("deaths > 0")

            if min_casualties is not None:
                where_clauses.append("casualties >= ?")
                params.append(min_casualties)

            if min_damage is not None:
                where_clauses.append("property_damage >= ?")
                params.append(min_damage)

            if keyword:
                kw = f"%{keyword.strip()}%"
                where_clauses.append("(sido LIKE ? OR sigungu LIKE ? OR eupmyeondong LIKE ? OR location_category LIKE ? OR location_detail LIKE ? OR cause_category LIKE ? OR cause_detail LIKE ? OR summary LIKE ?)")
                params.extend([kw, kw, kw, kw, kw, kw, kw, kw])

            where_str = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
            cur = conn.cursor()

            # 기본 KPI
            cur.execute(f"SELECT COUNT(*), COALESCE(SUM(deaths), 0), COALESCE(SUM(injuries), 0), COALESCE(SUM(casualties), 0), COALESCE(SUM(property_damage), 0) FROM fire_records{where_str}", params)
            row = cur.fetchone()
            total_fires = row[0]
            total_deaths = row[1]
            total_injuries = row[2]
            total_casualties = row[3]
            total_damage = row[4]

            # 시도별
            cur.execute(f"SELECT sido, COUNT(*) FROM fire_records{where_str} GROUP BY sido ORDER BY COUNT(*) DESC", params)
            sido_stats = [{"sido": r[0], "count": r[1]} for r in cur.fetchall()]

            # 원인별
            cur.execute(f"SELECT cause_category, COUNT(*) FROM fire_records{where_str} GROUP BY cause_category ORDER BY COUNT(*) DESC", params)
            cause_stats = [{"cause": r[0], "count": r[1]} for r in cur.fetchall()]

            # 장소별
            cur.execute(f"SELECT location_category, COUNT(*) FROM fire_records{where_str} GROUP BY location_category ORDER BY COUNT(*) DESC", params)
            location_stats = [{"location": r[0], "count": r[1]} for r in cur.fetchall()]

            # 연도별
            cur.execute(f"SELECT year, COUNT(*) FROM fire_records{where_str} GROUP BY year ORDER BY year ASC", params)
            yearly_stats = [{"year": str(r[0]), "count": r[1]} for r in cur.fetchall()]

            # 전국 총계
            cur.execute("SELECT COUNT(*) FROM fire_records")
            national_total = cur.fetchone()[0]

            sido_total = 0
            if sido and sido != "전체":
                cur.execute("SELECT COUNT(*) FROM fire_records WHERE sido LIKE ?", [f"%{sido}%"])
                sido_total = cur.fetchone()[0]
            else:
                sido_total = national_total

            sido_pct = round((sido_total / max(1, national_total)) * 100, 1) if national_total > 0 else 0.0
            sgg_pct = round((total_fires / max(1, sido_total)) * 100, 1) if (sigungu and sigungu != "전체" and sido_total > 0) else None

            conn.close()
            return {
                "total_fires": total_fires,
                "total_casualties": total_casualties,
                "total_deaths": total_deaths,
                "total_injuries": total_injuries,
                "total_property_damage_cheonwon": total_damage,
                "sido_total_fires": sido_total,
                "national_total_fires": national_total,
                "sido_percentage": sido_pct if (sido and sido != "전체") else 100.0,
                "sigungu_percentage": sgg_pct,
                "sido_stats": sido_stats,
                "cause_stats": cause_stats,
                "location_stats": location_stats,
                "yearly_stats": yearly_stats
            }
        except Exception:
            if conn:
                conn.close()

    # In-memory fallback
    rec_list = records if records is not None else get_all_real_records()
    total_fires = len(rec_list)
    total_deaths = sum(r.deaths for r in rec_list)
    total_injuries = sum(r.injuries for r in rec_list)
    total_casualties = total_deaths + total_injuries
    total_damage = sum(r.property_damage for r in rec_list)

    sido_counts: Dict[str, int] = {}
    for r in rec_list:
        sido_counts[r.sido] = sido_counts.get(r.sido, 0) + 1

    cause_counts: Dict[str, int] = {}
    for r in rec_list:
        cause_counts[r.cause_category] = cause_counts.get(r.cause_category, 0) + 1

    location_counts: Dict[str, int] = {}
    for r in rec_list:
        location_counts[r.location_category] = location_counts.get(r.location_category, 0) + 1

    yearly_counts: Dict[str, int] = {}
    for r in rec_list:
        y_str = str(r.year)
        yearly_counts[y_str] = yearly_counts.get(y_str, 0) + 1

    sido_total = 0
    if sido and sido != "전체":
        sido_total = sum(1 for r in rec_list if (sido in r.sido or r.sido in sido))
    else:
        sido_total = total_fires

    sido_pct = round((sido_total / max(1, total_fires)) * 100, 1) if total_fires > 0 else 0.0
    sgg_pct = round((total_fires / max(1, sido_total)) * 100, 1) if (sigungu and sigungu != "전체" and sido_total > 0) else None

    return {
        "total_fires": total_fires,
        "total_casualties": total_casualties,
        "total_deaths": total_deaths,
        "total_injuries": total_injuries,
        "total_property_damage_cheonwon": total_damage,
        "sido_total_fires": sido_total,
        "national_total_fires": total_fires,
        "sido_percentage": sido_pct if (sido and sido != "전체") else 100.0,
        "sigungu_percentage": sgg_pct,
        "sido_stats": [{"sido": k, "count": v} for k, v in sorted(sido_counts.items(), key=lambda x: x[1], reverse=True)],
        "cause_stats": [{"cause": k, "count": v} for k, v in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)],
        "location_stats": [{"location": k, "count": v} for k, v in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)],
        "yearly_stats": [{"year": k, "count": v} for k, v in sorted(yearly_counts.items())]
    }
