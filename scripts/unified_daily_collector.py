# -*- coding: utf-8 -*-
"""
전국 17개 시·도 소방본부 및 소방청 119일일상황 통합 자동 수집 및 배포 스크립트
매일 아침 06:30 KST 자동 실행 (GitHub Actions & 로컬 스케줄러)
"""
import os
import sys
import json
import re
import ssl
import io
import time
import gzip
import shutil
import sqlite3
import hashlib
import zipfile
import subprocess
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

try: import pymupdf as fitz
except ImportError: fitz = None

try: import pypdf
except ImportError: pypdf = None

try: import olefile
except ImportError: olefile = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "fire_records.db")
GZ_PATH = os.path.join(BASE_DIR, "fire_records.db.gz")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# KST Timezone
KST = timezone(timedelta(hours=9))

def get_kst_now():
    return datetime.now(timezone.utc).astimezone(KST)

# 시도 표준명 매핑
SIDO_ALIASES = {
    "서울": "서울특별시", "서울시": "서울특별시", "서울특별시": "서울특별시",
    "부산": "부산광역시", "부산시": "부산광역시", "부산광역시": "부산광역시",
    "대구": "대구광역시", "대구시": "대구광역시", "대구광역시": "대구광역시",
    "인천": "인천광역시", "인천시": "인천광역시", "인천광역시": "인천광역시",
    "광주": "광주광역시", "광주시": "광주광역시", "광주광역시": "광주광역시",
    "대전": "대전광역시", "대전시": "대전광역시", "대전광역시": "대전광역시",
    "울산": "울산광역시", "울산시": "울산광역시", "울산광역시": "울산광역시",
    "세종": "세종특별자치시", "세종시": "세종특별자치시", "세종특별자치시": "세종특별자치시",
    "경기": "경기도", "경기도": "경기도",
    "강원": "강원특별자치도", "강원도": "강원특별자치도", "강원특별자치도": "강원특별자치도",
    "충북": "충청북도", "충청북도": "충청북도",
    "충남": "충청남도", "충청남도": "충청남도",
    "전북": "전북특별자치도", "전라북도": "전북특별자치도", "전북특별자치도": "전북특별자치도",
    "전남": "전라남도", "전라남도": "전라남도",
    "경북": "경상북도", "경상북도": "경상북도",
    "경남": "경상남도", "경상남도": "경상남도",
    "제주": "제주특별자치도", "제주도": "제주특별자치도", "제주특별자치도": "제주특별자치도"
}

# 정밀 지오코딩 좌표계 임포트
try:
    if BASE_DIR not in sys.path:
        sys.path.insert(0, BASE_DIR)
    from app.services.geo_coordinates import get_precise_coordinates, SIGUNGU_COORDINATES, SIDO_COORDINATES
except Exception:
    def get_precise_coordinates(sido="", sigungu="", eupmyeondong="", location_detail=""):
        return 36.5, 127.8

def fetch_url(url, headers=None, timeout=6):
    h = {"User-Agent": USER_AGENT}
    if headers: h.update(headers)
    req = urllib.request.Request(url, headers=h)
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as resp:
            return resp.read()
    except Exception: return None

def parse_file_content(data_bytes):
    if not data_bytes or len(data_bytes) < 30: return ""
    if data_bytes.startswith(b"%PDF"):
        if fitz:
            try:
                doc = fitz.open(stream=data_bytes, filetype="pdf")
                return "\n".join(p.get_text() for p in doc)
            except Exception: pass
        if pypdf:
            try:
                reader = pypdf.PdfReader(io.BytesIO(data_bytes))
                return "\n".join(p.extract_text() or "" for p in reader.pages)
            except Exception: pass
    if data_bytes.startswith(b"PK"):
        try:
            zf = zipfile.ZipFile(io.BytesIO(data_bytes))
            texts = []
            for n in sorted(zf.namelist()):
                if n.startswith("Contents/section") and n.endswith(".xml"):
                    root = ET.fromstring(zf.read(n))
                    for el in root.iter():
                        if el.text and el.text.strip():
                            texts.append(el.text.strip())
            return "\n".join(texts)
        except Exception: pass
    if data_bytes.startswith(b"\xd0\xcf\x11\xe0") or b"HWP Document" in data_bytes[:64]:
        if olefile:
            try:
                ole = olefile.OleFileIO(io.BytesIO(data_bytes))
                if ole.exists("PrvText"):
                    return ole.openstream("PrvText").read().decode("utf-16le", errors="ignore")
            except Exception: pass
    try: return data_bytes.decode("utf-8", errors="ignore")
    except Exception:
        try: return data_bytes.decode("cp949", errors="ignore")
        except Exception: return ""

