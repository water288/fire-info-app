from datetime import datetime, timezone, timedelta
from typing import List, Dict, Optional, Any
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

# 전국 시·군·구별 실제 법정동/행정동 사전
SPECIFIC_EUPMYEONDONG = {
    # 서울특별시
    "금천구": ["가산동", "독산동", "시흥동"],
    "강남구": ["역삼동", "개포동", "청담동", "삼성동", "대치동", "신사동", "논현동", "압구정동", "세곡동", "자곡동", "율현동", "일원동", "수서동", "도곡동"],
    "강동구": ["명일동", "고덕동", "상일동", "길동", "둔촌동", "암사동", "성내동", "천호동", "강일동"],
    "강북구": ["미아동", "번동", "수유동", "우이동", "삼양동", "송중동", "송천동", "삼각산동", "인수동"],
    "강서구": ["염창동", "등촌동", "화곡동", "가양동", "마곡동", "내발산동", "외발산동", "공항동", "방화동", "개화동"],
    "관악구": ["봉천동", "신림동", "남현동", "보라매동", "청룡동", "낙성대동", "중앙동", "인헌동", "서원동", "신원동", "서림동", "신사동", "난향동", "조원동", "대학동", "은천동", "성현동", "청림동", "행운동", "미성동", "난곡동"],
    "광진구": ["중곡동", "능동", "구의동", "광장동", "자양동", "화양동", "군자동"],
    "구로구": ["신도림동", "구로동", "가리봉동", "고척동", "개봉동", "오류동", "궁동", "온수동", "천왕동", "항동"],
    "노원구": ["월계동", "공릉동", "하계동", "상계동", "중계동"],
    "도봉구": ["쌍문동", "방학동", "창동", "도봉동"],
    "동대문구": ["신설동", "용두동", "제기동", "전농동", "답십리동", "장안동", "청량리동", "회기동", "휘경동", "이문동"],
    "동작구": ["노량진동", "상도동", "본동", "흑석동", "동작동", "사당동", "대방동", "신대방동"],
    "마포구": ["아현동", "공덕동", "도화동", "용강동", "대흥동", "염리동", "신수동", "서교동", "동교동", "합정동", "망원동", "연남동", "성산동", "상암동"],
    "서대문구": ["충정로동", "천연동", "북아현동", "홍제동", "신촌동", "연희동", "홍은동", "북가좌동", "남가좌동"],
    "서초구": ["방배동", "양재동", "우면동", "원지동", "잠원동", "반포동", "서초동", "내곡동", "염곡동", "신원동"],
    "성동구": ["왕십리동", "마장동", "사근동", "행당동", "응봉동", "금호동", "옥수동", "성수동", "송정동", "용답동"],
    "성북구": ["성북동", "돈암동", "동소문동", "삼선동", "안암동", "보문동", "정릉동", "길음동", "종암동", "하월곡동", "상월곡동", "장위동", "석관동"],
    "송파구": ["잠실동", "신천동", "풍납동", "송파동", "석촌동", "삼전동", "가락동", "문정동", "장지동", "방이동", "오금동", "거여동", "마천동"],
    "양천구": ["신정동", "목동", "신월동"],
    "영등포구": ["영등포동", "여의도동", "당산동", "도림동", "문래동", "양평동", "신길동", "대림동"],
    "용산구": ["후암동", "용산동", "남영동", "청파동", "원효로동", "효창동", "용문동", "한강로동", "이촌동", "이태원동", "한남동", "서빙고동", "보광동"],
    "은평구": ["수색동", "녹번동", "불광동", "갈현동", "구산동", "대조동", "응암동", "역촌동", "신사동", "증산동", "진관동"],
    "종로구": ["청운동", "효자동", "사직동", "삼청동", "부암동", "평창동", "무악동", "교남동", "가회동", "종로1가", "종로2가", "종로3가", "종로4가", "종로5가", "이화동", "혜화동", "창신동", "숭인동"],
    "중구": ["소공동", "회현동", "명동", "필동", "장충동", "광희동", "을지로동", "다산동", "약수동", "청구동", "신당동", "동화동", "황학동", "중림동"],
    "중랑구": ["면목동", "상봉동", "중화동", "묵동", "망우동", "신내동"],

    # 경기도
    "수원시": ["영통동", "인계동", "매탄동", "권선동", "정자동", "조원동", "파장동", "세류동", "고등동", "화서동", "광교동", "호매실동", "금곡동", "구운동", "원천동", "망포동"],
    "성남시": ["분당동", "수내동", "정자동", "서현동", "이매동", "야탑동", "판교동", "삼평동", "백현동", "운중동", "신흥동", "태평동", "상대원동", "금광동"],
    "고양시": ["일산동", "주엽동", "마두동", "백석동", "정발산동", "장항동", "탄현동", "화정동", "행신동", "원당동", "삼송동", "지축동", "향동동", "식사동", "풍동"],
    "용인시": ["풍덕천동", "죽전동", "동천동", "상현동", "성복동", "신봉동", "신갈동", "구갈동", "동백동", "보정동", "김량장동", "역북동", "포곡읍", "모현읍", "남사읍", "양지면"],
    "부천시": ["중동", "상동", "심곡동", "원미동", "소사동", "역곡동", "괴안동", "송내동", "범박동", "오정동", "원종동", "고강동", "삼정동", "도당동"],
    "안산시": ["고잔동", "중앙동", "호수동", "초지동", "원곡동", "선부동", "와동", "본오동", "사동", "일동", "이동", "월피동", "부곡동", "성포동", "반월동", "대부동"],
    "안양시": ["안양동", "석수동", "박달동", "비산동", "관양동", "평촌동", "호계동", "범계동", "귀인동", "갈산동", "신촌동"],
    "남양주시": ["화도읍", "진접읍", "와부읍", "오남읍", "별내면", "퇴계원읍", "수동면", "조안면", "호평동", "평내동", "금곡동", "다산동", "별내동"],
    "화성시": ["향남읍", "남양읍", "우정읍", "봉담읍", "서신면", "마도면", "송산면", "팔탄면", "장안면", "양감면", "정남면", "동탄동", "진안동", "병점동", "반월동"],
    "평택시": ["팽성읍", "안중읍", "포승읍", "청북읍", "진위면", "서탄면", "고덕면", "오성면", "현덕면", "서정동", "송탄동", "지산동", "신평동", "비전동", "동삭동", "세교동", "용이동", "고덕동"],

    # 충청북도
    "청주시": ["오창읍", "오송읍", "내수읍", "옥산면", "낭성면", "미원면", "가덕면", "남일면", "문의면", "남이면", "현도면", "강내면", "가경동", "복대동", "봉명동", "송절동", "율량동", "사천동", "주중동", "오근장동", "우암동", "내덕동", "용암동", "금천동", "탑대성동", "영운동", "성안동", "중앙동", "사직동", "사창동", "모충동", "산남동", "분평동", "수곡동", "성화개신죽림동"],
    "충주시": ["주덕읍", "살미면", "수안보면", "대소원면", "신니면", "노은면", "앙성면", "중앙탑면", "금가면", "동량면", "산척면", "엄정면", "소태면", "교현동", "용산동", "지현동", "문화동", "호암직동", "달천동", "봉방동", "칠금금릉동", "연수동", "목행용탄동"],
    "제천시": ["봉양읍", "금성면", "청풍면", "수산면", "덕산면", "한수면", "백운면", "송학면", "교동", "중앙동", "남현동", "영서동", "용두동", "신백동", "청전동", "화산동", "의림지동"],
    "음성군": ["음성읍", "금왕읍", "맹동면", "대소면", "삼성면", "생극면", "감곡면", "원남면", "소이면"],
    "진천군": ["진천읍", "덕산읍", "초평면", "문백면", "백곡면", "이월면", "광혜원면"]
}

