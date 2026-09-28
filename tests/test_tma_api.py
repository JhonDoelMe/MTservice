import sys
import os

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root
sys.path.insert(0, os.path.abspath("."))

from bot.config import settings

# Use local test database
test_db_file = "data/test_tma.db"
if os.path.exists(test_db_file):
    os.remove(test_db_file)

settings.DATABASE_URL = f"sqlite+aiosqlite:///{test_db_file}"

import asyncio
from bot.database.db import init_db
from bot.database.cache import cache
from webapp.server import app
from fastapi.testclient import TestClient


def run_tests():
    print("1. Initializing DB and Cache...")
    asyncio.run(init_db())
    print("DB & Cache initialized.")

    client = TestClient(app)

    print("\n2. Testing HTML Mini App rendering (/)...")
    res = client.get("/")
    assert res.status_code == 200
    assert "Диспетчер генератора" in res.text
    assert "telegram-web-app.js" in res.text
    print("HTML served correctly with Telegram WebApp SDK.")

    print("\n3. Testing GET /api/status...")
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    print(f"Name: {data['name']}, Running: {data['is_running']}, Currency: {data['currency']}, Timezone: {data['timezone']}")
    assert data["currency"] == "₴"
    assert data["timezone"] == "Europe/Kyiv"
    assert not data["is_running"]

    print("\n4. Testing POST /api/generator/start...")
    res = client.post("/api/generator/start", json={"custom_time": "-15"})
    assert res.status_code == 200
    data = res.json()
    print("Start response:", data["message"])
    assert data["status"] == "ok"

    print("\n5. Testing GET /api/status while running...")
    res = client.get("/api/status")
    data = res.json()
    print(f"Status is_running: {data['is_running']}, current_run_hours: {data['current_run_hours']}")
    assert data["is_running"] is True

    print("\n6. Testing POST /api/fuel/add...")
    res = client.post("/api/fuel/add", json={"amount_liters": 50.0, "cost": 2750.0, "notes": "АЗС ОККО"})
    assert res.status_code == 200
    data = res.json()
    print("Refuel response:", data["message"])
    assert data["status"] == "ok"

    print("\n7. Testing POST /api/generator/stop...")
    res = client.post("/api/generator/stop", json={"notes": "Мережа стабільна"})
    assert res.status_code == 200
    data = res.json()
    print("Stop response:", data["message"])
    assert data["status"] == "ok"

    print("\n8. Testing POST /api/maintenance/perform...")
    res = client.post("/api/maintenance/perform", json={"description": "Заміна моторної оливи та фільтрів", "cost": 3400.0})
    assert res.status_code == 200
    data = res.json()
    print("Maint response:", data["message"])
    assert data["status"] == "ok"

    print("\n9. Testing GET /api/reports/summary & runs...")
    res = client.get("/api/reports/summary")
    assert res.status_code == 200
    sum_data = res.json()
    print(f"Today runs: {sum_data['today_runs_count']}, Today fuel: {sum_data['today_fuel']} L")
    assert sum_data["today_runs_count"] >= 1

    res_runs = client.get("/api/reports/runs")
    assert res_runs.status_code == 200
    runs = res_runs.json()
    print(f"Recorded runs count: {len(runs)}")
    assert len(runs) >= 1

    print("\n10. Testing GET /api/reports/excel (Streaming XLSX)...")
    res_excel = client.get("/api/reports/excel")
    assert res_excel.status_code == 200
    assert len(res_excel.content) > 2000
    assert "spreadsheetml" in res_excel.headers.get("content-type", "")
    print(f"Excel report streamed successfully: {len(res_excel.content)} bytes.")

    print("\nALL TELEGRAM MINI APP TESTS PASSED PERFECTLY! 🚀")


if __name__ == "__main__":
    run_tests()
