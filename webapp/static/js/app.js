// Telegram WebApp SDK initialization
const tg = window.Telegram?.WebApp;

if (tg) {
  tg.expand();
  tg.ready();
  if (tg.enableClosingConfirmation) {
    tg.enableClosingConfirmation();
  }
}

// Theme handling
function applyTheme(theme) {
  if (theme === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark');
  } else if (theme === 'light') {
    document.documentElement.setAttribute('data-theme', 'light');
  } else {
    document.documentElement.removeAttribute('data-theme'); // Auto (Telegram/System fallback)
  }
}

function changeTheme() {
  const theme = document.getElementById("themeSelect").value;
  localStorage.setItem("appTheme", theme);
  applyTheme(theme);
}

// Init theme on boot
const savedTheme = localStorage.getItem("appTheme") || "auto";
applyTheme(savedTheme);
document.addEventListener("DOMContentLoaded", () => {
  const sel = document.getElementById("themeSelect");
  if (sel) sel.value = savedTheme;
});

// State
let currentStatus = null;
let liveTimerInterval = null;
let activeStartTime = null;

// Haptic feedback helper
function haptic(type = "light") {
  if (!tg?.HapticFeedback) return;
  if (type === "success" || type === "warning" || type === "error") {
    tg.HapticFeedback.notificationOccurred(type);
  } else if (type === "selection") {
    tg.HapticFeedback.selectionChanged();
  } else {
    tg.HapticFeedback.impactOccurred(type);
  }
}

// Fetch helper with Telegram initData
async function apiCall(endpoint, method = "GET", body = null) {
  const headers = {
    "Content-Type": "application/json",
    "X-Telegram-Init-Data": tg?.initData || ""
  };
  const config = { method, headers };
  if (body) {
    config.body = JSON.stringify(body);
  }

  try {
    const res = await fetch(endpoint, config);
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "Помилка сервера" }));
      throw new Error(err.detail || `Помилка ${res.status}`);
    }
    return await res.json();
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
}

// Kyiv Clock Ticker
function updateKyivClock() {
  const now = new Date();
  const timeStr = now.toLocaleTimeString("uk-UA", {
    timeZone: "Europe/Kyiv",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit"
  });
  const el = document.getElementById("currentTimeKyiv");
  if (el) el.innerText = `Київ: ${timeStr}`;
}
setInterval(updateKyivClock, 1000);
updateKyivClock();

// Helper to reliably parse server ISO timestamp as UTC milliseconds
function parseUtcTime(isoStr) {
  if (!isoStr) return Date.now();
  let str = String(isoStr).trim();
  // If no timezone offset (Z, +HH:MM, or -HH:MM), treat as UTC by appending Z
  if (!str.endsWith("Z") && !str.includes("+") && !/[0-9]-[0-9]{2}:[0-9]{2}$/.test(str)) {
    str += "Z";
  }
  const t = new Date(str).getTime();
  return isNaN(t) ? Date.now() : t;
}

