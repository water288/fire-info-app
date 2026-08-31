import uvicorn
import webbrowser
import threading
import time
import socket

def get_local_ip():
    """스마트폰 접속용 로컬 네트워크 IP 탐색"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

def find_available_port(ports=[8080, 8000, 8501, 5000, 8888, 3000]):
    """Windows 포트 충돌 및 예약 포트 방지를 위해 사용 가능한 포트를 자동으로 탐색"""
    for port in ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('0.0.0.0', port))
                return port
        except OSError:
            continue
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', 0))
        return s.getsockname()[1]

def open_browser(port):
    time.sleep(1.2)
    url = f"http://127.0.0.1:{port}"
    print(f">> 웹 브라우저를 엽니다: {url}")
    webbrowser.open(url)

if __name__ == "__main__":
    port = find_available_port([8080, 8000, 8501, 5000, 8888, 3000])
    local_ip = get_local_ip()
    local_url = f"http://127.0.0.1:{port}"
    mobile_url = f"http://{local_ip}:{port}"

    print("=" * 65)
    print(" 🔥 소방청 10개년 화재발생 통계 & 검색 포털 서버 시작")
    print(f" [1] PC 브라우저 접속 주소  : {local_url}")
    print(f" [2] 스마트폰(동일 Wi-Fi) 접속 : {mobile_url}")
    print("=" * 65)

    threading.Thread(target=open_browser, args=(port,), daemon=True).start()
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
