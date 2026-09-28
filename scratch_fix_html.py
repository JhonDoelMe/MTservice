with open('webapp/templates/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('id="adminObjectsCard" style="display: none;"', 'class="card admin-only" style="display: none;"')

with open('webapp/templates/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("Fixed HTML admin tag")
