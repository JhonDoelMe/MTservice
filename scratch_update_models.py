import re

with open('bot/database/models.py', 'r', encoding='utf-8') as f:
    text = f.read()

# For RunLog
text = re.sub(
    r'(class RunLog\(Base\):\s*__tablename__ = "run_logs"\s*id: Mapped\[int\] = mapped_column\(Integer, primary_key=True, autoincrement=True\))',
    r'\1\n    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)',
    text
)

# For FuelLog
text = re.sub(
    r'(class FuelLog\(Base\):\s*__tablename__ = "fuel_logs"\s*id: Mapped\[int\] = mapped_column\(Integer, primary_key=True, autoincrement=True\))',
    r'\1\n    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)',
    text
)

# For MaintenanceLog
text = re.sub(
    r'(class MaintenanceLog\(Base\):\s*__tablename__ = "maintenance_logs"\s*id: Mapped\[int\] = mapped_column\(Integer, primary_key=True, autoincrement=True\))',
    r'\1\n    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)',
    text
)

# For AuditResetLog
text = re.sub(
    r'(class AuditResetLog\(Base\):\s*__tablename__ = "audit_reset_logs"\s*id: Mapped\[int\] = mapped_column\(Integer, primary_key=True, autoincrement=True\))',
    r'\1\n    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)',
    text
)

# For InventoryItem
text = re.sub(
    r'(class InventoryItem\(Base\):\s*__tablename__ = \'inventory_items\'\s*id: Mapped\[int\] = mapped_column\(Integer, primary_key=True, autoincrement=True\))',
    r'\1\n    generator_id: Mapped[int] = mapped_column(Integer, ForeignKey("generator_state.id"), default=1)',
    text
)

with open('bot/database/models.py', 'w', encoding='utf-8') as f:
    f.write(text)

print("Updated models!")