// Live Running Stopwatch
function startLiveStopwatch(startTimeIso) {
  if (liveTimerInterval) clearInterval(liveTimerInterval);
  activeStartTime = parseUtcTime(startTimeIso);

  function tick() {
    const now = Date.now();
    const diffMs = Math.max(0, now - activeStartTime);
    const totalSecs = Math.floor(diffMs / 1000);
    const hrs = Math.floor(totalSecs / 3600);
    const mins = Math.floor((totalSecs % 3600) / 60);
    const secs = totalSecs % 60;
    const str = `${String(hrs).padStart(2, '0')}:${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    const timerEl = document.getElementById("liveTimer");
    if (timerEl) timerEl.innerText = str;

    // Live update fuel consumed tile during run
    if (currentStatus?.fuel_rate) {
      const hoursElapsed = totalSecs / 3600;
      const liveSessionFuel = (hoursElapsed * currentStatus.fuel_rate).toFixed(2);
      const fuelConsVal = document.getElementById("fuelConsumptionVal");
      if (fuelConsVal) fuelConsVal.innerText = `${liveSessionFuel} л`;
    }
  }
  tick();
  liveTimerInterval = setInterval(tick, 1000);
}

function stopLiveStopwatch() {
  if (liveTimerInterval) {
    clearInterval(liveTimerInterval);
    liveTimerInterval = null;
  }
}

// Lock Screen helper
function showLockScreen(message) {
  const overlay = document.getElementById("accessLockOverlay");
  if (!overlay) return;
  overlay.style.display = "flex";

  const tgUser = tg?.initDataUnsafe?.user;
  if (tgUser) {
    const uidEl = document.getElementById("lockUserId");
    const unameEl = document.getElementById("lockUserName");
    if (uidEl) uidEl.innerText = tgUser.id;
    if (unameEl) unameEl.innerText = `${tgUser.first_name || ''} ${tgUser.last_name || ''} (@${tgUser.username || 'немає'})`.trim();
  }

  const iconEl = document.getElementById("lockIcon");
  const titleEl = document.getElementById("lockTitle");
  const msgEl = document.getElementById("lockMsg");

  if (message && message.includes("заблоковано")) {
    if (iconEl) iconEl.innerText = "⛔";
    if (titleEl) titleEl.innerText = "Доступ заблоковано";
    if (msgEl) msgEl.innerText = "Ваш доступ до системи диспетчера генератора заблоковано адміністратором.";
  } else {
    if (iconEl) iconEl.innerText = "⏳";
    if (titleEl) titleEl.innerText = "Очікування доступу";
    if (msgEl) msgEl.innerText = "Ваш акаунт очікує підтвердження адміністратором. Передайте свій Telegram ID керівнику або старшому диспетчеру.";
  }
}

// Render Dashboard
async function loadStatus() {
  try {
    const data = await apiCall("/api/status");
    currentStatus = data;

    // Hide lock screen if previously shown
    const lockOverlay = document.getElementById("accessLockOverlay");
    if (lockOverlay) lockOverlay.style.display = "none";

    // Header & User Info
    document.getElementById("genName").innerText = data.name;
    const badge = document.getElementById("headerStatusBadge");
    const statusText = document.getElementById("headerStatusText");
    const userRoleBadge = document.getElementById("userRoleBadge");

    if (userRoleBadge && data.current_user) {
      const uRole = data.current_user.role === "admin" ? "👑 Адмін" : "👤 Оператор";
      userRoleBadge.innerText = `${data.current_user.user_name || 'Диспетчер'} • ${uRole}`;
    }

    // Working Hours Chip
    const whChip = document.getElementById("workHoursChip");
    const whText = document.getElementById("workHoursText");
    const whIcon = document.getElementById("workHoursIcon");
    if (whChip && data.work_hours?.enabled) {
      whChip.style.display = "inline-flex";
      if (data.work_hours.is_allowed) {
        whChip.className = "work-hours-chip allowed";
        if (whIcon) whIcon.innerText = "🕒";
        if (whText) whText.innerText = `Графік: ${data.work_hours.start} – ${data.work_hours.end}`;
      } else {
        whChip.className = "work-hours-chip restricted";
        if (whIcon) whIcon.innerText = "⛔";
        if (whText) whText.innerText = `Поза графіком (${data.work_hours.start} – ${data.work_hours.end})`;
      }
    }

    if (data.is_running) {
      badge.className = "status-badge running";
      statusText.innerText = "В РОБОТІ";
      document.getElementById("runningView").style.display = "block";
      document.getElementById("stoppedView").style.display = "none";
      document.getElementById("runningOperatorInfo").innerText = `Запустив: ${data.current_start_user_name || 'Оператор'}`;
      if (data.current_start_time) {
        startLiveStopwatch(data.current_start_time);
      }
    } else {
      badge.className = "status-badge stopped";
      statusText.innerText = "ЗУПИНЕНО";
      document.getElementById("runningView").style.display = "none";
      document.getElementById("stoppedView").style.display = "block";
      stopLiveStopwatch();
    }

    // Fuel Hero
    document.getElementById("fuelPctChip").innerText = `${Math.round(data.fuel_pct)}%`;
    document.getElementById("fuelLiters").innerText = `${data.current_fuel} л`;
    document.getElementById("fuelCapacity").innerText = `із ${data.tank_capacity} л`;
    const bar = document.getElementById("fuelProgressBar");
    bar.style.width = `${Math.min(100, Math.max(0, data.fuel_pct))}%`;
    if (data.fuel_pct <= 20) {
      bar.className = "progress-bar-fill warning";
    } else {
      bar.className = "progress-bar-fill";
    }
    document.getElementById("fuelHoursRemaining").innerText = `~${data.remaining_runtime_hours} год`;
    document.getElementById("fuelRateText").innerText = `${data.fuel_rate} л/год`;

    // Metrics - 1. Total Hours
    document.getElementById("totalHoursVal").innerText = `${data.total_hours.toFixed(2)} мч`;

    // Metrics - 2. Maintenance
    const maintEl = document.getElementById("hoursToMaintVal");
    const maintBadge = document.getElementById("maintStatusBadge");
    maintEl.innerText = `${data.hours_to_maint.toFixed(1)} мч`;

    if (data.hours_to_maint <= 0) {
      maintBadge.innerText = `ПРОСТРОЧЕНО (${Math.abs(data.hours_to_maint).toFixed(1)} мч)!`;
      maintBadge.className = "metric-sub badge-danger";
    } else if (data.hours_to_maint <= data.warning_hours) {
      maintBadge.innerText = "Скоро планове ТО!";
      maintBadge.className = "metric-sub badge-warning";
    } else {
      maintBadge.innerText = "В нормі";
      maintBadge.className = "metric-sub badge-normal";
    }

    // Metrics - 3. Fuel Consumption
    const fuelConsVal = document.getElementById("fuelConsumptionVal");
    const fuelConsSub = document.getElementById("fuelConsumptionSub");
    if (fuelConsVal && fuelConsSub) {
      if (data.is_running) {
        fuelConsVal.innerText = `${(data.session_fuel_burned || 0).toFixed(2)} л`;
        fuelConsSub.innerText = `за сесію (сьогодні: ${(data.today_fuel_burned || 0).toFixed(1)} л)`;
      } else {
        fuelConsVal.innerText = `${(data.today_fuel_burned || 0).toFixed(1)} л`;
        fuelConsSub.innerText = `витрачено за сьогодні`;
      }
    }

    // Metrics - 4. Last Refuel
    const lastRefuelVal = document.getElementById("lastRefuelVal");
    const lastRefuelSub = document.getElementById("lastRefuelSub");
    if (lastRefuelVal && lastRefuelSub) {
      if (data.last_refuel) {
        lastRefuelVal.innerText = `+${data.last_refuel.amount_liters} л`;
        const costText = data.last_refuel.cost ? ` • ${data.last_refuel.cost} ₴` : '';
        const noteText = data.last_refuel.notes ? ` (${data.last_refuel.notes})` : '';
        lastRefuelSub.innerText = `${data.last_refuel.timestamp_formatted}${costText}${noteText}`;
      } else {
        lastRefuelVal.innerText = "—";
        lastRefuelSub.innerText = "Немає записів";
      }
    }

    // Tab 2 Fuel sync
    document.getElementById("fuelTabAmount").innerText = `${data.current_fuel} л (${Math.round(data.fuel_pct)}%)`;
    document.getElementById("fuelTabCap").innerText = `Ємність бака: ${data.tank_capacity} л (витрата: ${data.fuel_rate} л/год)`;

    // Tab 3 Main Maint sync
    document.getElementById("maintTabRemain").innerText = `${data.hours_to_maint.toFixed(1)} мч`;
    document.getElementById("maintTabInterval").innerText = `${data.maintenance_interval_hours} мч`;
    document.getElementById("maintTabLast").innerText = `${data.last_maintenance_hours} мч (${data.last_maintenance_date_formatted})`;
    const mChip = document.getElementById("maintTabStatusChip");
    if (data.hours_to_maint <= 0) {
      mChip.className = "badge-danger";
      mChip.innerText = "🔴 Прострочено!";
    } else if (data.hours_to_maint <= data.warning_hours) {
      mChip.className = "badge-warning";
      mChip.innerText = "🟡 Скоро ТО";
    } else {
      mChip.className = "badge-normal";
      mChip.innerText = "🟢 В нормі";
    }

    // Tab 3 Intermediate Maint components sync
    const spEl = document.getElementById("sparkPlugsAgoText");
    if (spEl) spEl.innerText = `${(data.spark_plugs_hours_ago || 0).toFixed(1)} мч тому`;

    const afEl = document.getElementById("airFilterAgoText");
    if (afEl) afEl.innerText = `${(data.air_filter_hours_ago || 0).toFixed(1)} мч тому`;

    const ffEl = document.getElementById("fuelFilterAgoText");
    if (ffEl) ffEl.innerText = `${(data.fuel_filter_hours_ago || 0).toFixed(1)} мч тому`;

    // Tab 5 Settings sync placeholders & profile
    document.getElementById("calibHoursInput").placeholder = data.base_total_hours;
    document.getElementById("calibFuelInput").placeholder = data.current_fuel;
    document.getElementById("calibRateInput").placeholder = data.fuel_rate;
    document.getElementById("calibTankInput").placeholder = data.tank_capacity;
    document.getElementById("calibIntervalInput").placeholder = data.maintenance_interval_hours;

    if (data.current_user) {
      const myInput = document.getElementById("myCustomNameInput");
      if (myInput && document.activeElement !== myInput) {
        myInput.value = data.current_user.custom_name || "";
      }
      const myRoleBadge = document.getElementById("myRoleBadge");
      if (myRoleBadge) {
        myRoleBadge.innerText = data.current_user.is_admin ? "👑 Адміністратор" : "👤 Оператор";
      }
    }

  } catch (e) {
    console.error("Помилка оновлення статусу:", e);
    if (e.message && (e.message.includes("очікує підтвердження") || e.message.includes("заблоковано") || e.message.includes("403"))) {
      showLockScreen(e.message);
    }
  }
}

// Tab Switching
function switchTab(tabId, btn) {
  haptic("selection");
  document.querySelectorAll(".tab-page").forEach(p => p.classList.remove("active"));
  document.querySelectorAll(".nav-item").forEach(b => b.classList.remove("active"));

  document.getElementById(tabId).classList.add("active");
  btn.classList.add("active");

  if (tabId === "tabFuel") loadFuelHistory();
  if (tabId === "tabMaint") loadMaintHistory();
  if (tabId === "tabReports") loadReports();
  if (tabId === "tabSettings") loadUsers();
}

// Modal open/close
function openModal(id) {
  haptic("light");
  document.getElementById(id).classList.add("active");
}

function closeModal(id) {
  haptic("light");
  document.getElementById(id).classList.remove("active");
}

// Immediate Start Generator (no modal, starts stopwatch at 00:00:00)
async function startGeneratorImmediately() {
  haptic("medium");

  if (currentStatus?.work_hours?.enabled && !currentStatus?.work_hours?.is_allowed) {
    alert(`⛔ Запуск заборонено: робочий час генератора з ${currentStatus.work_hours.start} до ${currentStatus.work_hours.end} за Києвом.`);
    return;
  }

  const runningView = document.getElementById("runningView");
  const stoppedView = document.getElementById("stoppedView");
  const badge = document.getElementById("headerStatusBadge");
  const statusText = document.getElementById("headerStatusText");
  const timerEl = document.getElementById("liveTimer");

  // Optimistic UI switch: immediately show running and timer 00:00:00
  if (stoppedView) stoppedView.style.display = "none";
  if (runningView) runningView.style.display = "block";
  if (badge) badge.className = "status-badge running";
  if (statusText) statusText.innerText = "В РОБОТІ";
  if (timerEl) timerEl.innerText = "00:00:00";

  // Start live timer from now (00:00:00)
  startLiveStopwatch(new Date().toISOString());

  try {
    const res = await apiCall("/api/generator/start", "POST", { custom_time: "зараз" });
    haptic("success");
    if (res?.data?.start_time) {
      startLiveStopwatch(res.data.start_time);
    }
    await loadStatus();
  } catch (err) {
    haptic("error");
    // Revert optimistic UI on error
    stopLiveStopwatch();
    if (stoppedView) stoppedView.style.display = "block";
    if (runningView) runningView.style.display = "none";
    if (badge) badge.className = "status-badge stopped";
    if (statusText) statusText.innerText = "ЗУПИНЕНО";
    alert(err.message);
    await loadStatus();
  }
}

function openStopModal() {
  document.getElementById("stopCustomTimeInput").value = "";
  document.getElementById("stopNotesInput").value = "";
  openModal("stopModal");
}

function openRefuelModal() {
  document.getElementById("refuelAmountInput").value = "";
  document.getElementById("refuelCostInput").value = "";
  document.getElementById("refuelNotesInput").value = "";
  openModal("refuelModal");
}

function openMaintModal() {
  document.getElementById("maintDescInput").value = "Заміна моторної оливи та масляного фільтру";
  document.getElementById("maintPartsInput").value = "";
  document.getElementById("maintCostInput").value = "";
  openModal("maintModal");
}

function openIntermediateMaintModal(type = "spark_plugs", defaultDesc = "") {
  const typeSelect = document.getElementById("interMaintTypeSelect");
  if (typeSelect) typeSelect.value = type;
  const descEl = document.getElementById("interMaintDescInput");
  if (descEl) descEl.value = defaultDesc || "";
  document.getElementById("interMaintPartsInput").value = "";
  document.getElementById("interMaintCostInput").value = "";
  openModal("intermediateMaintModal");
}

function onInterMaintTypeChange() {
  const type = document.getElementById("interMaintTypeSelect").value;
  const descEl = document.getElementById("interMaintDescInput");
  const titles = {
    spark_plugs: "Заміна свічок запалювання",
    air_filter: "Заміна / обслуговування повітряного фільтру",
    fuel_filter: "Заміна паливного фільтру тонкої очистки",
    battery: "Перевірка рівня електроліту та зарядка АКБ",
    other: "Проміжне обслуговування"
  };
  if (!descEl.value || Object.values(titles).includes(descEl.value)) {
    descEl.value = titles[type] || "";
  }
}

async function submitIntermediateMaint() {
  const maintType = document.getElementById("interMaintTypeSelect").value;
  const desc = document.getElementById("interMaintDescInput").value.trim();
  if (!desc) {
    alert("Будь ласка, вкажіть опис виконаних робіт!");
    return;
  }
  const parts = document.getElementById("interMaintPartsInput").value.trim() || null;
  const cost = parseFloat(document.getElementById("interMaintCostInput").value) || null;

  closeModal("intermediateMaintModal");
  haptic("medium");

  try {
    const res = await apiCall("/api/maintenance/perform", "POST", {
      description: desc,
      is_main: false,
      maint_type: maintType,
      parts_replaced: parts,
      cost: cost
    });
    haptic("success");
    alert(res.message || "Проміжне ТО успішно зафіксовано!");
    await loadStatus();
    loadMaintHistory();
  } catch (err) {
    haptic("error");
    alert(err.message);
  }
}

function openResetModal() {
  document.getElementById("resetTypeSelect").value = "fuel_zero";
  document.getElementById("resetReasonInput").value = "";
  openModal("resetModal");
}

async function submitResetCounters() {
  const resetType = document.getElementById("resetTypeSelect").value;
  const reason = document.getElementById("resetReasonInput").value.trim();

  if (!reason || reason.length < 5) {
    alert("Вкажіть обов'язково причину скидання (мінімум 5 символів)!");
    return;
  }

  const confirmMsg = "УВАГА: Ця дія скине вибрані лічильники і буде збережена в журналі безпеки з вашим ім'ям. Продовжити?";
  if (!confirm(confirmMsg)) return;

  closeModal("resetModal");
  haptic("heavy");

  try {
    const res = await apiCall("/api/admin/reset", "POST", {
      reset_type: resetType,
      reason: reason
    });
    haptic("success");
    alert(res.message || "Скидання виконано!");
    await loadStatus();
    loadAuditLogs();
  } catch (err) {
    haptic("error");
    alert(err.message);
  }
}

function setStopTimeOffset(mins) {
  haptic("light");
  document.getElementById("stopCustomTimeInput").value = mins === 0 ? "Зараз" : `-${mins} хв`;
}

async function submitStopGenerator() {
  haptic("medium");
  const timeVal = document.getElementById("stopCustomTimeInput").value.trim();
  const notes = document.getElementById("stopNotesInput").value.trim();
  closeModal("stopModal");

  try {
    const res = await apiCall("/api/generator/stop", "POST", { custom_time: timeVal, notes: notes });
    haptic("success");
    await loadStatus();
  } catch (err) {
    haptic("error");
    alert(err.message);
  }
}

async function submitRefuel() {
  const amount = parseFloat(document.getElementById("refuelAmountInput").value);
  if (!amount || amount <= 0) {
    alert("Будь ласка, вкажіть коректний об'єм пального!");
    return;
  }
  const delivered_by = document.getElementById("refuelDeliveredByInput")?.value?.trim() || null;
  const receipt_number = document.getElementById("refuelReceiptInput")?.value?.trim() || null;
  const cost = parseFloat(document.getElementById("refuelCostInput").value) || null;
  const notes = document.getElementById("refuelNotesInput").value.trim() || null;

  closeModal("refuelModal");
  haptic("medium");

  try {
    await apiCall("/api/fuel/add", "POST", {
      amount_liters: amount,
      delivered_by,
      receipt_number,
      cost,
      notes
    });
    haptic("success");
    await loadStatus();
    loadFuelHistory();
  } catch (err) {
    haptic("error");
    alert(err.message);
  }
}

async function submitMaintenance() {
  const desc = document.getElementById("maintDescInput").value.trim();
  if (!desc) {
    alert("Будь ласка, опишіть виконані роботи!");
    return;
  }
  const parts = document.getElementById("maintPartsInput").value.trim() || null;
  const cost = parseFloat(document.getElementById("maintCostInput").value) || null;

  closeModal("maintModal");
  haptic("medium");

  try {
    await apiCall("/api/maintenance/perform", "POST", { description: desc, parts_replaced: parts, cost, is_main: true });
    haptic("success");
    await loadStatus();
    loadMaintHistory();
  } catch (err) {
    haptic("error");
    alert(err.message);
  }
}

// Data loaders for tabs
async function loadFuelHistory() {
  const container = document.getElementById("fuelHistoryList");
  try {
    const list = await apiCall("/api/reports/fuel");
    if (!list || list.length === 0) {
      container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Записів заправок немає</div>';
      return;
    }
    container.innerHTML = list.map(item => `
      <div class="list-item">
        <div>
          <div class="list-item-title">+${item.amount_liters} л ${item.cost ? `(${item.cost} ₴)` : ''}</div>
          <div class="list-item-sub">${item.timestamp_formatted} • ${item.user_name || 'Оператор'}</div>
          ${item.delivered_by || item.receipt_number ? `
            <div style="font-size: 11px; color: var(--link-color); margin-top: 2px;">
              🚚 ${item.delivered_by ? `Привіз: <b>${item.delivered_by}</b>` : ''} ${item.receipt_number ? `• Чек: <b>${item.receipt_number}</b>` : ''}
            </div>
          ` : ''}
          ${item.notes ? `<div style="font-size: 11px; color: var(--hint-color); margin-top: 2px;">💬 ${item.notes}</div>` : ''}
        </div>
        <div class="list-item-right">
          <div class="list-item-val" style="color: var(--link-color);">${item.fuel_after} л</div>
          <div style="font-size: 11px; color: var(--hint-color);">в баку</div>
        </div>
      </div>
    `).join("");
  } catch (e) {
    container.innerHTML = '<div style="color: var(--accent-red); font-size: 13px; text-align: center; padding: 12px;">Помилка завантаження</div>';
  }
}

async function loadMaintHistory() {
  const container = document.getElementById("maintHistoryList");
  try {
    const list = await apiCall("/api/reports/maintenance");
    if (!list || list.length === 0) {
      container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Записів ТО немає</div>';
      return;
    }
    container.innerHTML = list.map(item => {
      const isMain = item.is_main !== false;
      const typeBadge = isMain
        ? '<span style="color: var(--accent-green); font-weight: 700; font-size: 11px; margin-left: 6px;">[🟢 Олива]</span>'
        : '<span style="color: var(--link-color); font-weight: 700; font-size: 11px; margin-left: 6px;">[🔧 Проміжне]</span>';
      return `
        <div class="list-item">
          <div>
            <div class="list-item-title">
              ТО: ${item.hours_at_maintenance} мч ${typeBadge}
            </div>
            <div class="list-item-sub">${item.timestamp_formatted} • 👤 ${item.user_name || 'Виконавець'}</div>
            <div style="font-size: 12px; margin-top: 4px;">🔧 ${item.description}</div>
            ${item.parts_replaced ? `<div style="font-size: 11px; color: var(--hint-color); margin-top: 2px;">⚙️ ${item.parts_replaced}</div>` : ''}
          </div>
          <div class="list-item-right">
            ${item.cost ? `<div class="list-item-val">${item.cost} ₴</div>` : ''}
            ${isMain ? `<div style="font-size: 11px; color: var(--hint-color);">наст: ${item.next_maintenance_hours} мч</div>` : ''}
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    container.innerHTML = '<div style="color: var(--accent-red); font-size: 13px; text-align: center; padding: 12px;">Помилка завантаження</div>';
  }
}

