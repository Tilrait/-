#!/bin/bash
# Управляющий скрипт для перевода проекта VergeLock

set -e

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функции для вывода
log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Проверка зависимостей
check_dependencies() {
    log_info "Проверка зависимостей..."
    
    # Проверяем Python
    if ! command -v python3 &> /dev/null; then
        log_error "Python3 не установлен"
        exit 1
    fi
    
    # Проверяем pip
    if ! command -v pip &> /dev/null; then
        log_warn "Pip не установлен, устанавливаем..."
        python3 -m ensurepip --upgrade
    fi
    
    # Проверяем библиотеки
    python3 -c "import requests, markdown, dotenv" 2>/dev/null || {
        log_warn "Устанавливаем необходимые библиотеки..."
        pip install requests markdown python-dotenv beautifulsoup4
    }
    
    log_info "✅ Все зависимости установлены"
}

# Настройка API ключа
setup_api_key() {
    if [ ! -f .env ]; then
        log_info "Настройка API ключа DeepSeek..."
        echo "Введите ваш API ключ DeepSeek:"
        read -s api_key
        
        echo "DEEPSEEK_API_KEY=$api_key" > .env
        log_info "✅ API ключ сохранен в .env"
    else
        log_info "✅ API ключ уже настроен"
    fi
}

# Создание глоссария
create_glossary() {
    local input_file=$1
    local glossary_file="glossary.json"
    
    if [ -f "$glossary_file" ]; then
        log_info "Глоссарий уже существует"
        return
    fi
    
    log_info "Создание глоссария из $input_file..."
    
    cat > extract_terms.py << 'PYEOF'
import re
import json
import sys
from collections import Counter

def extract_terms(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Паттерны для поиска терминов
    patterns = [
        r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\b',
        r'\b[А-ЯЁ][а-яё]{4,}\b',
        r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',
        r'\b[a-zA-Z]{6,}\b',
    ]
    
    terms = []
    for pattern in patterns:
        terms.extend(re.findall(pattern, content))
    
    # Считаем частоту
    counter = Counter(terms)
    
    # Фильтруем
    common = {'который', 'которые', 'такой', 'такие', 'может', 'должен'}
    result = {}
    
    for term, count in counter.most_common(50):
        term_lower = term.lower()
        if count >= 2 and len(term) > 4 and not any(word in term_lower for word in common):
            result[term] = {"count": count, "translation": ""}
    
    return result

if __name__ == "__main__":
    if len(sys.argv) > 1:
        terms = extract_terms(sys.argv[1])
        with open('glossary.json', 'w', encoding='utf-8') as f:
            json.dump({"glossary": terms}, f, indent=2, ensure_ascii=False)
        print(f"Извлечено {len(terms)} терминов")
PYEOF
    
    python3 extract_terms.py "$input_file"
    rm extract_terms.py
    
    log_info "✅ Глоссарий создан: $glossary_file"
}

# Основной перевод
translate_document() {
    local input_file=$1
    local output_file="${input_file%.md}_translated.md"
    
    log_info "Начинаю перевод $input_file..."
    
    # Запускаем переводчик
    python3 deepseek_translator.py "$input_file" --output "$output_file" --glossary "glossary.json"
    
    if [ $? -eq 0 ]; then
        log_info "✅ Перевод завершен: $output_file"
        
        # Создаем двуязычную версию
        log_info "Создаю двуязычную версию..."
        python3 -c "
import sys
sys.path.append('.')
from deepseek_translator import DeepSeekTranslator
translator = DeepSeekTranslator()
translator.create_bilingual_file('$input_file', '$output_file')
        "
    else
        log_error "Ошибка при переводе"
        exit 1
    fi
}

# Проверка качества
check_quality() {
    local original=$1
    local translated=$2
    
    log_info "Проверка качества перевода..."
    
    cat > check_translation.py << 'PYEOF'
import sys

def check_basic_quality(orig_file, trans_file):
    with open(orig_file, 'r', encoding='utf-8') as f:
        orig = f.read()
    with open(trans_file, 'r', encoding='utf-8') as f:
        trans = f.read()
    
    # Простые проверки
    orig_lines = orig.count('\n')
    trans_lines = trans.count('\n')
    
    orig_words = len(orig.split())
    trans_words = len(trans.split())
    
    print(f"Исходный файл: {orig_lines} строк, {orig_words} слов")
    print(f"Перевод: {trans_lines} строк, {trans_words} слов")
    
    ratio = trans_words / orig_words if orig_words > 0 else 0
    print(f"Соотношение слов: {ratio:.2f}")
    
    if 0.7 < ratio < 1.3:
        print("✅ Соотношение слов в норме")
    else:
        print("⚠️  Возможны проблемы с переводом")

if __name__ == "__main__":
    check_basic_quality(sys.argv[1], sys.argv[2])
PYEOF
    
    python3 check_translation.py "$original" "$translated"
    rm check_translation.py
}

# Основной процесс
main() {
    echo "========================================"
    echo "   ПЕРЕВОДЧИК ТЕХНИЧЕСКОЙ ДОКУМЕНТАЦИИ   "
    echo "========================================"
    
    # Входной файл
    INPUT_FILE="TechDocumFor-VergeLock.md"
    
    if [ ! -f "$INPUT_FILE" ]; then
        log_error "Файл $INPUT_FILE не найден"
        exit 1
    fi
    
    # 1. Проверка зависимостей
    check_dependencies
    
    # 2. Настройка API
    setup_api_key
    
    # 3. Создание глоссария
    create_glossary "$INPUT_FILE"
    
    # 4. Перевод документа
    translate_document "$INPUT_FILE"
    
    # 5. Проверка качества
    OUTPUT_FILE="${INPUT_FILE%.md}_translated.md"
    check_quality "$INPUT_FILE" "$OUTPUT_FILE"
    
    echo ""
    echo "========================================"
    echo "          🎉 ВСЁ ГОТОВО! ��             "
    echo "========================================"
    echo ""
    echo "Созданные файлы:"
    echo "  📄 Оригинал: $INPUT_FILE"
    echo "  🌐 Перевод: $OUTPUT_FILE"
    echo "  🔤 Двуязычный: ${INPUT_FILE%.md}_bilingual.md"
    echo "  📊 Статистика: ${INPUT_FILE%.md}_translated_stats.json"
    echo "  📚 Глоссарий: glossary.json"
    echo ""
    echo "Для редактирования глоссария:"
    echo "  nano glossary.json"
    echo ""
    echo "Для повторного перевода:"
    echo "  ./translate_project.sh"
}

# Запуск
main "$@"
