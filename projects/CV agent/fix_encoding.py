with open('prompts.py','r',encoding='cp1252') as f:
    content = f.read()

replacements = {
    '\x97': '--',
    '\x96': '-',
    '\x93': '"',
    '\x94': '"',
    '\x91': "'",
    '\x92': "'",
    '\x85': '...',
    '\x80': 'EUR',
}
for bad, good in replacements.items():
    content = content.replace(bad, good)

with open('prompts.py','w',encoding='utf-8') as f:
    f.write(content)

print('Done. Converted prompts.py to clean UTF-8')
