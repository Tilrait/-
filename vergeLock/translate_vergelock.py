#!/usr/bin/env python3
"""
Упрощенный переводчик для VergeLock документации
Работает в виртуальном окружении
"""

import os
import json
import time
import argparse
from pathlib import Path

# Проверяем что мы в виртуальном окружении
print("🔧 Проверка окружения...")
try:
    import requests
    print("✅ requests загружен")
except ImportError:
    print("❌ requests не установлен. В виртуальном окружении выполните:")
    print("   pip install requests")
    exit(1)

class VergeLockTranslator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        if not self.api_key:
            print("❌ API ключ не найден")
            print("Способы указать ключ:")
            print("  1. Установите переменную: export DEEPSEEK_API_KEY='ваш_ключ'")
            print("  2. Создайте файл .env с DEEPSEEK_API_KEY=ваш_ключ")
            print("  3. Используйте параметр --api-key")
            exit(1)
        
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        print("✅ Переводчик инициализирован")
    
    def read_file_safe(self, filepath):
        """Безопасное чтение файла с разными кодировками"""
        encodings = ['utf-8', 'cp1251', 'latin-1', 'iso-8859-1']
        
        for encoding in encodings:
            try:
                with open(filepath, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        
        # Последняя попытка
        with open(filepath, 'rb') as f:
            return f.read().decode('utf-8', errors='ignore')
    
    def smart_split(self, text, max_chars=2500):
        """Умное разбиение на части"""
        lines = text.split('\n')
        chunks = []
        current_chunk = []
        current_size = 0
        
        for line in lines:
            line_size = len(line)
            
            # Проверяем границы раздела
            if line.startswith('# ') and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            elif current_size + line_size > max_chars and current_chunk:
                chunks.append('\n'.join(current_chunk))
                current_chunk = [line]
                current_size = line_size
            else:
                current_chunk.append(line)
                current_size += line_size + 1
        
        if current_chunk:
            chunks.append('\n'.join(current_chunk))
        
        return chunks
    
    def translate_chunk(self, text, chunk_num, total_chunks):
        """Перевод одной части"""
        print(f"📤 Отправка части {chunk_num}/{total_chunks}...")
        
        # Проверяем если это код
        if text.strip().startswith('```'):
            print("   ⏭️  Пропускаем код блок")
            return text
        
        payload = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": """Ты переводчик технической документации с русского на английский.
                    
ВАЖНЫЕ ПРАВИЛА:
1. Сохраняй ВСЮ Markdown разметку (# заголовки, **жирный**, `код`)
2. НЕ переводи:
   - Имена: VergeLock, RAG и другие названия продуктов
   - Код внутри ``` ```
   - Команды терминала, пути файлов
   - Названия переменных, функций
3. Будь технически точным
4. Если не уверен в термине - оставь как есть"""
                },
                {
                    "role": "user",
                    "content": f"Переведи этот текст на английский, сохраняя разметку:\n\n{text}"
                }
            ],
            "temperature": 0.1,
            "max_tokens": 4000
        }
        
        try:
            response = requests.post(self.api_url, json=payload, 
                                   headers=self.headers, timeout=90)
            response.raise_for_status()
            
            result = response.json()
            translated = result['choices'][0]['message']['content']
            
            print(f"   ✅ Переведено ({len(translated)} символов)")
            return translated
            
        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            return f"[TRANSLATION ERROR: {str(e)[:50]}]\n{text}"
    
    def process_file(self, input_path, output_path=None):
        """Основной процесс перевода"""
        print(f"\n🚀 Начинаю перевод: {input_path}")
        
        # Читаем файл
        content = self.read_file_safe(input_path)
        print(f"📖 Размер: {len(content)} символов")
        
        # Разбиваем на части
        chunks = self.smart_split(content)
        print(f"📦 Разбито на {len(chunks)} частей")
        
        # Переводим каждую часть
        translated_chunks = []
        
        for i, chunk in enumerate(chunks, 1):
            translated = self.translate_chunk(chunk, i, len(chunks))
            translated_chunks.append(translated)
            
            # Пауза между запросами
            if i < len(chunks):
                time.sleep(2)  # 2 секунды между запросами
        
        # Собираем результат
        result = '\n\n'.join(translated_chunks)
        
        # Определяем имя выходного файла
        if not output_path:
            input_stem = Path(input_path).stem
            output_path = f"{input_stem}_translated.md"
        
        # Сохраняем
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(result)
        
        print(f"\n🎉 Готово!")
        print(f"📄 Исходный: {input_path}")
        print(f"🌐 Перевод: {output_path}")
        print(f"📊 Частей переведено: {len(translated_chunks)}")
        
        return output_path

def main():
    parser = argparse.ArgumentParser(description='Переводчик VergeLock документации')
    parser.add_argument('input', help='Входной Markdown файл')
    parser.add_argument('--output', '-o', help='Выходной файл')
    parser.add_argument('--api-key', help='API ключ DeepSeek')
    
    args = parser.parse_args()
    
    # Проверяем файл
    if not os.path.exists(args.input):
        print(f"❌ Файл не найден: {args.input}")
        return
    
    # Создаем переводчик
    translator = VergeLockTranslator(args.api_key)
    
    # Выполняем перевод
    translator.process_file(args.input, args.output)

if __name__ == "__main__":
    main()
