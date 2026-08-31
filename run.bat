@echo off
chcp 65001 > nul
echo ========================================================
echo  소방청 10개년 화재발생 상세정보 검색 및 정렬 대시보드
echo ========================================================
echo.
echo [1/2] 필수 라이브러리 확인 및 설치...
python -m pip install -r requirements.txt
echo.
echo [2/2] 대시보드 서버 실행 중... (웹 브라우저가 자동으로 열립니다)
python run.py
pause
