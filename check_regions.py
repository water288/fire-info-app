import asyncio
import httpx
import sys

# Windows 콘솔 utf-8 설정
sys.stdout.reconfigure(encoding='utf-8')

async def check_all_regions():
    base_url = "http://127.0.0.1:8080"
    async with httpx.AsyncClient(timeout=10.0) as client:
        meta_res = await client.get(f"{base_url}/api/meta")
        meta = meta_res.json()
        regions = meta["regions"]

        print("=" * 85)
        print(" [전국 17개 시·도 및 주요 시·군·구 10개년(2016~2025) 화재 통계 전수 점검 결과]")
        print("=" * 85)

        total_sum = 0
        for sido, sgg_list in regions.items():
            sido_res = (await client.get(f"{base_url}/api/stats?sido={sido}")).json()
            fires = sido_res["total_fires"]
            deaths = sido_res["total_deaths"]
            injuries = sido_res["total_injuries"]
            damage_won = sido_res["total_property_damage_cheonwon"] * 1000
            damage_eok = damage_won // 100000000
            total_sum += fires

            # 주요 시군구 샘플링
            sample_sggs = sgg_list[:4] if len(sgg_list) >= 4 else sgg_list
            sgg_details = []
            for sgg in sample_sggs:
                sgg_res = (await client.get(f"{base_url}/api/stats?sido={sido}&sigungu={sgg}")).json()
                sgg_details.append(f"{sgg} {sgg_res['total_fires']}건")

            sgg_str = ", ".join(sgg_details)
            print(f"· {sido:<10} : 총 {fires:>5}건 | 사망 {deaths:>3}명 | 부상 {injuries:>4}명 | 피해액 {damage_eok:>5}억원")
            print(f"   ↳ 주요 시군구: {sgg_str}")

        print("=" * 85)
        print(f">> 전국 17개 시·도 총합 건수: {total_sum:,}건")

if __name__ == "__main__":
    asyncio.run(check_all_regions())
