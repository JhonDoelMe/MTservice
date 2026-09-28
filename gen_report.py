import os
import sys

sys.stdout.reconfigure(encoding='utf-8')

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

with open("report.txt", "w", encoding="utf-8") as out:
    def write(s):
        out.write(s)
        
    write("--- 1. bot/database/models.py ---\n")
    lines = read_file('bot/database/models.py')
    for i, line in enumerate(lines, 1):
        write(f"{i}: {line}")

    write("\n--- 2. bot/services/generator_service.py ---\n")
    lines = read_file('bot/services/generator_service.py')
    target_methods = ['start_generator', 'stop_generator', 'add_fuel', 'perform_maintenance', 'reset_counters', 'calibrate_counters']
    i = 0
    while i < len(lines):
        if any(f"def {m}" in lines[i] for m in target_methods):
            for j in range(i, min(i+6, len(lines))):
                write(f"{j+1}: {lines[j]}")
            write("...\n")
            i += 6
        else:
            i += 1

    write("\n--- 3. webapp/server.py ---\n")
    lines = read_file('webapp/server.py')
    for i, line in enumerate(lines):
        if 'GeneratorService' in line and any(m in line for m in ['start_generator', 'stop_generator', 'add_fuel', 'perform_maintenance', 'reset_counters', 'calibrate_counters']):
            start = max(0, i-5)
            end = min(len(lines), i+6)
            write(f"\nMatch at line {i+1}:\n")
            for j in range(start, end):
                write(f"{j+1}: {lines[j]}")

    write("\n--- 4. bot/services/notify_service.py ---\n")
    lines = read_file('bot/services/notify_service.py')
    for i, line in enumerate(lines, 1):
        write(f"{i}: {line}")

    write("\n--- 5. webapp/static/css/style.css ---\n")
    lines = read_file('webapp/static/css/style.css')
    if len(lines) >= 770:
        for i in range(749, 770):
            write(f"{i+1}: {lines[i]}")
    else:
        write(f"File shorter than 770 lines, total lines: {len(lines)}\n")

    write("\n--- 6. webapp/static/js/app.js ---\n")
    lines = read_file('webapp/static/js/app.js')
    start = max(0, len(lines)-120)
    for i in range(start, len(lines)):
        write(f"{i+1}: {lines[i]}")

    write("\n--- app.js search ---\n")
    for i, line in enumerate(lines):
        if 'showToast' in line or 'toast' in line:
            write(f"{i+1}: {line}")

    write("\n--- 7. webapp/templates/index.html ---\n")
    lines = read_file('webapp/templates/index.html')
    for i, line in enumerate(lines):
        if 'wizardModal' in line or 'Notification Toast' in line:
            write(f"{i+1}: {line}")

print("Done")
