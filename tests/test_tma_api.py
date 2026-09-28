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
    asyncio.run(cache.clear_pattern("generator:*"))
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
    print(f"Status is_running: {data['is_running']}, current_run_hours: {data['current_run_hours']}, session_fuel: {data['session_fuel_burned']}")
    assert data["is_running"] is True
    assert "session_fuel_burned" in data
    assert "today_fuel_burned" in data

    print("\n6. Testing POST /api/fuel/add...")
    res = client.post("/api/fuel/add", json={"amount_liters": 50.0, "cost": 2750.0, "notes": "АЗС ОККО"})
    assert res.status_code == 200
    data = res.json()
    print("Refuel response:", data["message"])
    assert data["status"] == "ok"

    # Check that last_refuel is populated in status
    res = client.get("/api/status")
    data = res.json()
    print("Last refuel in status:", data["last_refuel"])
    assert data["last_refuel"] is not None
    assert data["last_refuel"]["amount_liters"] == 50.0
    assert data["last_refuel"]["cost"] == 2750.0

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

    print("\n11. Testing POST /api/maintenance/perform (Intermediate Maintenance)...")
    res_inter = client.post("/api/maintenance/perform", json={
        "description": "Заміна свічок запалювання NGK",
        "is_main": False,
        "maint_type": "spark_plugs",
        "cost": 650.0
    })
    assert res_inter.status_code == 200
    print("Intermediate maint response:", res_inter.json()["message"])
    status_inter = client.get("/api/status").json()
    print(f"Spark plugs hours ago: {status_inter['spark_plugs_hours_ago']}")
    assert status_inter["spark_plugs_hours_ago"] == 0.0

    print("\n12. Testing POST /api/users/custom-name...")
    res_name = client.post("/api/users/custom-name", json={
        "user_id": 100000001,
        "custom_name": "Іван Петренко (Старший електрик)"
    })
    assert res_name.status_code == 200
    users = client.get("/api/users").json()
    admin_u = next(u for u in users if u["user_id"] == 100000001)
    print(f"User custom_name: {admin_u['custom_name']}, display_name: {admin_u['display_name']}")
    assert admin_u["custom_name"] == "Іван Петренко (Старший електрик)"
    assert admin_u["display_name"] == "Іван Петренко (Старший електрик)"

    print("\n13. Testing POST /api/admin/reset & Audit Log...")
    res_reset = client.post("/api/admin/reset", json={
        "reset_type": "fuel_zero",
        "reason": "Калібрування бака після очищення"
    })
    assert res_reset.status_code == 200
    status_reset = client.get("/api/status").json()
    print(f"Current fuel after reset: {status_reset['current_fuel']} L")
    assert status_reset["current_fuel"] == 0.0

    audit_logs = client.get("/api/reports/audit").json()
    print(f"Audit logs count: {len(audit_logs)}, latest: {audit_logs[0]}")
    assert len(audit_logs) >= 1
    assert audit_logs[0]["reset_type"] == "fuel_zero"
    assert "Калібрування" in audit_logs[0]["reason"]

    print("\n14. Testing mandatory reason check on reset...")
    res_invalid_reset = client.post("/api/admin/reset", json={
        "reset_type": "hours_zero",
        "reason": " "
    })
    assert res_invalid_reset.status_code == 400
    print("Invalid reset caught successfully:", res_invalid_reset.json()["detail"])

    print("\n15. Testing Working Hours schedule structure in status...")
    status_wh = client.get("/api/status").json()
    assert "work_hours" in status_wh
    print(f"Work hours: {status_wh['work_hours']}")
    assert status_wh["work_hours"]["start"] == "08:00"
    assert status_wh["work_hours"]["end"] == "20:00"

    print("\n16. Testing Admin Recognition & Auto-promotion from Pending...")
    import hmac
    import hashlib
    import json
    import urllib.parse

    test_bot_token = "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11"
    settings.BOT_TOKEN = test_bot_token

    def make_tg_init_data(user_dict: dict) -> str:
        user_json = json.dumps(user_dict, separators=(",", ":"))
        params = {
            "auth_date": "1710000000",
            "query_id": "AAHdF6IQAAAAAN0XohDhrPwt",
            "user": user_json
        }
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
        secret_key = hmac.new(b"WebAppData", test_bot_token.encode("utf-8"), hashlib.sha256).digest()
        hash_val = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        params["hash"] = hash_val
        return urllib.parse.urlencode(params)

    # 1. Non-admin user gets created as pending and blocked with 403
    test_user_id = 888777666
    user_header = {"X-Telegram-Init-Data": make_tg_init_data({"id": test_user_id, "first_name": "Новий", "username": "new_worker"})}
    res_pending = client.get("/api/status", headers=user_header)
    assert res_pending.status_code == 403
    print("Pending user correctly blocked with 403:", res_pending.json()["detail"])

    # 2. User ID is now added to ADMIN_IDS in .env (as int or str with quotes)
    settings.ADMIN_IDS = [100000001, test_user_id]
    res_promoted = client.get("/api/status", headers=user_header)
    assert res_promoted.status_code == 200
    user_data = res_promoted.json()["current_user"]
    print("Admin successfully recognized & unblocked! Role:", user_data["role"], "is_admin:", user_data["is_admin"])
    assert user_data["is_admin"] is True
    assert user_data["role"] == "admin"

    # 3. Test admin recognized by @username in ADMIN_IDS
    settings.ADMIN_IDS = [100000001, "@super_chief"]
    chief_header = {"X-Telegram-Init-Data": make_tg_init_data({"id": 444333222, "first_name": "Шеф", "username": "super_chief"})}
    res_chief = client.get("/api/status", headers=chief_header)
    assert res_chief.status_code == 200
    chief_data = res_chief.json()["current_user"]
    print("Admin by username successfully recognized! is_admin:", chief_data["is_admin"])
    assert chief_data["is_admin"] is True

    print("\nALL TELEGRAM MINI APP TESTS PASSED PERFECTLY! 🚀")


if __name__ == "__main__":
    run_tests()