let fuelChartInstance = null;

function renderFuelChart(data) {
  const ctx = document.getElementById('fuelChart');
  if (!ctx) return;
  
  if (fuelChartInstance) {
    fuelChartInstance.destroy();
  }
  
  const textColor = getComputedStyle(document.documentElement).getPropertyValue('--text-color').trim() || '#0f172a';
  const gridColor = getComputedStyle(document.documentElement).getPropertyValue('--card-border').trim() || 'rgba(0,0,0,0.05)';

  fuelChartInstance = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.labels,
      datasets: [
        {
          label: 'Витрата (л)',
          data: data.fuel,
          backgroundColor: 'rgba(239, 68, 68, 0.8)',
          borderRadius: 4,
          yAxisID: 'y'
        },
        {
          label: 'Робота (год)',
          data: data.hours,
          backgroundColor: 'rgba(2, 132, 199, 0.8)',
          borderRadius: 4,
          yAxisID: 'y1'
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      color: textColor,
      plugins: {
        legend: {
          labels: { color: textColor, boxWidth: 12 }
        }
      },
      scales: {
        x: {
          grid: { color: gridColor },
          ticks: { color: textColor }
        },
        y: {
          type: 'linear',
          display: true,
          position: 'left',
          grid: { color: gridColor },
          ticks: { color: textColor }
        },
        y1: {
          type: 'linear',
          display: true,
          position: 'right',
          grid: { drawOnChartArea: false },
          ticks: { color: textColor }
        }
      }
    }
  });
}

