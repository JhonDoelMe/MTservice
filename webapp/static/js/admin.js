// --- ADMIN, MAINTENANCE & REPORTS MODULE ---

// 1. Проміжні ТО
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

// 2. Скидання лічильників
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

// 3. Звіти (Reports)
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

// 4. Калібрування параметрів генератора
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

async function saveCalibWarning() {
  const val = parseFloat(document.getElementById("calibWarningInput").value);
  if (isNaN(val) || val <= 0) return alert("Вкажіть число більше 0!");
  await saveAdminSetting({ warning_hours: val });
}

async function saveWorkHoursSettings() {
  const enabled = document.getElementById("workHoursEnabledInput").checked;
  const start = document.getElementById("workStartInput").value || "08:00";
  const end = document.getElementById("workEndInput").value || "20:00";
  await saveAdminSetting({
    work_hours_enabled: enabled,
    work_start_time: start,
    work_end_time: end
  });
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

// 5. Журнал аудиту та безпеки
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

// 6. Керування користувачами та системними іменами
let allUsersData = [];

async function loadUsers() {
  const container = document.getElementById("usersList");
  if (!container) return;
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
    alert("Системне ім'я збережено!");
    loadUsers();
    loadStatus();
  } catch (e) {
    haptic("error");
    alert(e.message);
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
