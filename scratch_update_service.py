import re

with open('bot/services/generator_service.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace get_state(session) calls
text = text.replace('gen = await GeneratorService.get_state(session)', 'gen = await GeneratorService.get_state(session, gen_id)')

# Replace start_generator
text = re.sub(
    r'(async def start_generator\(\s*session: AsyncSession,\s*user_id: int,\s*user_name: str\s*\)\s*-> Tuple\[bool, str, Dict\[str, Any\]\]:)',
    r'async def start_generator(session: AsyncSession, user_id: int, user_name: str, gen_id: int = 1) -> Tuple[bool, str, Dict[str, Any]]:',
    text
)

# Replace stop_generator
text = re.sub(
    r'(async def stop_generator\(\s*session: AsyncSession,\s*user_id: int,\s*user_name: str,\s*custom_stop_time: Optional\[datetime\] = None,\s*notes: Optional\[str\] = None\s*\)\s*-> Tuple\[bool, str, Dict\[str, Any\]\]:)',
    r'async def stop_generator(session: AsyncSession, user_id: int, user_name: str, custom_stop_time: Optional[datetime] = None, notes: Optional[str] = None, gen_id: int = 1) -> Tuple[bool, str, Dict[str, Any]]:',
    text
)

# Replace add_fuel
text = re.sub(
    r'(async def add_fuel\(\s*session: AsyncSession,\s*user_id: int,\s*user_name: str,\s*amount: float,\s*cost: Optional\[float\] = None,\s*receipt_number: Optional\[str\] = None,\s*delivered_by: Optional\[str\] = None,\s*notes: Optional\[str\] = None\s*\)\s*-> Tuple\[bool, str, Dict\[str, Any\]\]:)',
    r'async def add_fuel(session: AsyncSession, user_id: int, user_name: str, amount: float, cost: Optional[float] = None, receipt_number: Optional[str] = None, delivered_by: Optional[str] = None, notes: Optional[str] = None, gen_id: int = 1) -> Tuple[bool, str, Dict[str, Any]]:',
    text
)

# Replace perform_maintenance
text = re.sub(
    r'(async def perform_maintenance\(\s*session: AsyncSession,\s*user_id: int,\s*user_name: str,\s*is_main: bool,\s*maint_type: str,\s*title: Optional\[str\] = None,\s*description: str = "",\s*parts_replaced: Optional\[str\] = None,\s*cost: Optional\[float\] = None\s*\)\s*-> Tuple\[bool, str, Dict\[str, Any\]\]:)',
    r'async def perform_maintenance(session: AsyncSession, user_id: int, user_name: str, is_main: bool, maint_type: str, title: Optional[str] = None, description: str = "", parts_replaced: Optional[str] = None, cost: Optional[float] = None, gen_id: int = 1) -> Tuple[bool, str, Dict[str, Any]]:',
    text
)

# Replace reset_counters
text = re.sub(
    r'(async def reset_counters\(\s*session: AsyncSession,\s*user_id: int,\s*user_name: str,\s*reset_type: str,\s*reason: str\s*\)\s*-> Tuple\[bool, str, Dict\[str, Any\]\]:)',
    r'async def reset_counters(session: AsyncSession, user_id: int, user_name: str, reset_type: str, reason: str, gen_id: int = 1) -> Tuple[bool, str, Dict[str, Any]]:',
    text
)

# Replace calibrate_counters
text = re.sub(
    r'(async def calibrate_counters\([\s\S]*?last_maint_hours: Optional\[float\] = None,\n\s*fuel_type: Optional\[str\] = None,\n\s*fuel_price: Optional\[float\] = None,\n\s*auto_update_price: Optional\[bool\] = None,\n\s*\)\s*-> GeneratorState:)',
    r'async def calibrate_counters(\n        session: AsyncSession,\n        user_id: int,\n        user_name: str,\n        total_hours: Optional[float] = None,\n        current_fuel: Optional[float] = None,\n        fuel_rate: Optional[float] = None,\n        tank_capacity: Optional[float] = None,\n        maintenance_interval: Optional[float] = None,\n        last_maint_hours: Optional[float] = None,\n        fuel_type: Optional[str] = None,\n        fuel_price: Optional[float] = None,\n        auto_update_price: Optional[bool] = None,\n        gen_id: int = 1\n    ) -> GeneratorState:',
    text
)

# Update the log object creations with generator_id=gen_id
text = re.sub(r'(RunLog\()', r'\1generator_id=gen_id, ', text)
text = re.sub(r'(FuelLog\()', r'\1generator_id=gen_id, ', text)
text = re.sub(r'(MaintenanceLog\()', r'\1generator_id=gen_id, ', text)
text = re.sub(r'(AuditResetLog\()', r'\1generator_id=gen_id, ', text)

# Update cache deletes
text = text.replace('cache.delete("generator:dashboard")', 'cache.delete(f"generator:{gen_id}:dashboard")')
text = text.replace('cache.set("generator:dashboard"', 'cache.set(f"generator:{gen_id}:dashboard"')

with open('bot/services/generator_service.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("GeneratorService Updated!")
