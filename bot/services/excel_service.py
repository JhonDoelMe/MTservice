from io import BytesIO
from datetime import datetime, timezone
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bot.database.models import FuelLog, GeneratorState, MaintenanceLog, RunLog, AuditResetLog
from bot.services.generator_service import format_dt, format_duration


# Palette definition
NAVY_HEADER = "0F2942"
WHITE = "FFFFFF"
ZEBRA_EVEN = "F8FAFC"
ZEBRA_ODD = "FFFFFF"
BORDER_COLOR = "E2E8F0"
BORDER_DARK = "94A3B8"

# Accents
GREEN_BG = "DCFCE7"
GREEN_TXT = "166534"
RED_BG = "FEE2E2"
RED_TXT = "991B1B"
AMBER_BG = "FEF3C7"
AMBER_TXT = "92400E"
BLUE_BG = "E0F2FE"
BLUE_TXT = "0369A1"
PURPLE_BG = "EDE9FE"
PURPLE_TXT = "4338CA"


def apply_header_style(cell, text=None):
    """Applies modern deep navy styling to table header cells."""
    if text is not None:
        cell.value = text
    cell.font = Font(name="Calibri", size=11, bold=True, color=WHITE)
    cell.fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(border_style="thin", color=NAVY_HEADER)
    cell.border = Border(top=thin, left=thin, right=thin, bottom=thin)


def apply_data_cell(cell, value, align="center", is_even=False, bold=False, text_color=None, bg_color=None):
    """Applies clean data formatting with optional zebra striping and alignment."""
    cell.value = value
    cell.font = Font(
        name="Calibri",
        size=10,
        bold=bold,
        color=text_color if text_color else "1E293B"
    )

    fill_hex = bg_color if bg_color else (ZEBRA_EVEN if is_even else ZEBRA_ODD)
    cell.fill = PatternFill(start_color=fill_hex, end_color=fill_hex, fill_type="solid")
    cell.alignment = Alignment(horizontal=align, vertical="center", wrap_text=False)

    border_side = Side(border_style="thin", color=BORDER_COLOR)
    cell.border = Border(top=border_side, left=border_side, right=border_side, bottom=border_side)


def apply_total_row(ws, row_idx, num_cols, label="Всього:", sums=None):
    """Applies a professional double-underlined accounting total row at the bottom."""
    ws.row_dimensions[row_idx].height = 22
    for c in range(1, num_cols + 1):
        cell = ws.cell(row=row_idx, column=c)
        val = ""
        align = "center"
        if c == 1:
            val = label
            align = "left"
        elif sums and c in sums:
            val = sums[c]
            align = "right" if isinstance(val, (int, float)) or "₴" in str(val) else "center"

        cell.value = val
        cell.font = Font(name="Calibri", size=11, bold=True, color="0F172A")
        cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        cell.alignment = Alignment(horizontal=align, vertical="center")

        top_border = Side(border_style="thin", color="64748B")
        bottom_border = Side(border_style="double", color=NAVY_HEADER)
        side_border = Side(border_style="thin", color=BORDER_COLOR)
        cell.border = Border(top=top_border, bottom=bottom_border, left=side_border, right=side_border)


def auto_fit_columns(ws, min_width=12, max_width=45):
    """Calculates optimal column widths based on contents and headers."""
    for col in ws.columns:
        col_letter = get_column_letter(col[0].column)
        max_len = 0
        for cell in col:
            val_str = str(cell.value or "")
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = max(min(max_len + 4, max_width), min_width)