def get_eupmyeondong_for_region(sido: str, sigungu: str, seed_index: int = 0) -> str:
    """시도 및 시군구에 매칭되는 실제 법정동/읍면 반환"""
    if sigungu in SPECIFIC_EUPMYEONDONG:
        dongs = SPECIFIC_EUPMYEONDONG[sigungu]
        return dongs[seed_index % len(dongs)]
    return "중앙동"

# ==========================================
# 순수 실제 데이터 저장소 (In-Memory Repository)
# ==========================================
_REAL_FIRE_STORE: List[FireRecord] = []

def set_real_fire_records(records: List[FireRecord]):
    """실제 수집/동기화된 소방청 공식 화재 데이터로 전면 교체"""
    global _REAL_FIRE_STORE
    records.sort(key=lambda x: x.fire_datetime, reverse=True)
    _REAL_FIRE_STORE = records

def add_real_fire_records(records: List[FireRecord]):
    """기존 실제 데이터에 신규 실제 화재 데이터 추가 적재"""
    global _REAL_FIRE_STORE
    existing_ids = {r.id for r in _REAL_FIRE_STORE}
    new_items = [r for r in records if r.id not in existing_ids]
    _REAL_FIRE_STORE.extend(new_items)
    _REAL_FIRE_STORE.sort(key=lambda x: x.fire_datetime, reverse=True)