async function loadReports() {
  try {
    const summary = await apiCall("/api/reports/summary");
    document.getElementById("todayDateStr").innerText = summary.today_date;
    document.getElementById("repTodayHours").innerText = summary.today_duration_str;
    document.getElementById("repTodayFuel").innerText = `${summary.today_fuel} л`;
    document.getElementById("repTodayRefuel").innerText = `${summary.today_refuel} л`;
    document.getElementById("repTodayRuns").innerText = summary.today_runs_count;

    document.getElementById("repMonthHours").innerText = summary.month_duration_str;
    document.getElementById("repMonthFuel").innerText = `${summary.month_fuel} л`;

    // Render Chart
    try {
      const chartData = await apiCall("/api/reports/chart-data?days=7");
      renderFuelChart(chartData);
    } catch (e) {
      console.error("Chart error:", e);
    }

    const runsList = await apiCall("/api/reports/runs");
    const container = document.getElementById("runsHistoryList");
    if (!runsList || runsList.length === 0) {
      container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Сесій запусків немає</div>';
      return;
    }
    container.innerHTML = runsList.map(r => `
      <div class="list-item">
        <div>
          <div class="list-item-title">⏱ ${r.duration_str}</div>
          <div class="list-item-sub">${r.start_formatted} — ${r.stop_formatted}</div>
          <div style="font-size: 11px; color: var(--hint-color); margin-top: 2px;">👤 ${r.stop_user_name || r.start_user_name || 'Оператор'}</div>
        </div>
        <div class="list-item-right">
          <div class="list-item-val" style="color: var(--accent-red);">- ${r.fuel_consumed} л</div>
          <div style="font-size: 11px; color: var(--hint-color);">разом: ${r.total_hours_after} мч</div>
        </div>
      </div>
    `).join("");
  } catch (e) {
    console.error("Помилка завантаження звітів:", e);
  }
}

