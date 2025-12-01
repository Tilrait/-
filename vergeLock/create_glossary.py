"""
Автоматическое создание глоссария из технического документа
"""

import re
from collections import Counter
import csv

def extract_terms_from_md(md_file, output_csv="glossary.csv"):
    """
    Извлекает потенциальные термины из Markdown файла
    """
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    
    patterns = [
        r'\b[А-Я][а-я]+\s+[А-Я][а-я]+\b',
        r'\b[А-Я][а-я]{3,}\b',
        r'\b[\w-]+ция\b',
        r'\b[\w-]+ость\b',
        r'\b[\w-]+тор\b',
    ]
    
    terms = []
    for pattern in patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        terms.extend(matches)
    
    term_counter = Counter(terms)
    common_terms = [(term, count) for term, count in term_counter.items() 
                   if count >= 2 and len(term) > 3]
    
    common_terms.sort(key=lambda x: x[1], reverse=True)
    
    with open(output_csv, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Source', 'Target', 'Description'])
        for term, count in common_terms[:50]:
            writer.writerow([term, '', f'Частота: {count}'])
    
    print(f"Глоссарий создан: {output_csv}")
    print(f"Найдено уникальных терминов: {len(common_terms)}")
    
    print("\nПримеры терминов:")
    for term, count in common_terms[:10]:
        print(f"  {term}: {count} раз")

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        extract_terms_from_md(sys.argv[1])
    else:
        print("Использование: python3 create_glossary.py <файл.md>")