import re

with open('webapp/static/js/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

# Update loadStatus to call loadGeneratorsList if admin, and handle admin-only panels
if 'function loadStatus()' in text:
    pass

# We will just append the new JS logic.
new_js = '''
// --- MULTI-GENERATOR SUPPORT ---

async function loadGeneratorsList() {
  try {
    const data = await apiCall('/api/generators');
    const select = document.getElementById('globalGenSelect');
    if (!select) return;
    
    // Remember current selection
    const currentVal = window.currentGenId;
    
    select.innerHTML = '';
    data.forEach(gen => {
      const opt = document.createElement('option');
      opt.value = gen.id;
      opt.text = gen.name;
      if (gen.is_running) opt.text += ' (Працює)';
      select.appendChild(opt);
    });
    
    // Restore or select first
    if (data.find(g => g.id == currentVal)) {
      select.value = currentVal;
    } else if (data.length > 0) {
      select.value = data[0].id;
      window.currentGenId = data[0].id;
      localStorage.setItem('currentGenId', window.currentGenId);
    }
  } catch (e) {
    console.error('Failed to load generators list', e);
  }
}

async function switchGenerator() {
  const select = document.getElementById('globalGenSelect');
  if (!select) return;
  const newId = parseInt(select.value);
  if (newId && newId !== window.currentGenId) {
    window.currentGenId = newId;
    localStorage.setItem('currentGenId', newId);
    showToast('Перемикання об\\'єкту...');
    await loadStatus(); // Reload everything for new gen
  }
}

function openWizardModal() {
  document.getElementById('wizName').value = '';
  document.getElementById('wizTank').value = '';
  document.getElementById('wizRate').value = '';
  document.getElementById('wizHours').value = '';
  document.getElementById('wizFuel').value = '';
  openModal('wizardModal');
}

async function submitWizard() {
  const name = document.getElementById('wizName').value.trim();
  const fType = document.getElementById('wizFuelType').value;
  const tank = parseFloat(document.getElementById('wizTank').value.replace(',', '.')) || 150.0;
  const rate = parseFloat(document.getElementById('wizRate').value.replace(',', '.')) || 4.5;
  const hours = parseFloat(document.getElementById('wizHours').value.replace(',', '.')) || 0.0;
  const fuel = parseFloat(document.getElementById('wizFuel').value.replace(',', '.')) || 0.0;
  const maint = parseFloat(document.getElementById('wizMaint').value.replace(',', '.')) || 250.0;

  if (!name) return alert("Введіть назву!");
  
  const body = {
    name: name,
    fuel_type: fType,
    tank_capacity: tank,
    fuel_rate: rate,
    total_hours: hours,
    current_fuel: fuel,
    maintenance_interval: maint
  };

  try {
    const res = await apiCall('/api/generators', 'POST', body);
    closeModal('wizardModal');
    haptic('success');
    showToast('Об\\'єкт успішно створено!');
    window.currentGenId = res.id;
    localStorage.setItem('currentGenId', res.id);
    await loadGeneratorsList();
    await loadStatus();
  } catch (e) {
    haptic('error');
    alert(e.message);
  }
}

// Call loadGeneratorsList on start
document.addEventListener("DOMContentLoaded", () => {
  loadGeneratorsList();
});
'''

text = text + '\n' + new_js

# Ensure admin-only cards show properly
# in loadStatus, there is:
text = text.replace(
    'if (data.current_user.role === \'admin\') {',
    'if (data.current_user.role === \'admin\') {\n      document.querySelectorAll(".admin-only").forEach(el => el.style.display = "");\n      loadGeneratorsList();'
)

with open('webapp/static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("app.js updated")