function downloadExcelReport() {
  haptic("medium");
  window.open("/api/reports/excel", "_blank");
}

// Admin settings handlers
async function saveCalibHours() {
  const val = parseFloat(document.getElementById("calibHoursInput").value);
  if (isNaN(val) || val < 0) return alert("Вкажіть число!");
  await saveAdminSetting({ total_hours: val });
}

async function saveCalibFuel() {
  const val = parseFloat(document.getElementById("calibFuelInput").value);
  if (isNaN(val) || val < 0) return alert("Вкажіть число!");
  await saveAdminSetting({ current_fuel: val });
}

async function saveCalibRate() {
  const val = parseFloat(document.getElementById("calibRateInput").value);
  if (isNaN(val) || val <= 0) return alert("Вкажіть число більше 0!");
  await saveAdminSetting({ fuel_rate: val });
}

async function saveCalibTank() {
  const val = parseFloat(document.getElementById("calibTankInput").value);
  if (isNaN(val) || val <= 0) return alert("Вкажіть число більше 0!");
  await saveAdminSetting({ tank_capacity: val });
}

async function saveCalibInterval() {
  const val = parseFloat(document.getElementById("calibIntervalInput").value);
  if (isNaN(val) || val <= 0) return alert("Вкажіть число більше 0!");
  await saveAdminSetting({ maintenance_interval: val });
}