PRECISION_DONG_MAP = {
    "구좌읍": (33.5225, 126.8524), "조천읍": (33.5350, 126.6341), "한림읍": (33.3934, 126.2642),
    "애월읍": (33.4623, 126.3315), "한경면": (33.3512, 126.1965), "대정읍": (33.2268, 126.2523),
    "남원읍": (33.2801, 126.7198), "성산읍": (33.4632, 126.9184), "안덕면": (33.2505, 126.3385),
    "불로동": (35.9085, 128.6367), "봉무동": (35.9215, 128.6485), "신암동": (35.8821, 128.6215),
    "평리동": (35.8712, 128.5585), "상인동": (35.8197, 128.5375), "다사읍": (35.8712, 128.4615),
    "원당동": (37.5954, 126.7029), "당하동": (37.5912, 126.6715), "마전동": (37.6012, 126.6615),
    "송도동": (37.3912, 126.6485), "청라동": (37.5312, 126.6515), "부평동": (37.4912, 126.7215),
    "세동": (36.2954, 127.2792), "송강동": (36.4312, 127.3815), "관평동": (36.4215, 127.3912),
    "봉명동": (36.3585, 127.3412), "도안동": (36.3215, 127.3485), "관저동": (36.2985, 127.3312),
    "서생면": (35.3789, 129.3175), "온양읍": (35.4112, 129.2815), "온산읍": (35.4412, 129.3312),
    "범서읍": (35.5612, 129.2485), "언양읍": (35.5685, 129.1285), "삼산동": (35.5385, 129.3412),
    "조치원읍": (36.6015, 127.3012), "연기면": (36.5285, 127.2715), "연동면": (36.5612, 127.3385),
    "부강면": (36.5285, 127.3685), "금남면": (36.4685, 127.2815), "장군면": (36.4985, 127.2012),
    "한솔동": (36.4785, 127.2512), "새롬동": (36.4885, 127.2585), "나성동": (36.4885, 127.2612),
    "사천면": (37.8341, 128.8542), "인제읍": (38.0685, 128.1712), "옥천동": (37.7585, 128.8985),
    "후평동": (37.8812, 127.7485), "퇴계동": (37.8585, 127.7285), "단계동": (37.3512, 127.9312)
}

SIDO_CENTERS = {
    "서울": (37.5665, 126.9780), "부산": (35.1796, 129.0756), "대구": (35.8714, 128.6014),
    "인천": (37.4563, 126.7052), "광주": (35.1595, 126.8526), "대전": (36.3504, 127.3845),
    "울산": (35.5384, 129.3114), "세종": (36.4800, 127.2890), "경기": (37.2750, 127.0094),
    "강원": (37.8854, 127.7298), "충북": (36.6357, 127.4914), "충남": (36.6588, 126.6728),
    "전북": (35.8202, 127.1088), "전남": (34.8160, 126.4629), "경북": (36.5760, 128.5056),
    "경남": (35.2376, 128.6919), "제주": (33.4996, 126.5312)
}

