// Telegram WebApp SDK initialization
const tg = window.Telegram?.WebApp;

if (tg) {
  tg.expand();
  tg.ready();
  if (tg.enableClosingConfirmation) {
    tg.enableClosingConfirmation();
  }
}

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

// Live Running Stopwatch
function startLiveStopwatch(startTimeIso) {
  if (liveTimerInterval) clearInterval(liveTimerInterval);
  activeStartTime = new Date(startTimeIso).getTime();

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

// Render Dashboard
async function loadStatus() {
  try {
    const data = await apiCall("/api/status");
    currentStatus = data;

    // Header
    document.getElementById("genName").innerText = data.name;
    const badge = document.getElementById("headerStatusBadge");
    const statusText = document.getElementById("headerStatusText");

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

    // Metrics
    document.getElementById("totalHoursVal").innerText = `${data.total_hours.toFixed(2)} мч`;
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

    // Tab 2 Fuel sync
    document.getElementById("fuelTabAmount").innerText = `${data.current_fuel} л (${Math.round(data.fuel_pct)}%)`;
    document.getElementById("fuelTabCap").innerText = `Ємність бака: ${data.tank_capacity} л (витрата: ${data.fuel_rate} л/год)`;

    // Tab 3 Maint sync
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

    // Tab 5 Settings sync placeholders
    document.getElementById("calibHoursInput").placeholder = data.base_total_hours;
    document.getElementById("calibFuelInput").placeholder = data.current_fuel;
    document.getElementById("calibRateInput").placeholder = data.fuel_rate;
    document.getElementById("calibTankInput").placeholder = data.tank_capacity;
    document.getElementById("calibIntervalInput").placeholder = data.maintenance_interval_hours;

  } catch (e) {
    console.error("Помилка оновлення статусу:", e);
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

function openStartModal() {
  document.getElementById("startCustomTimeInput").value = "";
  openModal("startModal");
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
  document.getElementById("maintDescInput").value = "";
  document.getElementById("maintPartsInput").value = "";
  document.getElementById("maintCostInput").value = "";
  openModal("maintModal");
}

function setStartTimeOffset(mins) {
  haptic("light");
  document.getElementById("startCustomTimeInput").value = mins === 0 ? "Зараз" : `-${mins} хв`;
}

function setStopTimeOffset(mins) {
  haptic("light");
  document.getElementById("stopCustomTimeInput").value = mins === 0 ? "Зараз" : `-${mins} хв`;
}

// Action Submissions
async function submitStartGenerator() {
  haptic("medium");
  const timeVal = document.getElementById("startCustomTimeInput").value.trim();
  closeModal("startModal");

  try {
    const res = await apiCall("/api/generator/start", "POST", { custom_time: timeVal });
    haptic("success");
    await loadStatus();
  } catch (err) {
    haptic("error");
    alert(err.message);
  }
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
  const cost = parseFloat(document.getElementById("refuelCostInput").value) || null;
  const notes = document.getElementById("refuelNotesInput").value.trim() || null;

  closeModal("refuelModal");
  haptic("medium");

  try {
    await apiCall("/api/fuel/add", "POST", { amount_liters: amount, cost, notes });
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
    await apiCall("/api/maintenance/perform", "POST", { description: desc, parts_replaced: parts, cost });
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
    container.innerHTML = list.map(item => `
      <div class="list-item">
        <div>
          <div class="list-item-title">ТО на позначці ${item.hours_at_maintenance} мч</div>
          <div class="list-item-sub">${item.timestamp_formatted} • ${item.user_name || 'Виконавець'}</div>
          <div style="font-size: 12px; margin-top: 4px;">🔧 ${item.description}</div>
          ${item.parts_replaced ? `<div style="font-size: 11px; color: var(--hint-color);">⚙️ ${item.parts_replaced}</div>` : ''}
        </div>
        <div class="list-item-right">
          ${item.cost ? `<div class="list-item-val">${item.cost} ₴</div>` : ''}
          <div style="font-size: 11px; color: var(--hint-color);">наст: ${item.next_maintenance_hours} мч</div>
        </div>
      </div>
    `).join("");
  } catch (e) {
    container.innerHTML = '<div style="color: var(--accent-red); font-size: 13px; text-align: center; padding: 12px;">Помилка завантаження</div>';
  }
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

async function loadUsers() {
  const container = document.getElementById("usersList");
  try {
    const users = await apiCall("/api/users");
    if (!users || users.length === 0) {
      container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Користувачів не знайдено</div>';
      return;
    }
    container.innerHTML = users.map(u => {
      const roleBadge = u.role === "admin" ? "👑 Адмін" : (u.role === "operator" ? "👤 Оператор" : (u.role === "pending" ? "⏳ Очікує" : "⛔ Блок"));
      return `
        <div class="list-item">
          <div>
            <div class="list-item-title">${u.full_name || 'Без імені'} ${u.username ? `(@${u.username})` : ''}</div>
            <div class="list-item-sub">ID: ${u.user_id} • ${roleBadge}</div>
          </div>
          <div>
            ${u.role !== 'operator' ? `<button class="btn-secondary" style="padding: 4px 8px; font-size: 11px;" onclick="changeRole(${u.user_id}, 'operator')">Одобрити</button>` : ''}
            ${u.role !== 'admin' ? `<button class="btn-secondary" style="padding: 4px 8px; font-size: 11px; margin-left: 4px;" onclick="changeRole(${u.user_id}, 'admin')">Адмін</button>` : ''}
          </div>
        </div>
      `;
    }).join("");
  } catch (e) {
    container.innerHTML = '<div style="color: var(--hint-color); font-size: 13px; text-align: center; padding: 12px;">Немає доступу до списку користувачів</div>';
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