async function saveAdminSetting(payload) {
  haptic("medium");
  try {
    await apiCall("/api/admin/settings", "POST", payload);
    haptic("success");
    alert("Параметр успішно збережено!");
    await loadStatus();
  } catch (e) {
    haptic("error");
    alert(e.message);
  }
}

let allUsersData = [];

async function loadAuditLogs() {
  const container = document.getElementById("auditHistoryList");
  if (!container) return;
  try {
    const logs = await apiCall("/api/reports/audit");
    if (!logs || logs.length === 0) {
      container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Записів аудиту немає</div>';
      return;
    }
    const typeLabels = {
      all: "💥 Повне скидання",
      fuel_zero: "⛽ Обнулення бака",
      hours_zero: "⏱ Обнулення мотогодин",
      maint_main: "🛠 Скидання ТО",
      maint_intermediate: "🔧 Проміжне скидання"
    };
    container.innerHTML = logs.map(a => `
      <div class="list-item">
        <div>
          <div class="list-item-title" style="color: var(--accent-red);">${typeLabels[a.reset_type] || a.reset_type}</div>
          <div class="list-item-sub">${a.timestamp} • 👤 ${a.user_name}</div>
          <div style="font-size: 12px; margin-top: 3px;">📝 Причина: <i>${a.reason}</i></div>
          ${a.details ? `<div style="font-size: 11px; color: var(--hint-color); margin-top: 2px;">ℹ️ ${a.details}</div>` : ''}
        </div>
      </div>
    `).join("");
  } catch (e) {
    container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Немає доступу до аудиту</div>';
  }
}

