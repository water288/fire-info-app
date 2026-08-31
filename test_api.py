import asyncio
import httpx

async def test_backend():
    base_url = "http://127.0.0.1:8080"
    async with httpx.AsyncClient(timeout=5.0) as client:
        # 1. 메타데이터 확인
        print("[1] Checking /api/meta...")
        r = await client.get(f"{base_url}/api/meta")
        assert r.status_code == 200, f"Failed meta: {r.status_code}"
        meta = r.json()
        print(f"    - Years: {meta['years'][0]} ~ {meta['years'][-1]}")
        print(f"    - Region count: {len(meta['regions'])}")

        # 2. 10개년 데이터 검색 (기본 정렬: 일시 최신순)
        print("\n[2] Checking /api/fire-data (default sort)...")
        r = await client.get(f"{base_url}/api/fire-data?page=1&page_size=5")
        assert r.status_code == 200
        data = r.json()
        print(f"    - Total fires: {data['total_count']:,} records")
        print(f"    - First item: {data['items'][0]['fire_datetime']} / {data['items'][0]['sido']} / {data['items'][0]['cause_category']}")

        # 3. 사상자 많은순 정렬 테스트
        print("\n[3] Checking /api/fire-data (sort by casualties DESC)...")
        r = await client.get(f"{base_url}/api/fire-data?sort_by=casualties&sort_order=desc&page=1&page_size=3")
        assert r.status_code == 200
        casualties_data = r.json()
        for idx, item in enumerate(casualties_data['items']):
            print(f"    - Top #{idx+1}: 사상자 {item['casualties']}명 (사망 {item['deaths']}, 부상 {item['injuries']}) - {item['fire_datetime']} {item['sido']}")

        # 4. 재산피해액순 정렬 및 필터 테스트 (서울 + 전기적 요인)
        print("\n[4] Checking /api/fire-data with filters (sido=서울특별시, cause=전기적 요인, sort=property_damage)...")
        r = await client.get(f"{base_url}/api/fire-data?sido=서울특별시&cause_category=전기적 요인&sort_by=property_damage&sort_order=desc&page=1&page_size=3")
        assert r.status_code == 200
        damage_data = r.json()
        print(f"    - Filtered count: {damage_data['total_count']} records")
        if damage_data['items']:
            top_dmg = damage_data['items'][0]
            print(f"    - Highest damage in filter: 약 {top_dmg['property_damage']*1000:,}원 ({top_dmg['location_category']})")

        # 5. 통계 집계 API 테스트
        print("\n[5] Checking /api/stats...")
        r = await client.get(f"{base_url}/api/stats")
        assert r.status_code == 200
        stats = r.json()
        print(f"    - Total Fires: {stats['total_fires']:,}")
        print(f"    - Total Deaths: {stats['total_deaths']:,}")
        print(f"    - Total Casualties: {stats['total_casualties']:,}")
        print(f"    - Yearly Trend Count: {len(stats['yearly_trend'])} years")
        print(f"    - Top Cause: {stats['cause_breakdown'][0]['cause']} ({stats['cause_breakdown'][0]['percentage']}%)")

        # 6. CSV 내보내기 테스트
        print("\n[6] Checking /api/export-csv...")
        r = await client.get(f"{base_url}/api/export-csv?sort_by=fire_datetime&page=1")
        assert r.status_code == 200
        assert "attachment; filename=" in r.headers.get("content-disposition", "")
        print(f"    - CSV Content Length: {len(r.content):,} bytes")

        # 7. 프론트엔드 서빙 확인
        print("\n[7] Checking Frontend Root / ...")
        r = await client.get(f"{base_url}/")
        assert r.status_code == 200
        assert "소방청 화재발생 10개년 통계 포털" in r.text
        print("    - HTML Root served successfully!")

    print("\n[SUCCESS] All Backend & Frontend API Tests Passed Successfully!")

if __name__ == "__main__":
    asyncio.run(test_backend())
