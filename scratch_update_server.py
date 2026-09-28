import re

with open('webapp/server.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Add Query to fastapi imports
if 'from fastapi import' in text and 'Query' not in text:
    text = text.replace('from fastapi import', 'from fastapi import Query,')

# Function 1: get_status
text = re.sub(
    r'(async def get_status\(current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def get_status(current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('data = await GeneratorService.get_dashboard_data(session)', 'data = await GeneratorService.get_dashboard_data(session, gen_id)')

# Function 2: start_generator
text = re.sub(
    r'(async def start_generator\(req: StartRequest, current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def start_generator(req: StartRequest, current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('success, msg, _ = await GeneratorService.start_generator(session, current_user["user_id"], current_user["user_name"])', 'success, msg, _ = await GeneratorService.start_generator(session, current_user["user_id"], current_user["user_name"], gen_id=gen_id)')

# Function 3: stop_generator
text = re.sub(
    r'(async def stop_generator\(req: StopRequest, current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def stop_generator(req: StopRequest, current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('success, msg, _ = await GeneratorService.stop_generator(', 'success, msg, _ = await GeneratorService.stop_generator(\n            gen_id=gen_id,')

# Function 4: refuel
text = re.sub(
    r'(async def add_fuel\(req: RefuelRequest, current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def add_fuel(req: RefuelRequest, current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('success, msg, _ = await GeneratorService.add_fuel(', 'success, msg, _ = await GeneratorService.add_fuel(\n            gen_id=gen_id,')

# Function 5: maint
text = re.sub(
    r'(async def perform_maintenance\(req: MaintenanceRequest, current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def perform_maintenance(req: MaintenanceRequest, current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('success, msg, _ = await GeneratorService.perform_maintenance(', 'success, msg, _ = await GeneratorService.perform_maintenance(\n            gen_id=gen_id,')

# Function 6: reset
text = re.sub(
    r'(async def reset_counters\(req: ResetRequest, current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def reset_counters(req: ResetRequest, current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('success, msg, _ = await GeneratorService.reset_counters(', 'success, msg, _ = await GeneratorService.reset_counters(\n            gen_id=gen_id,')

# Function 7: update settings
text = re.sub(
    r'(async def update_admin_settings\(req: AdminSettingsRequest, current_user: Dict\[str, Any\] = Depends\(get_current_user\)\):)',
    r'async def update_admin_settings(req: AdminSettingsRequest, current_user: Dict[str, Any] = Depends(get_current_user), gen_id: int = Query(1)):',
    text
)
text = text.replace('gen = await GeneratorService.calibrate_counters(', 'gen = await GeneratorService.calibrate_counters(\n            gen_id=gen_id,')

with open('webapp/server.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("server.py Updated!")