async function loadUsers() {
  const container = document.getElementById("usersList");
  try {
    const users = await apiCall("/api/users");
    allUsersData = users;
    const badgeCount = document.getElementById("usersCountBadge");
    if (badgeCount) badgeCount.innerText = `${users.length} користувачів`;

    if (!users || users.length === 0) {
      container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Користувачів не знайдено</div>';
      return;
    }
    container.innerHTML = users.map(u => {
      const roleBadge = u.role === "admin"
        ? '<span style="color: var(--accent-yellow); font-weight: 700;">👑 Адмін</span>'
        : (u.role === "operator"
          ? '<span style="color: var(--accent-green); font-weight: 700;">👤 Оператор</span>'
          : (u.role === "pending"
            ? '<span style="color: var(--hint-color); font-weight: 700;">⏳ Очікує</span>'
            : '<span style="color: var(--accent-red); font-weight: 700;">⛔ Заблоковано</span>'));

      const nameDisplay = u.custom_name
        ? `<b style="color: var(--text-color);">${u.custom_name}</b> <span style="color: var(--hint-color); font-size: 12px;">(${u.full_name || 'ТГ'})</span>`
        : `<b style="color: var(--text-color);">${u.full_name || 'Без імені'}</b>`;

      return `
        <div class="list-item" style="flex-direction: column; align-items: stretch; gap: 8px; padding: 12px 0;">
          <div style="display: flex; justify-content: space-between; align-items: flex-start;">
            <div>
              <div class="list-item-title">${nameDisplay} ${u.username ? `<span style="color: var(--link-color); font-size: 12px;">@${u.username}</span>` : ''}</div>
              <div class="list-item-sub">ID: ${u.user_id} • ${roleBadge}</div>
            </div>
            <button class="btn-mini" onclick="openEditUserNameModal(${u.user_id})">✏️ Системне ім'я</button>
          </div>
          <div style="display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-end;">
            ${u.role !== 'operator' ? `<button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="changeRole(${u.user_id}, 'operator')">Схвалити (Оператор)</button>` : ''}
            ${u.role !== 'admin' ? `<button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="changeRole(${u.user_id}, 'admin')">Зробити адміном</button>` : ''}
            ${u.role !== 'blocked' ? `<button class="btn-secondary" style="padding: 4px 10px; font-size: 11px; color: var(--accent-red);" onclick="changeRole(${u.user_id}, 'blocked')">Блокувати</button>` : `<button class="btn-secondary" style="padding: 4px 10px; font-size: 11px;" onclick="changeRole(${u.user_id}, 'operator')">Розблокувати</button>`}
          </div>
        </div>
      `;
    }).join("");
    loadAuditLogs();
  } catch (e) {
    container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Немає доступу до списку користувачів</div>';
  }
}

