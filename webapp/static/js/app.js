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

    // Tab 5 Settings sync placeholders
    document.getElementById("calibHoursInput").placeholder = data.base_total_hours;
    document.getElementById("calibFuelInput").placeholder = data.current_fuel;
    document.getElementById("calibRateInput").placeholder = data.fuel_rate;
    document.getElementById("calibTankInput").placeholder = data.tank_capacity;
    document.getElementById("calibIntervalInput").placeholder = data.maintenance_interval_hours;

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

// Immediate Stop Generator (no modal prompt)
async function stopGeneratorImmediately() {
  haptic("medium");

  const runningView = document.getElementById("runningView");
  const stoppedView = document.getElementById("stoppedView");
  const badge = document.getElementById("headerStatusBadge");
  const statusText = document.getElementById("headerStatusText");

  // Optimistic UI switch: immediately show stopped view and stop stopwatch
  stopLiveStopwatch();
  if (runningView) runningView.style.display = "none";
  if (stoppedView) stoppedView.style.display = "block";
  if (badge) badge.className = "status-badge stopped";
  if (statusText) statusText.innerText = "ЗУПИНЕНО";

  try {
    const res = await apiCall("/api/generator/stop", "POST", { custom_time: "зараз" });
    haptic("success");
    await loadStatus();
  } catch (err) {
    haptic("error");
    // Revert optimistic UI on error
    if (currentStatus?.is_running) {
      if (stoppedView) stoppedView.style.display = "none";
      if (runningView) runningView.style.display = "block";
      if (badge) badge.className = "status-badge running";
      if (statusText) statusText.innerText = "В РОБОТІ";
      if (currentStatus?.current_start_time) {
        startLiveStopwatch(currentStatus.current_start_time);
      }
    }
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
