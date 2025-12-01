"""
Продвинутый переводчик технической документации с использованием DeepSeek API
Поддерживает Markdown, сохраняет форматирование и терминологию
"""

import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import List, Dict, Tuple
import requests
from dotenv import load_dotenv
import markdown
from bs4 import BeautifulSoup

load_dotenv()

class DeepSeekTranslator:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('DEEPSEEK_API_KEY')
        self.api_url = "https://api.deepseek.com/v1/chat/completions"
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        self.stats = {
            'total_segments': 0,
            'translated_segments': 0,
            'total_tokens': 0,
            'errors': 0
        }
        
        self.translation_cache = {}
        
    def split_markdown_into_segments(self, content: str, max_segment_length: int = 1500) -> List[Dict]:
        """
        Разбивает Markdown документ на логические сегменты для перевода
        """
        segments = []
        
        lines = content.split('\n')
        current_segment = []
        current_header = None
        
        for line in lines:
            if re.match(r'^#{1,6}\s+', line):
                if current_segment:
                    segments.append({
                        'type': 'text',
                        'header': current_header,
                        'content': '\n'.join(current_segment),
                        'original': '\n'.join(current_segment)
                    })
                    current_segment = []
                
                current_header = line
                segments.append({
                    'type': 'header',
                    'content': line,
                    'original': line,
                    'level': line.count('#')
                })
            
            elif line.strip().startswith('```'):
                if current_segment:
                    segments.append({
                        'type': 'text',
                        'header': current_header,
                        'content': '\n'.join(current_segment),
                        'original': '\n'.join(current_segment)
                    })
                    current_segment = []
                
                code_block = [line]
                in_code_block = True
                
                for next_line in lines[lines.index(line) + 1:]:
                    code_block.append(next_line)
                    if next_line.strip().startswith('```'):
                        break
                
                segments.append({
                    'type': 'code',
                    'content': '\n'.join(code_block),
                    'original': '\n'.join(code_block)
                })
            
            elif '|' in line and re.search(r'\|\s*:?-+:?\s*\|', line):
                if current_segment:
                    segments.append({
                        'type': 'text',
                        'header': current_header,
                        'content': '\n'.join(current_segment),
                        'original': '\n'.join(current_segment)
                    })
                    current_segment = []
                
                table_lines = [line]
                table_index = lines.index(line)
                
                for i in range(1, 20):
                    if table_index + i < len(lines):
                        next_line = lines[table_index + i]
                        if '|' in next_line:
                            table_lines.append(next_line)
                        else:
                            break
                
                segments.append({
                    'type': 'table',
                    'content': '\n'.join(table_lines),
                    'original': '\n'.join(table_lines)
                })
            
            else:
                current_segment.append(line)
        
        if current_segment:
            segments.append({
                'type': 'text',
                'header': current_header,
                'content': '\n'.join(current_segment),
                'original': '\n'.join(current_segment)
            })
        
        merged_segments = []
        current_merge = []
        current_length = 0
        
        for segment in segments:
            seg_length = len(segment['content'])
            
            if segment['type'] in ['code', 'table']:
                if current_merge:
                    merged_segments.append(self._merge_segments(current_merge))
                    current_merge = []
                    current_length = 0
                merged_segments.append(segment)
            elif current_length + seg_length > max_segment_length and current_merge:
                merged_segments.append(self._merge_segments(current_merge))
                current_merge = [segment]
                current_length = seg_length
            else:
                current_merge.append(segment)
                current_length += seg_length
        
        if current_merge:
            merged_segments.append(self._merge_segments(current_merge))
        
        return merged_segments
    
    def _merge_segments(self, segments: List[Dict]) -> Dict:
        """Объединяет несколько сегментов в один"""
        if len(segments) == 1:
            return segments[0]
        
        content_parts = []
        original_parts = []
        
        for seg in segments:
            content_parts.append(seg['content'])
            original_parts.append(seg.get('original', seg['content']))
        
        return {
            'type': 'text',
            'header': segments[0].get('header'),
            'content': '\n\n'.join(content_parts),
            'original': '\n\n'.join(original_parts)
        }
    
    def create_glossary_from_text(self, text: str, max_terms: int = 100) -> Dict[str, str]:
        """
        Создает глоссарий из текста, идентифицируя технические термины
        """
        clean_text = re.sub(r'`[^`]+`', '', text)
        clean_text = re.sub(r'```.*?```', '', clean_text, flags=re.DOTALL)
        
        term_patterns = [
            r'\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+\b',
            r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\b',
            r'\b[а-яё]{6,}\b',
            r'\b[a-zA-Z]{6,}\b',
        ]
        
        terms = set()
        for pattern in term_patterns:
            matches = re.findall(pattern, clean_text, re.IGNORECASE)
            terms.update(matches)
        
        common_words = {
            'русский': ['который', 'которые', 'такой', 'такие', 'может', 'должен',
                       'имеет', 'имеют', 'можно', 'нужно', 'очень', 'будет',
                       'есть', 'это', 'что', 'как', 'для', 'надо', 'хотя'],
            'english': ['which', 'that', 'this', 'these', 'have', 'has', 'will',
                       'should', 'could', 'would', 'very', 'much', 'many']
        }
        
        filtered_terms = []
        for term in terms:
            term_lower = term.lower()
            if (len(term) > 4 and 
                not any(word in term_lower for word in common_words['русский']) and
                not any(word in term_lower for word in common_words['english'])):
                filtered_terms.append(term)
        
        top_terms = filtered_terms[:max_terms]
        
        glossary = {}
        for term in top_terms:
            glossary[term] = ""
        
        return glossary
    
    def translate_with_deepseek(self, text: str, glossary: Dict[str, str] = None, 
                                context: str = None) -> Tuple[str, Dict]:
        """
        Переводит текст с использованием DeepSeek API с учетом глоссария и контекста
        """
        cache_key = hash(text)
        if cache_key in self.translation_cache:
            return self.translation_cache[cache_key], {'cached': True}
        
        system_prompt = """Ты профессиональный переводчик технической документации. 
Твоя задача - точно переводить тексты с русского на английский, сохраняя:
1. Техническую точность терминов
2. Структуру документа (заголовки, списки, форматирование)
3. Стиль технической документации

Требования:
- Используй технические термины из предоставленного глоссария
- Сохраняй Markdown разметку
- Не переводи имена собственные, названия продуктов, переменные в коде
- Будь консистентен в переводе терминов"""
        
        if glossary:
            glossary_text = "\nГлоссарий для перевода:\n"
            for rus, eng in glossary.items():
                if eng:
                    glossary_text += f"{rus} → {eng}\n"
            system_prompt += glossary_text
        
        if context:
            system_prompt += f"\nКонтекст предыдущего раздела: {context[:500]}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Переведи следующий технический текст на английский, сохраняя всю разметку:\n\n{text}"}
        ]
        
        payload = {
            "model": "deepseek-chat",
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 4000,
            "stream": False
        }
        
        try:
            response = requests.post(self.api_url, headers=self.headers, 
                                   json=payload, timeout=120)
            response.raise_for_status()
            
            result = response.json()
            translated_text = result['choices'][0]['message']['content']
            
            self.stats['total_segments'] += 1
            self.stats['translated_segments'] += 1
            if 'usage' in result:
                self.stats['total_tokens'] += result['usage'].get('total_tokens', 0)
            
            self.translation_cache[cache_key] = translated_text
            
            return translated_text, result
            
        except Exception as e:
            self.stats['errors'] += 1
            print(f"Ошибка при переводе: {e}")
            return f"[ОШИБКА ПЕРЕВОДА: {str(e)}]", {'error': str(e)}
    
    def translate_markdown_file(self, input_file: str, output_file: str = None, 
                               glossary_file: str = None):
        """
        Основная функция для перевода Markdown файла
        """
        print(f"Начинаю перевод файла: {input_file}")
        
        with open(input_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        glossary = {}
        if glossary_file and os.path.exists(glossary_file):
            with open(glossary_file, 'r', encoding='utf-8') as f:
                glossary_data = json.load(f)
                glossary = glossary_data.get('glossary', {})
        
        segments = self.split_markdown_into_segments(content)
        print(f"Разбито на {len(segments)} сегментов")
        
        translated_segments = []
        
        for i, segment in enumerate(segments, 1):
            print(f"Перевод сегмента {i}/{len(segments)}...")
            
            if segment['type'] in ['code', 'table']:
                translated_segments.append(segment['content'])
            else:
                context = None
                if i > 1 and translated_segments:
                    context = translated_segments[-1][-1000:]
                
                translated, _ = self.translate_with_deepseek(
                    segment['content'], 
                    glossary,
                    context
                )
                translated_segments.append(translated)
            
            if i % 5 == 0:
                time.sleep(1)
        
        translated_content = '\n\n'.join(translated_segments)
        
        if not output_file:
            output_file = Path(input_file).stem + '_translated.md'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(translated_content)
        
        print(f"\n✅ Перевод завершен!")
        print(f"Файл сохранен: {output_file}")
        print(f"\n📊 Статистика:")
        print(f"   Сегментов переведено: {self.stats['translated_segments']}/{self.stats['total_segments']}")
        print(f"   Всего токенов: {self.stats['total_tokens']}")
        print(f"   Ошибок: {self.stats['errors']}")
        
        stats_file = Path(output_file).stem + '_stats.json'
        with open(stats_file, 'w', encoding='utf-8') as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)
        
        return output_file
    
    def create_bilingual_file(self, original_file: str, translated_file: str, 
                             output_file: str = None):
        """
        Создает двуязычный файл (русский/английский)
        """
        with open(original_file, 'r', encoding='utf-8') as f:
            original = f.read()
        
        with open(translated_file, 'r', encoding='utf-8') as f:
            translated = f.read()
        
        orig_lines = original.split('\n')
        trans_lines = translated.split('\n')
        
        bilingual = []
        max_lines = max(len(orig_lines), len(trans_lines))
        
        for i in range(max_lines):
            orig_line = orig_lines[i] if i < len(orig_lines) else ""
            trans_line = trans_lines[i] if i < len(trans_lines) else ""
            
            if orig_line.strip() or trans_line.strip():
                bilingual.append(f"RU: {orig_line}")
                bilingual.append(f"EN: {trans_line}")
                bilingual.append("---")
        
        if not output_file:
            output_file = Path(original_file).stem + '_bilingual.md'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write('\n'.join(bilingual))
        
        print(f"✅ Двуязычный файл создан: {output_file}")
        return output_file

def main():
    parser = argparse.ArgumentParser(description='Переводчик технической документации с DeepSeek API')
    parser.add_argument('input', help='Входной Markdown файл')
    parser.add_argument('--output', '-o', help='Выходной файл')
    parser.add_argument('--glossary', '-g', help='Файл глоссария (JSON)')
    parser.add_argument('--api-key', help='API ключ DeepSeek')
    parser.add_argument('--bilingual', '-b', action='store_true', 
                       help='Создать двуязычный файл')
    
    args = parser.parse_args()
    
    api_key = args.api_key or os.getenv('DEEPSEEK_API_KEY')
    if not api_key:
        print("❌ Ошибка: API ключ не найден")
        print("Добавьте ключ в .env файл или укажите через --api-key")
        return
    
    translator = DeepSeekTranslator(api_key)
    
    translated_file = translator.translate_markdown_file(
        args.input, 
        args.output,
        args.glossary
    )
    
    if args.bilingual:
        translator.create_bilingual_file(args.input, translated_file)

if __name__ == "__main__":
    main()
