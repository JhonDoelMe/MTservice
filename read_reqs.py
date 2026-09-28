import os

dir_path = r"C:\Users\Anubis\.gemini\antigravity\worktrees\MTservice\generator_telegram_bot_setup"

def read_file(filepath):
    path = os.path.join(dir_path, filepath)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.readlines()
    except Exception as e:
        return [f"Error reading file: {e}\n"]

def print_lines(lines, start=1):
    for i, line in enumerate(lines, start):
        print(f"{i}: {line}", end='')

# 1
print("--- 1. bot/database/models.py ---")
print_lines(read_file('bot/database/models.py'))

# 2
print("\n--- 2. bot/services/generator_service.py ---")
lines = read_file('bot/services/generator_service.py')
target_methods = ['def start_generator', 'def stop_generator', 'def add_fuel', 'def perform_maintenance', 'def reset_counters', 'def calibrate_counters']
i = 0
while i < len(lines):
    if any(lines[i].lstrip().startswith(m) for m in target_methods):
        for j in range(i, min(i+6, len(lines))):
            print(f"{j+1}: {lines[j]}", end='')
        print("...")
        i += 6
    else:
        i += 1

# 3
print("\n--- 3. webapp/server.py ---")
lines = read_file('webapp/server.py')
for i, line in enumerate(lines):
    if 'GeneratorService' in line and any(m in line for m in ['start_generator', 'stop_generator', 'add_fuel', 'perform_maintenance', 'reset_counters', 'calibrate_counters']):
        start = max(0, i-5)
        end = min(len(lines), i+6)
        print(f"\nMatch at line {i+1}:")
        for j in range(start, end):
            print(f"{j+1}: {lines[j]}", end='')

# 4
print("\n--- 4. bot/services/notify_service.py ---")
print_lines(read_file('bot/services/notify_service.py'))

# 5
print("\n--- 5. webapp/static/css/style.css ---")
lines = read_file('webapp/static/css/style.css')
if len(lines) >= 770:
    for i in range(749, 770):
        print(f"{i+1}: {lines[i]}", end='')
else:
    print(f"File shorter than 770 lines, total lines: {len(lines)}")

# 6
print("\n--- 6. webapp/static/js/app.js ---")
lines = read_file('webapp/static/js/app.js')
start = max(0, len(lines)-120)
for i in range(start, len(lines)):
    print(f"{i+1}: {lines[i]}", end='')

print("\n--- app.js search ---")
for i, line in enumerate(lines):
    if 'showToast' in line or 'toast' in line:
        print(f"{i+1}: {line}", end='')

# 7
print("\n--- 7. webapp/templates/index.html ---")
lines = read_file('webapp/templates/index.html')
for i, line in enumerate(lines):
    if 'wizardModal' in line or 'Notification Toast' in line:
        print(f"{i+1}: {line}", end='')