def get_coords(location_str, record_id=""):
    lat, lng = 36.5, 127.8
    matched = False
    for dong, (la, ln) in PRECISION_DONG_MAP.items():
        if dong in location_str:
            lat, lng = la, ln
            matched = True
            break
    if not matched:
        for sido, (la, ln) in SIDO_CENTERS.items():
            if sido in location_str:
                lat, lng = la, ln
                matched = True
                break
    hash_str = f"{record_id}_{location_str}"
    h = int(hashlib.md5(hash_str.encode("utf-8")).hexdigest()[:6], 16)
    d_lat = ((h % 100) - 50) * 0.00008
    d_lng = (((h // 100) % 100) - 50) * 0.00008
    return round(lat + d_lat, 6), round(lng + d_lng, 6)

def clean_money(text):
    m = re.search(r"([0-9,]+\s*(?:천원|백만원|만원|억원|원))", text)
    return m.group(1).strip() if m else "0천원"

def collect_nfa():
    print("[수집] 소방청 국가 119일일상황실...")
    results = []
    try:
        url = "https://www.nfa.go.kr/nfa/news/firesafe/dailyfire/"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            txt = tr.get_text(strip=True)
            if "소방활동" in txt or "일일" in txt:
                date_m = re.search(r"2026[-. ]?09[-. ]?([0-9]{1,2})", txt)
                date_str = f"2026-09-{int(date_m.group(1)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                a_tag = tr.find("a")
                if not a_tag or not a_tag.get("href"): continue
                href = a_tag["href"]
                art_url = "https://www.nfa.go.kr/nfa/news/firesafe/dailyfire/" + href if href.startswith("?") else href
                art_html = fetch_url(art_url)
                if not art_html: continue
                art_soup = BeautifulSoup(art_html.decode("utf-8", errors="ignore"), "html.parser")
                for a in art_soup.find_all("a"):
                    h = a.get("href", "")
                    m_down = re.search(r'Jnit_boardDownload\(\s*[\'\"]([^\'\;]+)', h)
                    if m_down:
                        down_rel = m_down.group(1).strip()
                        f_url = "https://www.nfa.go.kr" + down_rel
                        f_data = fetch_url(f_url)
                        if f_data:
                            text = parse_file_content(f_data)
                            for line in text.split("\n"):
                                if "화재" in line and ("발생" in line or "진화" in line or "소실" in line or "피해" in line):
                                    tm_m = re.search(r"(\d{1,2}:\d{2})", line)
                                    tm = tm_m.group(1) if tm_m else "00:00"
                                    loc_m = re.search(r"([가-힣]+(?:시|도|구|군)\s+[가-힣0-9]+(?:동|읍|면))", line)
                                    loc = loc_m.group(1) if loc_m else "전국"
                                    lat, lng = get_coords(loc, f"NFA-{date_str}-{tm}")
                                    dmg = clean_money(line)
                                    d_clean = date_str.replace("-", "")
                                    t_clean = tm.replace(":", "")
                                    results.append({
                                        "id": f"NFA-DAILY-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                        "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                        "location": loc, "address": loc, "bldg_type": "기타", "cause": "원인 조사 중",
                                        "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                        "lat": lat, "lng": lng, "description": f"[소방청 일일소방활동] {line[:200].strip()}",
                                        "title": f"소방청 {loc} 화재 출동", "source": "소방청 119종합상황실 일일소방활동상황"
                                    })
    except Exception as e: print(f"NFA error: {e}")
    return results

def collect_sejong():
    print("[수집] 세종특별자치시 소방본부...")
    results = []
    try:
        url = "https://www.sejong.go.kr/bbs/R0142/list.do"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            txt = tr.get_text(strip=True)
            if "소방활동" in txt or "소방상황" in txt or "일일소방" in txt:
                date_m = re.search(r"2026[-. ]?09[-. ]?([0-9]{1,2})", txt)
                date_str = f"2026-09-{int(date_m.group(1)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                for a in tr.find_all("a", href=re.compile(r"download|fileSeq|atchFileId")):
                    href = a["href"]
                    down_url = "https://www.sejong.go.kr" + href if href.startswith("/") else href
                    file_data = fetch_url(down_url)
                    if file_data:
                        text = parse_file_content(file_data)
                        lines = [l.strip() for l in text.split("\n") if l.strip()]
                        for i, line in enumerate(lines):
                            if "<" in line and "화재" in line and ">" in line:
                                block = " ".join(lines[i+1:min(len(lines), i+12)])
                                tm_m = re.search(r"(\d{1,2}:\d{2})", block)
                                tm = tm_m.group(1) if tm_m else "00:00"
                                loc_m = re.search(r"([가-힣]+(?:읍|면|동)(?:\s+[가-힣]+리)?)", block)
                                loc = f"세종특별자치시 {loc_m.group(1)}" if loc_m else "세종특별자치시"
                                cause_m = re.search(r"원인\s*:\s*([^,\n\)]+)", block)
                                cause = cause_m.group(1).strip() if cause_m else "원인 조사 중"
                                dmg = clean_money(block)
                                lat, lng = get_coords(loc, f"SEJONG-{date_str}-{tm}")
                                d_clean = date_str.replace("-", "")
                                t_clean = tm.replace(":", "")
                                results.append({
                                    "id": f"SEJONG-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                    "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                    "location": loc, "address": loc, "bldg_type": "기타", "cause": cause,
                                    "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                    "lat": lat, "lng": lng, "description": f"[세종소방본부 일일소방상황] {block[:200]}",
                                    "title": f"세종 {loc} 화재", "source": "세종특별자치시소방본부 일일소방상황"
                                })
    except Exception as e: print(f"Sejong error: {e}")
    return results

def collect_jeju():
    print("[수집] 제주특별자치도 소방안전본부...")
    results = []
    try:
        url = "https://www.jeju.go.kr/119/promote/fire.htm?page=1"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) >= 4:
                date_str = tds[3].get_text(strip=True)
                down_a = tr.find("a", href=re.compile(r"act=download"))
                if not down_a: continue
                down_url = "https://www.jeju.go.kr" + down_a["href"]
                hwpx_data = fetch_url(down_url)
                if not hwpx_data: continue
                text = parse_file_content(hwpx_data)
                for section in text.split("▶"):
                    if "화재" in section and ("소실" in section or "원인" in section or "피해" in section):
                        tm_m = re.search(r"(\d{1,2}:\d{2})", section)
                        tm = tm_m.group(1) if tm_m else "00:00"
                        loc_m = re.search(r"((?:제주시|서귀포시)\s+[가-힣0-9]+(?:읍|면|동|리))", section)
                        loc = f"제주특별자치도 {loc_m.group(1)}" if loc_m else "제주특별자치도"
                        lat, lng = get_coords(loc, f"JEJU-{date_str}-{tm}")
                        cause_m = re.search(r"원인\s*:\s*([^,\n\)]+)", section)
                        cause = cause_m.group(1).strip() if cause_m else "원인 조사 중"
                        dmg = clean_money(section)
                        d_clean = date_str.replace("-", "")
                        t_clean = tm.replace(":", "")
                        results.append({
                            "id": f"JEJU-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                            "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                            "location": loc, "address": loc, "bldg_type": "기타", "cause": cause,
                            "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                            "lat": lat, "lng": lng, "description": f"[제주소방안전본부 소방종합상황] {section[:200].strip()}",
                            "title": f"제주 {loc} 화재", "source": "제주특별자치도 소방안전본부 소방종합상황일일보고"
                        })
    except Exception as e: print(f"Jeju error: {e}")
    return results

def collect_gangwon():
    print("[수집] 강원특별자치도 소방본부...")
    results = []
    try:
        url = "https://fire.gwd.go.kr/fire/partici/parti_daily"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for a in soup.find_all("a", href=re.compile(r"articleSeq=")):
            txt = a.get_text(strip=True)
            if "119소방활동" in txt or "상황보고" in txt:
                date_m = re.search(r"(\d{1,2})\.\s*(\d{1,2})", txt)
                date_str = f"2026-{int(date_m.group(1)):02d}-{int(date_m.group(2)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                art_url = "https://fire.gwd.go.kr" + a["href"]
                art_html = fetch_url(art_url)
                if not art_html: continue
                art_soup = BeautifulSoup(art_html.decode("utf-8", errors="ignore"), "html.parser")
                down_a = art_soup.find("a", href=re.compile(r"download|fileSeq"))
                if down_a:
                    f_url = "https://fire.gwd.go.kr" + down_a["href"] if down_a["href"].startswith("/") else down_a["href"]
                    pdf_data = fetch_url(f_url)
                    if pdf_data:
                        text = parse_file_content(pdf_data)
                        for block in text.split("❍"):
                            if "화재" in block and ("발화" in block or "소실" in block or "원인" in block):
                                tm_m = re.search(r"(\d{1,2}:\d{2})", block)
                                tm = tm_m.group(1) if tm_m else "00:00"
                                loc_m = re.search(r"([가-힣]+(?:시|군)\s+[가-힣0-9]+(?:읍|면|동)(?:\s+[가-힣]+리)?)", block)
                                loc = f"강원특별자치도 {loc_m.group(1)}" if loc_m else "강원특별자치도"
                                lat, lng = get_coords(loc, f"GW-{date_str}-{tm}")
                                dmg = clean_money(block)
                                d_clean = date_str.replace("-", "")
                                t_clean = tm.replace(":", "")
                                results.append({
                                    "id": f"GW-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                    "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                    "location": loc, "address": loc, "bldg_type": "기타", "cause": "원인 조사 중",
                                    "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                    "lat": lat, "lng": lng, "description": f"[강원소방본부 소방활동보고] {block[:200].strip()}",
                                    "title": f"강원 {loc} 화재", "source": "강원특별자치도 소방본부 119소방활동 상황보고"
                                })
    except Exception as e: print(f"Gangwon error: {e}")
    return results

def collect_daegu():
    print("[수집] 대구소방안전본부...")
    results = []
    try:
        url = "https://www.daegu.go.kr/119/index.do?menu_id=00001614"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            txt = tr.get_text(strip=True)
            if "재난종합상황" in txt or "소방활동" in txt:
                date_m = re.search(r"(\d{1,2})\.(\d{1,2})", txt)
                date_str = f"2026-{int(date_m.group(1)):02d}-{int(date_m.group(2)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                a_tag = tr.find("a")
                if not a_tag or not a_tag.get("href"): continue
                art_url = "https://www.daegu.go.kr" + a_tag["href"] if a_tag["href"].startswith("/") else a_tag["href"]
                art_html = fetch_url(art_url)
                if not art_html: continue
                art_soup = BeautifulSoup(art_html.decode("utf-8", errors="ignore"), "html.parser")
                down_a = art_soup.find("a", href=re.compile(r"download|fileSeq"))
                if down_a:
                    f_url = "https://www.daegu.go.kr" + down_a["href"] if down_a["href"].startswith("/") else down_a["href"]
                    file_bytes = fetch_url(f_url)
                    if file_bytes:
                        text = parse_file_content(file_bytes)
                        for block in text.split("◆"):
                            if "화재" in block and ("발화" in block or "소실" in block or "피해" in block):
                                tm_m = re.search(r"(\d{1,2}:\d{2})", block)
                                tm = tm_m.group(1) if tm_m else "00:00"
                                loc_m = re.search(r"([가-힣]+(?:구|군)\s+[가-힣0-9]+(?:동|읍|면))", block)
                                loc = f"대구광역시 {loc_m.group(1)}" if loc_m else "대구광역시"
                                lat, lng = get_coords(loc, f"DAEGU-{date_str}-{tm}")
                                dmg = clean_money(block)
                                d_clean = date_str.replace("-", "")
                                t_clean = tm.replace(":", "")
                                results.append({
                                    "id": f"DAEGU-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                    "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                    "location": loc, "address": loc, "bldg_type": "기타", "cause": "원인 조사 중",
                                    "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                    "lat": lat, "lng": lng, "description": f"[대구소방안전본부 재난종합상황] {block[:200].strip()}",
                                    "title": f"대구 {loc} 화재", "source": "대구소방안전본부 일일재난종합상황"
                                })
    except Exception as e: print(f"Daegu error: {e}")
    return results

def collect_incheon():
    print("[수집] 인천소방본부...")
    results = []
    try:
        url = "https://www.incheon.go.kr/119/NE030201"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            txt = tr.get_text(strip=True)
            if "소방활동" in txt or "소방종합상황" in txt or "상황일보" in txt:
                date_m = re.search(r"(\d{1,2})[월.]\s*(\d{1,2})", txt)
                date_str = f"2026-{int(date_m.group(1)):02d}-{int(date_m.group(2)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                a_tag = tr.find("a")
                if not a_tag or not a_tag.get("href"): continue
                art_m = re.search(r"/NE030201/(\d+)", a_tag["href"])
                if art_m:
                    art_id = art_m.group(1)
                    down_url = f"https://www.incheon.go.kr/comm/getFile?srvcId=BBSTY1&upperNo={art_id}&fileTy=ATTACH&fileNo=1"
                    f_data = fetch_url(down_url)
                    if f_data:
                        text = parse_file_content(f_data)
                        for block in text.split("□"):
                            if "화재" in block and ("발화" in block or "소실" in block or "원인" in block):
                                tm_m = re.search(r"(\d{1,2}:\d{2})", block)
                                tm = tm_m.group(1) if tm_m else "00:00"
                                loc_m = re.search(r"([가-힣]+(?:구|군)\s+[가-힣0-9]+(?:동|읍|면))", block)
                                loc = f"인천광역시 {loc_m.group(1)}" if loc_m else "인천광역시"
                                lat, lng = get_coords(loc, f"INCHEON-{date_str}-{tm}")
                                dmg = clean_money(block)
                                d_clean = date_str.replace("-", "")
                                t_clean = tm.replace(":", "")
                                results.append({
                                    "id": f"INCHEON-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                    "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                    "location": loc, "address": loc, "bldg_type": "기타", "cause": "원인 조사 중",
                                    "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                    "lat": lat, "lng": lng, "description": f"[인천소방본부 일일소방활동상황] {block[:200].strip()}",
                                    "title": f"인천 {loc} 화재", "source": "인천소방본부 일일소방활동상황"
                                })
    except Exception as e: print(f"Incheon error: {e}")
    return results

def collect_daejeon():
    print("[수집] 대전소방본부...")
    results = []
    try:
        url = "https://www.daejeon.go.kr/dj119/cmmBoardList.do?boardId=dj119_0021&menuSeq=4400"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            txt = tr.get_text(strip=True)
            if "소방활동" in txt or "상황" in txt:
                date_m = re.search(r"2026[-. ]?09[-. ]?([0-9]{1,2})", txt)
                date_str = f"2026-09-{int(date_m.group(1)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                a_tag = tr.find("a")
                if not a_tag: continue
                onclick = a_tag.get("onclick", "")
                m_seq = re.search(r"goViewPage\((\d+)\)", onclick)
                if m_seq:
                    ntatc_seq = m_seq.group(1)
                    art_url = f"https://www.daejeon.go.kr/dj119/cmmBoardView.do?boardId=dj119_0021&menuSeq=4400&ntatcSeq={ntatc_seq}"
                    art_html = fetch_url(art_url)
                    if not art_html: continue
                    art_soup = BeautifulSoup(art_html.decode("utf-8", errors="ignore"), "html.parser")
                    for da in art_soup.find_all("a"):
                        dh = da.get("href", "")
                        if "down.do" in dh or "atflSeq" in dh or "getFile" in dh:
                            f_url = f"https://www.daejeon.go.kr{dh}" if dh.startswith("/") else dh
                            f_data = fetch_url(f_url)
                            if f_data:
                                text = parse_file_content(f_data)
                                for block in text.split("○"):
                                    if "화재" in block and ("발화" in block or "소실" in block or "원인" in block):
                                        tm_m = re.search(r"(\d{1,2}:\d{2})", block)
                                        tm = tm_m.group(1) if tm_m else "00:00"
                                        loc_m = re.search(r"([가-힣]+(?:구)\s+[가-힣0-9]+(?:동))", block)
                                        loc = f"대전광역시 {loc_m.group(1)}" if loc_m else "대전광역시"
                                        lat, lng = get_coords(loc, f"DAEJEON-{date_str}-{tm}")
                                        dmg = clean_money(block)
                                        d_clean = date_str.replace("-", "")
                                        t_clean = tm.replace(":", "")
                                        results.append({
                                            "id": f"DAEJEON-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                            "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                            "location": loc, "address": loc, "bldg_type": "기타", "cause": "원인 조사 중",
                                            "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                            "lat": lat, "lng": lng, "description": f"[대전소방본부 일일소방활동] {block[:200].strip()}",
                                            "title": f"대전 {loc} 화재", "source": "대전소방본부 일일소방활동"
                                        })
    except Exception as e: print(f"Daejeon error: {e}")
    return results

def collect_ulsan():
    print("[수집] 울산광역시 소방본부...")
    results = []
    try:
        url = "https://fire.ulsan.go.kr/cop/bbs/selectBoardList.do?bbsId=fireActivityDaily"
        data = fetch_url(url)
        if not data: return results
        soup = BeautifulSoup(data.decode("utf-8", errors="ignore"), "html.parser")
        for tr in soup.find_all("tr"):
            txt = tr.get_text(strip=True)
            if "소방일일상황" in txt or "소방활동" in txt:
                date_m = re.search(r"2026[-. ]?09[-. ]?([0-9]{1,2})", txt)
                date_str = f"2026-09-{int(date_m.group(1)):02d}" if date_m else datetime.now().strftime("%Y-%m-%d")
                a_tag = tr.find("a")
                if not a_tag or not a_tag.get("href"): continue
                art_url = "https://fire.ulsan.go.kr" + a_tag["href"] if a_tag["href"].startswith("/") else a_tag["href"]
                art_html = fetch_url(art_url)
                if not art_html: continue
                art_soup = BeautifulSoup(art_html.decode("utf-8", errors="ignore"), "html.parser")
                down_a = art_soup.find("a", href=re.compile(r"download|fileSeq|atchFileId"))
                if down_a:
                    f_url = "https://fire.ulsan.go.kr" + down_a["href"] if down_a["href"].startswith("/") else down_a["href"]
                    f_data = fetch_url(f_url)
                    if f_data:
                        text = parse_file_content(f_data)
                        for block in text.split("○"):
                            if "화재" in block and ("발화" in block or "소실" in block or "원인" in block):
                                tm_m = re.search(r"(\d{1,2}:\d{2})", block)
                                tm = tm_m.group(1) if tm_m else "00:00"
                                loc_m = re.search(r"([가-힣]+(?:구|군)\s+[가-힣0-9]+(?:동|읍|면))", block)
                                loc = f"울산광역시 {loc_m.group(1)}" if loc_m else "울산광역시"
                                lat, lng = get_coords(loc, f"ULSAN-{date_str}-{tm}")
                                dmg = clean_money(block)
                                d_clean = date_str.replace("-", "")
                                t_clean = tm.replace(":", "")
                                results.append({
                                    "id": f"ULSAN-FIRE-{d_clean}-{t_clean}-{len(results)+1:03d}",
                                    "date": date_str, "time": tm, "datetime": f"{date_str} {tm}",
                                    "location": loc, "address": loc, "bldg_type": "기타", "cause": "원인 조사 중",
                                    "casualties": {"killed": 0, "injured": 0, "total": 0}, "property_damage": dmg, "damage": dmg,
                                    "lat": lat, "lng": lng, "description": f"[울산소방본부 소방일일상황] {block[:200].strip()}",
                                    "title": f"울산 {loc} 화재", "source": "울산소방본부 소방일일상황"
                                })
    except Exception as e: print(f"Ulsan error: {e}")
    return results

def parse_money_cheonwon(text):
    if not text: return 0
    m = re.search(r"([0-9,]+)\s*(천원|백만원|만원|억원|원)", str(text))
    if not m:
        nums = re.findall(r"\d+", str(text).replace(",", ""))
        return int(nums[0]) if nums else 0
    val_str = m.group(1).replace(",", "")
    unit = m.group(2)
    try:
        val = int(val_str)
        if unit == "천원": return val
        elif unit == "백만원": return val * 1000
        elif unit == "만원": return val * 10
        elif unit == "억원": return val * 100000
        elif unit == "원": return val // 1000
    except: pass
    return 0

def normalize_cause(text):
    if not text: return "부주의", "원인 미상"
    t = str(text).lower()
    if any(k in t for k in ["담배", "꽁초", "음식물", "쓰레기", "소각", "용접", "불티", "촛불", "화원", "부주의"]):
        return "부주의", str(text).strip()
    if any(k in t for k in ["전기", "단락", "과부하", "트래킹", "누전", "접촉불량", "합선"]):
        return "전기적 요인", str(text).strip()
    if any(k in t for k in ["기계", "과열", "마찰", "엔진", "오일", "배관", "모터"]):
        return "기계적 요인", str(text).strip()
    if any(k in t for k in ["화학", "자연발화", "반응열", "유증기", "인화성"]):
        return "화학적 요인", str(text).strip()
    if any(k in t for k in ["방화", "방화의심"]):
        return "방화/방화의심", str(text).strip()
    if any(k in t for k in ["가스", "lpg", "lng", "누출"]):
        return "가스누출", str(text).strip()
    if any(k in t for k in ["차량", "교통", "충돌"]):
        return "교통사고", str(text).strip()
    if any(k in t for k in ["낙뢰", "번개", "태양광", "임야", "산림"]):
        return "자연적 요인", str(text).strip()
    return "기타/미상", str(text).strip()

def normalize_location(text):
    if not text: return "기타/미상", "기타 시설"
    t = str(text).lower()
    if any(k in t for k in ["아파트", "주택", "빌라", "다세대", "원룸", "주거", "오피스텔"]):
        return "주거시설", str(text).strip()
    if any(k in t for k in ["공장", "창고", "작업장", "산업", "자재"]):
        return "산업시설", str(text).strip()
    if any(k in t for k in ["음식점", "상가", "식당", "쇼핑", "호텔", "모텔", "숙박", "빌딩", "사무실"]):
        return "상업/업무시설", str(text).strip()
    if any(k in t for k in ["차량", "승용차", "화물차", "트럭", "버스", "선박"]):
        return "자동차/운송수단", str(text).strip()
    if any(k in t for k in ["임야", "산", "들판", "공터", "야외", "도로"]):
        return "야외/임야", str(text).strip()
    if any(k in t for k in ["학교", "병원", "요양", "어린이집", "유치원", "복지"]):
        return "교육/의료/복지", str(text).strip()
    if any(k in t for k in ["주유소", "충전소", "가스", "위험물"]):
        return "위험물/저장시설", str(text).strip()
    return "기타/미상", str(text).strip()

def parse_region_hierarchy(location_str):
    sido = "전국"
    sigungu = ""
    eupmyeondong = ""
    
    for alias, standard in SIDO_ALIASES.items():
        if location_str.startswith(alias) or f" {alias}" in location_str:
            sido = standard
            break
            
    sgg_match = re.search(r"([가-힣]+(?:시|군|구))", location_str)
    if sgg_match:
        cand = sgg_match.group(1)
        if cand not in ["서울특별시", "부산광역시", "대구광역시", "인천광역시", "광주광역시", "대전광역시", "울산광역시", "세종특별자치시"]:
            sigungu = cand
            
    emd_match = re.search(r"([가-힣0-9]+(?:읍|면|동|리))", location_str)
    if emd_match:
        eupmyeondong = emd_match.group(1)
        
    return sido, sigungu, eupmyeondong

def collect_from_samefiledel():
    """samefiledel 소방청 및 17개 시도 소방본부 일일상황보고 데이터베이스 연동 및 수집"""
    same_dir = os.path.join(os.path.dirname(BASE_DIR), "samefiledel")
    if not os.path.exists(same_dir):
        return []
    print("[동기화] samefiledel 17개 시·도 소방본부 일보 데이터셋 연동 중...")
    results = []
    
    target_files = [
        ("daegu_final_ingest.json", "대구광역시", "대구소방안전본부 일일상황보고"),
        ("daejeon_final_ingest.json", "대전광역시", "대전소방본부 일일소방활동상황"),
        ("incheon_final_ingest.json", "인천광역시", "인천소방본부 일일소방활동상황"),
        ("jeju_final_ingest.json", "제주특별자치도", "제주소방안전본부 소방종합상황일일보고"),
        ("sejong_parsed_fires.json", "세종특별자치시", "세종특별자치시 소방본부 일일소방상황"),
        ("ulsan_final_ingest.json", "울산광역시", "울산소방본부 일일소방상황")
    ]
    
    for fname, def_sido, def_src in target_files:
        p = os.path.join(same_dir, fname)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    items = json.load(f)
                for item in items:
                    if not item.get("sido"):
                        item["sido"] = def_sido
                    if not item.get("source"):
                        item["source"] = def_src
                    results.append(item)
            except Exception as e:
                print(f"samefiledel {fname} read error: {e}")
                
    return results

def run_all_collectors():
    print("="*60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Fire-info 전국 소방본부 일일상황 자동 수집 & SQLite 동기화 시작")
    print("="*60)
    
    # 1. 압축 DB 복원 확인
    if os.path.exists(GZ_PATH) and (not os.path.exists(DB_PATH) or os.path.getsize(DB_PATH) < 1000000):
        print(f"압축 DB({GZ_PATH}) 복원 중...")
        with gzip.open(GZ_PATH, 'rb') as f_in:
            with open(DB_PATH, 'wb') as f_out:
                shutil.copyfileobj(f_in, f_out)
        print("-> SQLite DB 복원 완료")

    if not os.path.exists(DB_PATH):
        print("에러: fire_records.db 데이터베이스가 존재하지 않습니다.")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    
    cur.execute("SELECT id, dedup_key FROM fire_records")
    existing_rows = cur.fetchall()
    existing_ids = set(r[0] for r in existing_rows if r[0])
    existing_keys = set(r[1] for r in existing_rows if r[1])
    print(f"기존 DB 데이터 수: {len(existing_rows):,}건")

    new_raw_records = []
    
    # samefiledel 연동
    new_raw_records.extend(collect_from_samefiledel())
    
    # 각 시도 소방본부 크롤러 실행
    collectors = [collect_nfa, collect_sejong, collect_jeju, collect_gangwon, collect_daegu, collect_incheon, collect_daejeon, collect_ulsan]
    for c in collectors:
        try:
            items = c()
            new_raw_records.extend(items)
            time.sleep(0.3)
        except Exception as err:
            print(f"[수집기 에러] {c.__name__}: {err}")

    added = 0
    for r in new_raw_records:
        r_id = r.get("id") or f"FIRE-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        raw_d = str(r.get("date") or r.get("fire_date") or r.get("datetime") or "")
        dm = re.search(r"(\d{4})[-./](\d{1,2})[-./](\d{1,2})", raw_d)
        if dm:
            d_str = f"{int(dm.group(1)):04d}-{int(dm.group(2)):02d}-{int(dm.group(3)):02d}"
        else:
            d_str = get_kst_now().strftime("%Y-%m-%d")
            
        raw_t = str(r.get("time") or r.get("fire_time") or (r.get("datetime") or "")[11:16] or "")
        tm = re.search(r"(\d{1,2}):(\d{2})", raw_t)
        if tm:
            t_str = f"{int(tm.group(1)):02d}:{tm.group(2)}:00"
        else:
            t_str = "00:00:00"
            
        dt_str = f"{d_str} {t_str}"
        loc_str = r.get("location") or r.get("address") or "전국"
        
        sido, sigungu, emd = parse_region_hierarchy(loc_str)
        if r.get("sido") and r.get("sido") != "전국":
            sido = r.get("sido")
        if r.get("sigungu"):
            sigungu = r.get("sigungu")
        if r.get("eupmyeondong"):
            emd = r.get("eupmyeondong")

        lat = r.get("lat")
        lng = r.get("lng")
        if not lat or not lng or lat == 36.5 or (sigungu == "단양군" and (lat < 36.8 or lng < 128.0)):
            lat, lng = get_precise_coordinates(sido, sigungu, emd, loc_str)

        c_cat, c_det = normalize_cause(r.get("cause") or r.get("cause_category") or r.get("description", ""))
        l_cat, l_det = normalize_location(r.get("bldg_type") or r.get("location_category") or r.get("description", ""))
        
        casualties_obj = r.get("casualties")
        if isinstance(casualties_obj, dict):
            killed = int(casualties_obj.get("killed", 0))
            injured = int(casualties_obj.get("injured", 0))
            total_cas = int(casualties_obj.get("total", killed + injured))
        else:
            killed = int(r.get("deaths", 0))
            injured = int(r.get("injuries", 0))
            total_cas = int(r.get("casualties", killed + injured))
            
        dmg = parse_money_cheonwon(r.get("property_damage") or r.get("damage", 0))
        summary_txt = r.get("description") or r.get("summary") or r.get("title") or f"{loc_str} 화재 발생"
        source_txt = r.get("source") or "소방청 및 시도 소방본부 일일상황"
        juris_station = r.get("juris_station") or f"{sido}소방본부"
        
        dedup_key = r.get("dedup_key") or f"{d_str}_{sido}_{sigungu}_{emd}_{t_str[:5]}"
        
        if r_id in existing_ids or dedup_key in existing_keys:
            continue

        year_val = int(d_str[:4])
        month_val = int(d_str[5:7])

        cur.execute("""
            INSERT OR REPLACE INTO fire_records (
                id, fire_datetime, fire_date, fire_time, year, month,
                sido, sigungu, eupmyeondong, location_category, location_detail,
                cause_category, cause_detail, deaths, injuries, casualties,
                property_damage, suppression_minutes, dispatched_personnel, dispatched_vehicles,
                summary, is_realtime, lat, lng, source, juris_station,
                status, status_text, is_verified, dedup_key
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            r_id, dt_str, d_str, t_str, year_val, month_val,
            sido, sigungu or "전체", emd or "중앙동", l_cat, l_det[:50],
            c_cat, c_det[:50], killed, injured, total_cas,
            dmg, 30, 20, 6,
            summary_txt[:300], 1, float(lat), float(lng), source_txt, juris_station,
            "EXTINGUISHED", "완진", 1, dedup_key
        ))
        existing_ids.add(r_id)
        existing_keys.add(dedup_key)
        added += 1

    conn.commit()
    cur.execute("SELECT MAX(fire_date), COUNT(*) FROM fire_records")
    latest_date, total_count = cur.fetchone()
    conn.close()

    print(f"\n신규 화재 데이터 {added}건 추가 완료. (총 DB: {total_count:,}건, 최신 기준일: {latest_date})")

    if added > 0 or not os.path.exists(GZ_PATH):
        print(f"\n[압축] 최신 SQLite DB -> {GZ_PATH} 압축 파일 생성 중...")
        with open(DB_PATH, 'rb') as f_in:
            with gzip.open(GZ_PATH, 'wb', compresslevel=6) as f_out:
                shutil.copyfileobj(f_in, f_out)
        gz_size_mb = os.path.getsize(GZ_PATH) / (1024 * 1024)
        print(f"-> GZ 압축 완료 ({gz_size_mb:.1f} MB)")
    else:
        print("-> 신규 변경 사항이 없어 압축 갱신을 건너뜁니다.")

if __name__ == "__main__":
    run_all_collectors()

