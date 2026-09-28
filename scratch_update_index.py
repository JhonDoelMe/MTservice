import re

with open('webapp/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add Wizard Card in Settings
wizard_card = '''
      <div class="card admin-only" style="display: none;">
        <div class="card-header">
          <span class="card-title">🏢 Управління об'єктами</span>
        </div>
        <div style="font-size: 13px; color: var(--hint-color); margin-bottom: 12px; line-height: 1.4;">
          Додайте новий генератор або об'єкт. Після створення ви зможете перемикатися між ними у шапці додатку.
        </div>
        <button class="btn-primary" style="width: 100%; background: linear-gradient(135deg, #10b981 0%, #059669 100%);" onclick="openWizardModal()">
          ➕ Додати новий об'єкт/генератор
        </button>
      </div>
'''
text = text.replace('      <div class="card">\n        <div class="card-header">\n          <span class="card-title">🎨', wizard_card + '\n      <div class="card">\n        <div class="card-header">\n          <span class="card-title">🎨')

# 2. Add Wizard Modal HTML
wizard_modal = '''
  <!-- Wizard Modal -->
  <div class="modal-overlay" id="wizardModal">
    <div class="modal-content" style="max-height: 90vh; overflow-y: auto;">
      <h3 class="modal-title">➕ Додати об'єкт</h3>
      
      <div class="form-group">
        <label class="form-label">Назва об'єкту (або генератора):</label>
        <input type="text" id="wizName" class="form-input" placeholder="напр. Офіс Київ - Ген 1" required>
      </div>
      
      <div class="form-group">
        <label class="form-label">Тип пального:</label>
        <select id="wizFuelType" class="form-input" style="appearance: auto;">
          <option value="ДП">ДП (Дизель)</option>
          <option value="А-95">Бензин А-95</option>
          <option value="А-92">Бензин А-92</option>
        </select>
      </div>
      
      <div class="form-group">
        <label class="form-label">Об'єм баку (л):</label>
        <input type="text" inputmode="decimal" id="wizTank" class="form-input" placeholder="напр. 150">
      </div>
      
      <div class="form-group">
        <label class="form-label">Паспортна витрата (л/год):</label>
        <input type="text" inputmode="decimal" id="wizRate" class="form-input" placeholder="напр. 4.5">
      </div>
      
      <div class="form-group">
        <label class="form-label">Поточні мотогодини:</label>
        <input type="text" inputmode="decimal" id="wizHours" class="form-input" placeholder="напр. 0">
      </div>
      
      <div class="form-group">
        <label class="form-label">Поточний залишок у баку (л):</label>
        <input type="text" inputmode="decimal" id="wizFuel" class="form-input" placeholder="напр. 0">
      </div>
      
      <div class="form-group">
        <label class="form-label">Інтервал ТО (мч):</label>
        <input type="text" inputmode="decimal" id="wizMaint" class="form-input" value="250">
      </div>

      <div style="display: flex; gap: 8px; margin-top: 24px;">
        <button class="btn-secondary" style="flex: 1;" onclick="closeModal('wizardModal')">Скасувати</button>
        <button class="btn-primary" style="flex: 1;" onclick="submitWizard()">Створити</button>
      </div>
    </div>
  </div>
'''

text = text.replace('  <!-- Notification Toast -->', wizard_modal + '\n  <!-- Notification Toast -->')

with open('webapp/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(text)
    
print("Added UI elements")
