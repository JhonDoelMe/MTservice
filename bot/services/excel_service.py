from io import BytesIO
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import FuelLog, GeneratorState, MaintenanceLog, RunLog
from bot.services.generator_service import format_dt, utc_to_local


def apply_header_style(cell):
    cell.font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    cell.fill = PatternFill(start_color="1F4E79", end_color="1F4E79", fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)


def apply_cell_border(cell):
    thin = Side(border_style="thin", color="D9D9D9")
    cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)


class ExcelService:

    @staticmethod
    async def generate_full_report(session: AsyncSession) -> BytesIO:
        wb = Workbook()

        # 1. Summary sheet
        ws_summary = wb.active
        ws_summary.title = "Сводка"
        ws_summary.views.sheetView[0].showGridLines = True

        gen_res = await session.execute(select(GeneratorState).where(GeneratorState.id == 1))
        gen = gen_res.scalar_one_or_none()

        runs_res = await session.execute(select(RunLog).order_by(RunLog.id.desc()))
        runs = runs_res.scalars().all()

        fuel_res = await session.execute(select(FuelLog).order_by(FuelLog.id.desc()))
        refuels = fuel_res.scalars().all()

        maint_res = await session.execute(select(MaintenanceLog).order_by(MaintenanceLog.id.desc()))
        maints = maint_res.scalars().all()

        total_hours_ran = sum(r.duration_hours for r in runs)
        total_fuel_burned = sum(r.fuel_consumed for r in runs)
        total_fuel_added = sum(f.amount_liters for f in refuels)

        # Summary title
        ws_summary.merge_cells("A1:D1")
        title_cell = ws_summary["A1"]
        title_cell.value = f"Отчет по генератору: {gen.name if gen else 'Генератор'}"
        title_cell.font = Font(name="Calibri", size=14, bold=True, color="1F4E79")
        title_cell.alignment = Alignment(horizontal="left", vertical="center")

        ws_summary["A2"] = f"Сформирован: {format_dt(datetime.utcnow())}"
        ws_summary["A2"].font = Font(name="Calibri", size=9, italic=True, color="595959")

        summary_data = [
            ("Текущий статус", "В РАБОТЕ" if (gen and gen.is_running) else "ОСТАНОВЛЕН"),
            ("Текущая наработка (моточасы)", f"{gen.total_hours:.2f} мч" if gen else "0 мч"),
            ("Остаток топлива в баке", f"{gen.current_fuel:.1f} л из {gen.tank_capacity:.1f} л" if gen else "0 л"),
            ("Паспортный расход", f"{gen.fuel_rate:.2f} л/ч" if gen else "—"),
            ("Интервал планового ТО", f"{gen.maintenance_interval_hours:.1f} мч" if gen else "—"),
            ("Наработка при последнем ТО", f"{gen.last_maintenance_hours:.1f} мч" if gen else "—"),
            ("Остаток до следующего ТО", f"{((gen.last_maintenance_hours + gen.maintenance_interval_hours) - gen.total_hours):.2f} мч" if gen else "—"),
            ("Всего зафиксировано запусков", len(runs)),
            ("Суммарное время работы по журналу", f"{total_hours_ran:.2f} ч"),
            ("Суммарный расход топлива", f"{total_fuel_burned:.2f} л"),
            ("Суммарно заправлено", f"{total_fuel_added:.2f} л"),
            ("Количество проведенных ТО", len(maints)),
        ]

        row = 4
        for param, val in summary_data:
            ws_summary.cell(row=row, column=1, value=param).font = Font(name="Calibri", size=11, bold=True)
            ws_summary.cell(row=row, column=2, value=val).font = Font(name="Calibri", size=11)
            apply_cell_border(ws_summary.cell(row=row, column=1))
            apply_cell_border(ws_summary.cell(row=row, column=2))
            row += 1

        # 2. Runs sheet
        ws_runs = wb.create_sheet(title="Журнал запусков")
        ws_runs.views.sheetView[0].showGridLines = True
        run_headers = [
            "№", "Запуск", "Остановка", "Время работы (ч)", "Расход (л)",
            "Норма (л/ч)", "Бак до (л)", "Бак после (л)", "Наработка (мч)",
            "Запустил", "Остановил", "Заметки"
        ]
        for col_idx, header in enumerate(run_headers, start=1):
            cell = ws_runs.cell(row=1, column=col_idx, value=header)
            apply_header_style(cell)

        for row_idx, r in enumerate(runs, start=2):
            ws_runs.cell(row=row_idx, column=1, value=r.id)
            ws_runs.cell(row=row_idx, column=2, value=format_dt(r.start_time))
            ws_runs.cell(row=row_idx, column=3, value=format_dt(r.stop_time))
            ws_runs.cell(row=row_idx, column=4, value=r.duration_hours)
            ws_runs.cell(row=row_idx, column=5, value=r.fuel_consumed)
            ws_runs.cell(row=row_idx, column=6, value=r.fuel_rate)
            ws_runs.cell(row=row_idx, column=7, value=r.start_fuel)
            ws_runs.cell(row=row_idx, column=8, value=r.end_fuel)
            ws_runs.cell(row=row_idx, column=9, value=r.total_hours_after)
            ws_runs.cell(row=row_idx, column=10, value=r.start_user_name or "—")
            ws_runs.cell(row=row_idx, column=11, value=r.stop_user_name or "—")
            ws_runs.cell(row=row_idx, column=12, value=r.notes or "")
            for c in range(1, 13):
                apply_cell_border(ws_runs.cell(row=row_idx, column=c))

        # 3. Refuels sheet
        ws_fuel = wb.create_sheet(title="Заправки")
        ws_fuel.views.sheetView[0].showGridLines = True
        fuel_headers = ["№", "Дата и время", "Заправлено (л)", "Бак до (л)", "Бак после (л)", "Стоимость", "Кто заправил", "Заметки"]
        for col_idx, header in enumerate(fuel_headers, start=1):
            cell = ws_fuel.cell(row=1, column=col_idx, value=header)
            apply_header_style(cell)

        for row_idx, f in enumerate(refuels, start=2):
            ws_fuel.cell(row=row_idx, column=1, value=f.id)
            ws_fuel.cell(row=row_idx, column=2, value=format_dt(f.timestamp))
            ws_fuel.cell(row=row_idx, column=3, value=f.amount_liters)
            ws_fuel.cell(row=row_idx, column=4, value=f.fuel_before)
            ws_fuel.cell(row=row_idx, column=5, value=f.fuel_after)
            ws_fuel.cell(row=row_idx, column=6, value=f.cost or "")
            ws_fuel.cell(row=row_idx, column=7, value=f.user_name or "—")
            ws_fuel.cell(row=row_idx, column=8, value=f.notes or "")
            for c in range(1, 9):
                apply_cell_border(ws_fuel.cell(row=row_idx, column=c))

        # 4. Maintenance sheet
        ws_maint = wb.create_sheet(title="Обслуживание (ТО)")
        ws_maint.views.sheetView[0].showGridLines = True
        maint_headers = ["№", "Дата", "Моточасы ТО", "Следующее ТО (мч)", "Описание работ", "Замененные детали", "Стоимость", "Кто провел"]
        for col_idx, header in enumerate(maint_headers, start=1):
            cell = ws_maint.cell(row=1, column=col_idx, value=header)
            apply_header_style(cell)

        for row_idx, m in enumerate(maints, start=2):
            ws_maint.cell(row=row_idx, column=1, value=m.id)
            ws_maint.cell(row=row_idx, column=2, value=format_dt(m.timestamp))
            ws_maint.cell(row=row_idx, column=3, value=m.hours_at_maintenance)
            ws_maint.cell(row=row_idx, column=4, value=m.next_maintenance_hours)
            ws_maint.cell(row=row_idx, column=5, value=m.description)
            ws_maint.cell(row=row_idx, column=6, value=m.parts_replaced or "")
            ws_maint.cell(row=row_idx, column=7, value=m.cost or "")
            ws_maint.cell(row=row_idx, column=8, value=m.user_name or "—")
            for c in range(1, 9):
                apply_cell_border(ws_maint.cell(row=row_idx, column=c))

        # Auto-adjust column widths for all sheets
        for sheet in wb.worksheets:
            for col in sheet.columns:
                max_len = 0
                col_letter = get_column_letter(col[0].column)
                for cell in col:
                    val_str = str(cell.value or "")
                    if len(val_str) > max_len:
                        max_len = len(val_str)
                sheet.column_dimensions[col_letter].width = max(max_len + 4, 12)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