class ExcelService:

    @staticmethod
    async def generate_full_report(session: AsyncSession) -> BytesIO:
        wb = Workbook()

        # -----------------------------------------------------------------
        # 1. SUMMARY SHEET (Зведення)
        # -----------------------------------------------------------------
        ws_summary = wb.active
        ws_summary.title = "📊 Зведення"
        ws_summary.sheet_properties.tabColor = "0284C7"
        ws_summary.views.sheetView[0].showGridLines = True
        ws_summary.freeze_panes = "A4"

        gen_res = await session.execute(select(GeneratorState).where(GeneratorState.id == 1))
        gen = gen_res.scalar_one_or_none()

        runs_res = await session.execute(select(RunLog).order_by(RunLog.id.desc()))
        runs = runs_res.scalars().all()

        fuel_res = await session.execute(select(FuelLog).order_by(FuelLog.id.desc()))
        refuels = fuel_res.scalars().all()

        maint_res = await session.execute(select(MaintenanceLog).order_by(MaintenanceLog.id.desc()))
        maints = maint_res.scalars().all()

        audit_res = await session.execute(select(AuditResetLog).order_by(AuditResetLog.id.desc()))
        audits = audit_res.scalars().all()

        total_hours_ran = sum(r.duration_hours for r in runs)
        total_fuel_burned = sum(r.fuel_consumed for r in runs)
        total_fuel_added = sum(f.amount_liters for f in refuels)
        total_fuel_cost = sum((f.cost or 0.0) for f in refuels)
        total_maint_cost = sum((m.cost or 0.0) for m in maints)

        # Main Title Banner
        ws_summary.merge_cells("A1:D1")
        title_cell = ws_summary["A1"]
        title_cell.value = f"⚡ ЗВІТ ДИСПЕТЧЕРА ГЕНЕРАТОРА: {gen.name if gen else 'Основний ДГУ'}"
        title_cell.font = Font(name="Calibri", size=15, bold=True, color=WHITE)
        title_cell.fill = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
        title_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws_summary.row_dimensions[1].height = 36

        # Subtitle Row
        ws_summary.merge_cells("A2:D2")
        sub_cell = ws_summary["A2"]
        sub_cell.value = f"Сформовано: {format_dt(datetime.now(timezone.utc))} (Київський час) | MTservice Smart Generator Management"
        sub_cell.font = Font(name="Calibri", size=9, italic=True, color="64748B")
        sub_cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        sub_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
        ws_summary.row_dimensions[2].height = 20

        sections = [
            ("📌 ОСНОВНІ ПАРАМЕТРИ ОБ'ЄКТА", BLUE_BG, BLUE_TXT, [
                ("Поточний робочий стан", "🟢 В РОБОТІ" if (gen and gen.is_running) else "🔴 ЗУПИНЕНО"),
                ("Паспортна норма витрати пального", f"{gen.fuel_rate:.2f} л/год" if gen else "4.50 л/год"),
                ("Загальна ємність паливного бака", f"{gen.tank_capacity:.0f} л" if gen else "150 л"),
                ("Поточний залишок у баку", f"{gen.current_fuel:.1f} л ({(gen.current_fuel / gen.tank_capacity * 100):.0f}%)" if (gen and gen.tank_capacity) else "—"),
                ("Прогноз автономної роботи на залишку", f"~{(gen.current_fuel / gen.fuel_rate):.1f} год" if (gen and gen.fuel_rate) else "—"),
            ]),
            ("⏱ МОТОГОДИНИ ТА ТЕХНІЧНЕ ОБСЛУГОВУВАННЯ", PURPLE_BG, PURPLE_TXT, [
                ("Загальне напрацювання генератора", f"{gen.total_hours:.2f} мч" if gen else "0.00 мч"),
                ("Регламентний інтервал між ТО", f"{gen.maintenance_interval_hours:.0f} мч" if gen else "250 мч"),
                ("Позначка попереднього ТО (олива)", f"{gen.last_maintenance_hours:.1f} мч" if gen else "0.0 мч"),
                ("Залишок до наступного ТО", f"{((gen.last_maintenance_hours + gen.maintenance_interval_hours) - gen.total_hours):.2f} мч" if gen else "—"),
                ("Напрацювання свічок запалювання", f"{(gen.total_hours - (gen.last_spark_plugs_hours or 0.0)):.1f} мч тому" if gen else "—"),
                ("Напрацювання повітряного фільтру", f"{(gen.total_hours - (gen.last_air_filter_hours or 0.0)):.1f} мч тому" if gen else "—"),
                ("Напрацювання паливного фільтру", f"{(gen.total_hours - (gen.last_fuel_filter_hours or 0.0)):.1f} мч тому" if gen else "—"),
            ]),
            ("⛽ ПАЛИВНИЙ БАЛАНС ТА СТАТИСТИКА РОБОТИ", AMBER_BG, AMBER_TXT, [
                ("Всього зафіксовано запусків", f"{len(runs)} сесій"),
                ("Сумарний час роботи за весь період", f"{total_hours_ran:.2f} год ({format_duration(total_hours_ran)})"),
                ("Сумарна витрата пального за період", f"{total_fuel_burned:.2f} л"),
                ("Сумарно заправлено пального за період", f"{total_fuel_added:.2f} л"),
                ("Кількість проведених заправок", f"{len(refuels)} заправок"),
                ("Кількість виконаних ТО", f"{len(maints)} записів"),
            ]),
            ("💰 ФІНАНСОВІ ВИТРАТИ", GREEN_BG, GREEN_TXT, [
                ("Сумарні витрати на заправку пального", f"{total_fuel_cost:,.2f} ₴".replace(",", " ")),
                ("Сумарні витрати на сервіс та запчастини", f"{total_maint_cost:,.2f} ₴".replace(",", " ")),
                ("ЗАГАЛЬНИЙ БЮДЖЕТ ЕКСПЛУАТАЦІЇ", f"{(total_fuel_cost + total_maint_cost):,.2f} ₴".replace(",", " ")),
            ]),
        ]

        curr_row = 4
        for sec_title, sec_bg, sec_txt, items in sections:
            ws_summary.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=4)
            sec_cell = ws_summary.cell(row=curr_row, column=1)
            sec_cell.value = sec_title
            sec_cell.font = Font(name="Calibri", size=11, bold=True, color=sec_txt)
            sec_cell.fill = PatternFill(start_color=sec_bg, end_color=sec_bg, fill_type="solid")
            sec_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)
            ws_summary.row_dimensions[curr_row].height = 24
            curr_row += 1

            for idx, (param, val) in enumerate(items):
                ws_summary.merge_cells(start_row=curr_row, start_column=1, end_row=curr_row, end_column=2)
                p_cell = ws_summary.cell(row=curr_row, column=1, value=param)
                p_cell.font = Font(name="Calibri", size=10, bold=False, color="334155")
                p_cell.alignment = Alignment(horizontal="left", vertical="center", indent=1)

                ws_summary.merge_cells(start_row=curr_row, start_column=3, end_row=curr_row, end_column=4)
                v_cell = ws_summary.cell(row=curr_row, column=3, value=val)
                v_cell.font = Font(name="Calibri", size=10, bold=True, color="0F172A")
                v_cell.alignment = Alignment(horizontal="right", vertical="center")

                # Highlight status
                if "В РОБОТІ" in str(val):
                    v_cell.fill = PatternFill(start_color=GREEN_BG, end_color=GREEN_BG, fill_type="solid")
                    v_cell.font = Font(name="Calibri", size=10, bold=True, color=GREEN_TXT)
                elif "ЗУПИНЕНО" in str(val):
                    v_cell.fill = PatternFill(start_color=RED_BG, end_color=RED_BG, fill_type="solid")
                    v_cell.font = Font(name="Calibri", size=10, bold=True, color=RED_TXT)

                is_even = (idx % 2 == 1)
                row_bg = ZEBRA_EVEN if is_even else ZEBRA_ODD
                if not v_cell.fill.start_color.rgb:
                    v_cell.fill = PatternFill(start_color=row_bg, end_color=row_bg, fill_type="solid")
                p_cell.fill = PatternFill(start_color=row_bg, end_color=row_bg, fill_type="solid")

                border_thin = Side(border_style="thin", color=BORDER_COLOR)
                for col_i in range(1, 5):
                    ws_summary.cell(row=curr_row, column=col_i).border = Border(
                        top=border_thin, left=border_thin, right=border_thin, bottom=border_thin
                    )

                ws_summary.row_dimensions[curr_row].height = 20
                curr_row += 1

            curr_row += 1  # Empty gap between sections

        auto_fit_columns(ws_summary, min_width=18, max_width=50)

        # -----------------------------------------------------------------
        # 2. RUNS SHEET (Журнал запусків)
        # -----------------------------------------------------------------
        ws_runs = wb.create_sheet(title="⏱ Журнал запусків")
        ws_runs.sheet_properties.tabColor = "10B981"
        ws_runs.views.sheetView[0].showGridLines = True
        ws_runs.freeze_panes = "A2"
        ws_runs.row_dimensions[1].height = 28

        run_headers = [
            "№", "Час запуску (Київ)", "Час зупинки (Київ)", "Тривалість (год)",
            "Витрата (л)", "Норма (л/год)", "Бак до (л)", "Бак після (л)",
            "Мотогодини (мч)", "Запустив", "Зупинив", "Примітки"
        ]
        for col_idx, h in enumerate(run_headers, start=1):
            cell = ws_runs.cell(row=1, column=col_idx)
            apply_header_style(cell, h)

        for row_idx, r in enumerate(runs, start=2):
            ws_runs.row_dimensions[row_idx].height = 21
            is_even = (row_idx % 2 == 0)

            apply_data_cell(ws_runs.cell(row=row_idx, column=1), r.id, align="center", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=2), format_dt(r.start_time), align="center", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=3), format_dt(r.stop_time), align="center", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=4), round(r.duration_hours, 2), align="right", is_even=is_even, bold=True, text_color=BLUE_TXT)
            apply_data_cell(ws_runs.cell(row=row_idx, column=5), round(r.fuel_consumed, 2), align="right", is_even=is_even, bold=True, text_color=RED_TXT)
            apply_data_cell(ws_runs.cell(row=row_idx, column=6), round(r.fuel_rate, 2), align="right", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=7), round(r.start_fuel, 1), align="right", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=8), round(r.end_fuel, 1), align="right", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=9), round(r.total_hours_after, 2), align="right", is_even=is_even, bold=True)
            apply_data_cell(ws_runs.cell(row=row_idx, column=10), r.start_user_name or "—", align="left", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=11), r.stop_user_name or "—", align="left", is_even=is_even)
            apply_data_cell(ws_runs.cell(row=row_idx, column=12), r.notes or "", align="left", is_even=is_even)

        # Totals Row
        tot_row_runs = len(runs) + 2
        apply_total_row(ws_runs, tot_row_runs, len(run_headers), label="Всього за період:", sums={
            4: round(total_hours_ran, 2),
            5: round(total_fuel_burned, 2)
        })

        ws_runs.auto_filter.ref = f"A1:{get_column_letter(len(run_headers))}{tot_row_runs - 1}"
        auto_fit_columns(ws_runs, min_width=12, max_width=40)

        # -----------------------------------------------------------------
        # 3. REFUELS SHEET (Заправки)
        # -----------------------------------------------------------------
        ws_fuel = wb.create_sheet(title="⛽ Заправки")
        ws_fuel.sheet_properties.tabColor = "F59E0B"
        ws_fuel.views.sheetView[0].showGridLines = True
        ws_fuel.freeze_panes = "A2"
        ws_fuel.row_dimensions[1].height = 28

        fuel_headers = [
            "№", "Дата і час (Київ)", "Заправлено (л)", "Бак до (л)",
            "Бак після (л)", "Вартість (₴)", "Хто заправив", "Примітки / АЗС"
        ]
        for col_idx, h in enumerate(fuel_headers, start=1):
            cell = ws_fuel.cell(row=1, column=col_idx)
            apply_header_style(cell, h)

        for row_idx, f in enumerate(refuels, start=2):
            ws_fuel.row_dimensions[row_idx].height = 21
            is_even = (row_idx % 2 == 0)

            apply_data_cell(ws_fuel.cell(row=row_idx, column=1), f.id, align="center", is_even=is_even)
            apply_data_cell(ws_fuel.cell(row=row_idx, column=2), format_dt(f.timestamp), align="center", is_even=is_even)
            apply_data_cell(ws_fuel.cell(row=row_idx, column=3), round(f.amount_liters, 1), align="right", is_even=is_even, bold=True, text_color=GREEN_TXT)
            apply_data_cell(ws_fuel.cell(row=row_idx, column=4), round(f.fuel_before, 1), align="right", is_even=is_even)
            apply_data_cell(ws_fuel.cell(row=row_idx, column=5), round(f.fuel_after, 1), align="right", is_even=is_even)
            cost_str = f"{f.cost:.2f} ₴" if f.cost else "—"
            apply_data_cell(ws_fuel.cell(row=row_idx, column=6), cost_str, align="right", is_even=is_even, bold=bool(f.cost))
            apply_data_cell(ws_fuel.cell(row=row_idx, column=7), f.user_name or "—", align="left", is_even=is_even)
            apply_data_cell(ws_fuel.cell(row=row_idx, column=8), f.notes or "", align="left", is_even=is_even)

        tot_row_fuel = len(refuels) + 2
        apply_total_row(ws_fuel, tot_row_fuel, len(fuel_headers), label="Всього заправлено:", sums={
            3: round(total_fuel_added, 1),
            6: f"{total_fuel_cost:,.2f} ₴".replace(",", " ")
        })

        ws_fuel.auto_filter.ref = f"A1:{get_column_letter(len(fuel_headers))}{tot_row_fuel - 1}"
        auto_fit_columns(ws_fuel, min_width=13, max_width=40)

        # -----------------------------------------------------------------
        # 4. MAINTENANCE SHEET (ТО)
        # -----------------------------------------------------------------
        ws_maint = wb.create_sheet(title="🔧 Обслуговування (ТО)")
        ws_maint.sheet_properties.tabColor = "6366F1"
        ws_maint.views.sheetView[0].showGridLines = True
        ws_maint.freeze_panes = "A2"
        ws_maint.row_dimensions[1].height = 28

        maint_headers = [
            "№", "Дата і час (Київ)", "Категорія ТО", "Мотогодини ТО",
            "Наступне ТО (мч)", "Опис виконаних робіт", "Замінені деталі / розхідники",
            "Вартість (₴)", "Хто виконав"
        ]
        for col_idx, h in enumerate(maint_headers, start=1):
            cell = ws_maint.cell(row=1, column=col_idx)
            apply_header_style(cell, h)

        for row_idx, m in enumerate(maints, start=2):
            ws_maint.row_dimensions[row_idx].height = 21
            is_even = (row_idx % 2 == 0)

            is_main = getattr(m, "is_main", True)
            type_label = "🟢 ГОЛОВНЕ (Олива)" if is_main else f"🔧 ПРОМІЖНЕ: {m.title or m.maint_type or 'Деталі'}"
            type_bg = GREEN_BG if is_main else BLUE_BG
            type_txt = GREEN_TXT if is_main else BLUE_TXT

            apply_data_cell(ws_maint.cell(row=row_idx, column=1), m.id, align="center", is_even=is_even)
            apply_data_cell(ws_maint.cell(row=row_idx, column=2), format_dt(m.timestamp), align="center", is_even=is_even)
            apply_data_cell(ws_maint.cell(row=row_idx, column=3), type_label, align="center", is_even=is_even, bold=True, text_color=type_txt, bg_color=type_bg)
            apply_data_cell(ws_maint.cell(row=row_idx, column=4), round(m.hours_at_maintenance, 1), align="right", is_even=is_even, bold=True)
            apply_data_cell(ws_maint.cell(row=row_idx, column=5), round(m.next_maintenance_hours, 1) if is_main else "—", align="right", is_even=is_even)
            apply_data_cell(ws_maint.cell(row=row_idx, column=6), m.description, align="left", is_even=is_even)
            apply_data_cell(ws_maint.cell(row=row_idx, column=7), m.parts_replaced or "", align="left", is_even=is_even)
            m_cost_str = f"{m.cost:.2f} ₴" if m.cost else "—"
            apply_data_cell(ws_maint.cell(row=row_idx, column=8), m_cost_str, align="right", is_even=is_even, bold=bool(m.cost))
            apply_data_cell(ws_maint.cell(row=row_idx, column=9), m.user_name or "—", align="left", is_even=is_even)

        tot_row_maint = len(maints) + 2
        apply_total_row(ws_maint, tot_row_maint, len(maint_headers), label="Всього витрат на ТО:", sums={
            8: f"{total_maint_cost:,.2f} ₴".replace(",", " ")
        })

        ws_maint.auto_filter.ref = f"A1:{get_column_letter(len(maint_headers))}{tot_row_maint - 1}"
        auto_fit_columns(ws_maint, min_width=14, max_width=45)

        # -----------------------------------------------------------------
        # 5. AUDIT RESET SHEET (Журнал аудиту та скидань)
        # -----------------------------------------------------------------
        ws_audit = wb.create_sheet(title="🛡 Журнал аудиту")
        ws_audit.sheet_properties.tabColor = "EF4444"
        ws_audit.views.sheetView[0].showGridLines = True
        ws_audit.freeze_panes = "A2"
        ws_audit.row_dimensions[1].height = 28

        audit_headers = [
            "№", "Дата і час (Київ)", "Тип скидання", "Обов'язкова причина",
            "Хто виконав", "Деталі операції та попередній стан"
        ]
        for col_idx, h in enumerate(audit_headers, start=1):
            cell = ws_audit.cell(row=1, column=col_idx)
            apply_header_style(cell, h)

        reset_labels = {
            "all": "💥 ПОВНЕ СКИДАННЯ",
            "fuel_zero": "⛽ ОБНУЛЕННЯ БАКА",
            "hours_zero": "⏱ ОБНУЛЕННЯ МОТОГОДИН",
            "maint_main": "🛠 СКИДАННЯ ГОЛОВНОГО ТО",
            "maint_intermediate": "🔧 СКИДАННЯ ПРОМІЖНОГО ТО",
        }

        for row_idx, a in enumerate(audits, start=2):
            ws_audit.row_dimensions[row_idx].height = 21
            is_even = (row_idx % 2 == 0)
            a_label = reset_labels.get(a.reset_type, a.reset_type)

            apply_data_cell(ws_audit.cell(row=row_idx, column=1), a.id, align="center", is_even=is_even)
            apply_data_cell(ws_audit.cell(row=row_idx, column=2), format_dt(a.timestamp), align="center", is_even=is_even)
            apply_data_cell(ws_audit.cell(row=row_idx, column=3), a_label, align="center", is_even=is_even, bold=True, text_color=RED_TXT, bg_color=RED_BG)
            apply_data_cell(ws_audit.cell(row=row_idx, column=4), a.reason, align="left", is_even=is_even, bold=True)
            apply_data_cell(ws_audit.cell(row=row_idx, column=5), a.user_name or "—", align="left", is_even=is_even)
            apply_data_cell(ws_audit.cell(row=row_idx, column=6), a.details or "", align="left", is_even=is_even)

        tot_row_audit = len(audits) + 2
        apply_total_row(ws_audit, tot_row_audit, len(audit_headers), label="Всього записів аудиту:", sums={
            3: f"{len(audits)} дій"
        })

        ws_audit.auto_filter.ref = f"A1:{get_column_letter(len(audit_headers))}{tot_row_audit - 1}"
        auto_fit_columns(ws_audit, min_width=14, max_width=55)

        output = BytesIO()
        wb.save(output)
        output.seek(0)
        return output