function openEditUserNameModal(userId) {
  const user = allUsersData.find(u => u.user_id === userId);
  if (!user) return;
  document.getElementById("editUserIdInput").value = userId;
  document.getElementById("editUserTgInfo").innerText = `${user.full_name || 'Без імені'} (@${user.username || 'немає'}) [ID: ${user.user_id}]`;
  document.getElementById("editCustomNameInput").value = user.custom_name || "";
  openModal("editUserNameModal");
  setTimeout(() => {
    const input = document.getElementById("editCustomNameInput");
    if (input) {
      input.focus();
      input.select();
    }
  }, 100);
}

async function submitCustomUserName() {
  const userId = parseInt(document.getElementById("editUserIdInput").value);
  const customName = document.getElementById("editCustomNameInput").value.trim();

  closeModal("editUserNameModal");
  haptic("medium");

  try {
    await apiCall("/api/users/custom-name", "POST", {
      user_id: userId,
      custom_name: customName
    });
    haptic("success");
    alert("✅ Системне ім'я збережено!");
    await loadStatus();
    loadUsers();
  } catch (e) {
    haptic("error");
    alert(e.message);
  }
}

async function saveMyProfileName() {
  const input = document.getElementById("myCustomNameInput");
  const val = input ? input.value.trim() : "";
  if (!currentStatus?.current_user?.user_id) {
    alert("Помилка: користувач не ідентифікований");
    return;
  }
  haptic("medium");
  try {
    await apiCall("/api/users/custom-name", "POST", {
      user_id: currentStatus.current_user.user_id,
      custom_name: val
    });
    haptic("success");
    alert("✅ Ваше системне ім'я успішно оновлено!");
    await loadStatus();
    loadUsers();
  } catch (e) {
    haptic("error");
    alert("❌ Помилка збереження: " + e.message);
  }
}

async function changeRole(userId, newRole) {
  haptic("medium");
  try {
    await apiCall("/api/users/role", "POST", { user_id: userId, role: newRole });
    haptic("success");
    loadUsers();
  } catch (e) {
    haptic("error");
    alert(e.message);
  }
}

// Initial load and periodic polling
loadStatus();
setInterval(() => {
  if (currentStatus?.is_running) {
    loadStatus();
  }
}, 4000);
setInterval(() => {
  if (!currentStatus?.is_running) {
    loadStatus();
  }
}, 15000);