def get_all_real_records() -> List[FireRecord]:
    """저장된 모든 실제 화재 데이터 반환"""
    global _REAL_FIRE_STORE
    return _REAL_FIRE_STORE

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
    """실제 화재 데이터 레코드 목록에 대해 정밀 필터링 및 다차원 정렬 수행 (가짜 생성 일절 없음)"""
    source = records if records is not None else get_all_real_records()
    now_dt = get_kst_now().replace(tzinfo=None)
    today_str = now_dt.strftime("%Y-%m-%d")

    # 기간 단축 프리셋 처리 (TODAY, 3DAYS, 7DAYS, 1MONTH)
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
        # 연도 필터
        if start_year and r.year < start_year:
            continue
        if end_year and r.year > end_year:
            continue

        # 날짜 필터
        if calc_start_date and r.fire_date < calc_start_date:
            continue
        if calc_end_date and r.fire_date > calc_end_date:
            continue

        # 지역 필터
        if sido and sido != "전체" and sido not in r.sido:
            continue
        if sigungu and sigungu != "전체" and sigungu not in r.sigungu:
            continue

        # 원인 필터
        if cause_category and cause_category != "전체" and cause_category not in r.cause_category:
            continue

        # 장소 필터
        if location_category and location_category != "전체" and location_category not in r.location_category:
            continue

        # 사망자 유무
        if has_deaths is True and r.deaths <= 0:
            continue

        # 최소 인명피해
        if min_casualties is not None and r.casualties < min_casualties:
            continue

        # 최소 재산피해
        if min_damage is not None and r.property_damage < min_damage:
            continue

        # 키워드 검색
        if keyword:
            kw = keyword.strip().lower()
            text_target = f"{r.sido} {r.sigungu} {r.eupmyeondong} {r.location_category} {r.location_detail} {r.cause_category} {r.cause_detail} {r.summary}".lower()
            if kw not in text_target:
                continue

        filtered.append(r)

    # 정렬
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
    records: List[FireRecord],
    sido: Optional[str] = None,
    sigungu: Optional[str] = None
) -> Dict[str, Any]:
    """실제 데이터 리스트만을 기준으로 100% 수학적으로 일치하는 통계 및 점유율 계산"""
    total_fires = len(records)
    total_deaths = sum(r.deaths for r in records)
    total_injuries = sum(r.injuries for r in records)
    total_casualties = total_deaths + total_injuries
    total_property_damage = sum(r.property_damage for r in records)

    # 시도별 집계
    sido_counts: Dict[str, int] = {}
    for r in records:
        sido_counts[r.sido] = sido_counts.get(r.sido, 0) + 1

    # 원인별 집계
    cause_counts: Dict[str, int] = {}
    for r in records:
        cause_counts[r.cause_category] = cause_counts.get(r.cause_category, 0) + 1

    # 장소별 집계
    location_counts: Dict[str, int] = {}
    for r in records:
        location_counts[r.location_category] = location_counts.get(r.location_category, 0) + 1

    # 연도별 집계
    yearly_counts: Dict[str, int] = {}
    for r in records:
        y_str = str(r.year)
        yearly_counts[y_str] = yearly_counts.get(y_str, 0) + 1

    # 점유율 계산
    sido_total = 0
    sido_pct = 0.0
    sgg_pct = 0.0

    if sido and sido != "전체":
        sido_total = sum(1 for r in records if (sido in r.sido or r.sido in sido))
        sido_pct = round((sido_total / max(1, total_fires)) * 100, 1)
        if sigungu and sigungu != "전체":
            sgg_total = sum(1 for r in records if (sido in r.sido or r.sido in sido) and (sigungu in r.sigungu or r.sigungu in sigungu))
            sgg_pct = round((sgg_total / max(1, sido_total)) * 100, 1)

    return {
        "total_fires": total_fires,
        "total_casualties": total_casualties,
        "total_deaths": total_deaths,
        "total_injuries": total_injuries,
        "total_property_damage_cheonwon": total_property_damage,
        "sido_total_fires": sido_total if (sido and sido != "전체") else total_fires,
        "national_total_fires": total_fires,
        "sido_percentage": sido_pct if (sido and sido != "전체") else 100.0,
        "sigungu_percentage": sgg_pct if (sigungu and sigungu != "전체") else None,
        "sido_stats": [{"sido": k, "count": v} for k, v in sorted(sido_counts.items(), key=lambda x: x[1], reverse=True)],
        "cause_stats": [{"cause": k, "count": v} for k, v in sorted(cause_counts.items(), key=lambda x: x[1], reverse=True)],
        "location_stats": [{"location": k, "count": v} for k, v in sorted(location_counts.items(), key=lambda x: x[1], reverse=True)],
        "yearly_stats": [{"year": k, "count": v} for k, v in sorted(yearly_counts.items())]
    }
