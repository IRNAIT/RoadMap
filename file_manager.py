#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import json
import os
import base64
from PIL import Image, ImageDraw, ImageFont
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import QObject

class FileManager(QObject):
    """Менеджер файлов для работы с проектами RoadMap"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_file_path = None
        
    def save_project(self, file_path, project_data):
        """Сохранение проекта в формате .rm"""
        try:
            # Подготавливаем данные для сохранения
            save_data = {
                'version': '1.0',
                'project_info': {
                    'name': project_data.get('name', 'Новый проект'),
                    'description': project_data.get('description', ''),
                    'created_date': project_data.get('created_date', ''),
                    'modified_date': project_data.get('modified_date', '')
                },
                'stages': [],
                'connections': project_data.get('connections', [])
            }
            
            # Обрабатываем этапы
            for stage in project_data.get('stages', []):
                stage_data = stage.copy()
                
                # Обрабатываем изображения
                if 'image_path' in stage_data and stage_data['image_path']:
                    image_path = stage_data['image_path']
                    if os.path.exists(image_path):
                        # Кодируем изображение в base64
                        with open(image_path, 'rb') as img_file:
                            img_data = base64.b64encode(img_file.read()).decode('utf-8')
                            stage_data['image_data'] = img_data
                            stage_data['image_format'] = os.path.splitext(image_path)[1][1:].upper()
                
                # Сохраняем текст заметки для блокнота
                if stage_data.get('type') == 'note' or stage_data.get('type') == 'txt':
                    stage_data['note_text'] = stage.get('note_text', '')
                
                save_data['stages'].append(stage_data)
            
            # Сохраняем в JSON файл
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(save_data, f, ensure_ascii=False, indent=2)
                
            self.current_file_path = file_path
            return True
            
        except Exception as e:
            raise Exception(f"Ошибка сохранения проекта: {str(e)}")
            
    def load_project(self, file_path):
        """Загрузка проекта из формата .rm"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                save_data = json.load(f)
                
            # Проверяем версию
            version = save_data.get('version', '1.0')
            if version != '1.0':
                raise Exception(f"Неподдерживаемая версия файла: {version}")
                
            # Восстанавливаем данные проекта
            project_data = {
                'name': save_data.get('project_info', {}).get('name', 'Новый проект'),
                'description': save_data.get('project_info', {}).get('description', ''),
                'created_date': save_data.get('project_info', {}).get('created_date', ''),
                'modified_date': save_data.get('project_info', {}).get('modified_date', ''),
                'stages': [],
                'connections': save_data.get('connections', [])
            }
            
            # Обрабатываем этапы
            for stage_data in save_data.get('stages', []):
                stage = stage_data.copy()
                
                # Восстанавливаем изображения
                if 'image_data' in stage:
                    try:
                        # Создаем временную папку для изображений
                        temp_dir = os.path.join(os.path.dirname(file_path), 'images')
                        os.makedirs(temp_dir, exist_ok=True)
                        
                        # Декодируем и сохраняем изображение
                        img_data = base64.b64decode(stage['image_data'])
                        img_format = stage.get('image_format', 'PNG')
                        img_filename = f"stage_{stage['id']}.{img_format.lower()}"
                        img_path = os.path.join(temp_dir, img_filename)
                        
                        with open(img_path, 'wb') as img_file:
                            img_file.write(img_data)
                            
                        stage['image_path'] = img_path
                        
                    except Exception as e:
                        print(f"Ошибка восстановления изображения: {str(e)}")
                        stage['image_path'] = ''
                
                # Восстанавливаем текст заметки для блокнота
                if stage.get('type') == 'note' or stage.get('type') == 'txt':
                    stage['note_text'] = stage_data.get('note_text', '')
                
                project_data['stages'].append(stage)
                
            self.current_file_path = file_path
            return project_data
            
        except Exception as e:
            raise Exception(f"Ошибка загрузки проекта: {str(e)}")
            
    def export_to_image(self, project_data, file_path, format='PNG', size=(1920, 1080)):
        """Экспорт проекта в изображение"""
        try:
            # Создаем изображение
            img = Image.new('RGB', size, color='white')
            draw = ImageDraw.Draw(img)
            
            # Загружаем шрифт
            try:
                font_large = ImageFont.truetype("arial.ttf", 24)
                font_medium = ImageFont.truetype("arial.ttf", 16)
                font_small = ImageFont.truetype("arial.ttf", 12)
            except:
                # Используем стандартный шрифт
                font_large = ImageFont.load_default()
                font_medium = ImageFont.load_default()
                font_small = ImageFont.load_default()
            
            # Рисуем заголовок
            title = project_data.get('name', 'RoadMap проекта')
            draw.text((50, 50), title, fill='black', font=font_large)
            
            # Рисуем этапы
            stages = project_data.get('stages', [])
            stage_positions = {}
            
            for i, stage in enumerate(stages):
                x = 50 + (i % 3) * 300
                y = 150 + (i // 3) * 200
                
                # Рисуем рамку этапа
                draw.rectangle([x, y, x + 250, y + 150], outline='blue', width=2)
                
                # Рисуем заголовок этапа
                title = stage.get('title', f'Этап {i+1}')
                draw.text((x + 10, y + 10), title, fill='black', font=font_medium)
                
                # Рисуем статус
                status = "Завершен" if stage.get('completed', False) else "В процессе"
                status_color = 'green' if stage.get('completed', False) else 'orange'
                draw.text((x + 10, y + 40), status, fill=status_color, font=font_small)
                
                # Рисуем прогресс
                progress = stage.get('progress', 0)
                draw.text((x + 10, y + 60), f"Прогресс: {progress}%", fill='black', font=font_small)
                
                # Рисуем описание
                description = stage.get('description', '')
                if description:
                    # Обрезаем длинное описание
                    if len(description) > 50:
                        description = description[:47] + "..."
                    draw.text((x + 10, y + 80), description, fill='gray', font=font_small)
                
                # Сохраняем позицию для связей
                stage_positions[stage.get('id', i)] = (x + 125, y + 75)
            
            # Рисуем связи
            connections = project_data.get('connections', [])
            for conn in connections:
                start_id = conn.get('start_id')
                end_id = conn.get('end_id')
                
                if start_id in stage_positions and end_id in stage_positions:
                    start_pos = stage_positions[start_id]
                    end_pos = stage_positions[end_id]
                    
                    # Рисуем линию
                    draw.line([start_pos, end_pos], fill='gray', width=2)
                    
                    # Рисуем стрелку
                    arrow_size = 10
                    dx = end_pos[0] - start_pos[0]
                    dy = end_pos[1] - start_pos[1]
                    
                    if dx != 0 or dy != 0:
                        # Нормализуем вектор
                        length = (dx**2 + dy**2)**0.5
                        dx /= length
                        dy /= length
                        
                        # Рисуем стрелку
                        arrow_x = end_pos[0] - arrow_size * dx
                        arrow_y = end_pos[1] - arrow_size * dy
                        
                        draw.line([(arrow_x, arrow_y), end_pos], fill='gray', width=2)
            
            # Сохраняем изображение
            img.save(file_path, format.upper())
            return True
            
        except Exception as e:
            raise Exception(f"Ошибка экспорта в изображение: {str(e)}")
            
    def export_to_html(self, project_data, file_path):
        """Экспорт проекта в HTML"""
        try:
            html_content = f"""
<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{project_data.get('name', 'RoadMap проекта')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .header {{
            text-align: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 2px solid #2196F3;
        }}
        .stages {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }}
        .stage {{
            border: 2px solid #2196F3;
            border-radius: 10px;
            padding: 15px;
            background-color: #E3F2FD;
        }}
        .stage.completed {{
            border-color: #4CAF50;
            background-color: #E8F5E8;
        }}
        .stage-title {{
            font-weight: bold;
            font-size: 18px;
            margin-bottom: 10px;
            color: #1976D2;
        }}
        .stage-status {{
            display: inline-block;
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
            font-weight: bold;
            margin-bottom: 10px;
        }}
        .status-pending {{
            background-color: #FF9800;
            color: white;
        }}
        .status-completed {{
            background-color: #4CAF50;
            color: white;
        }}
        .stage-progress {{
            margin-bottom: 10px;
        }}
        .progress-bar {{
            width: 100%;
            height: 20px;
            background-color: #e0e0e0;
            border-radius: 10px;
            overflow: hidden;
        }}
        .progress-fill {{
            height: 100%;
            background-color: #4CAF50;
            transition: width 0.3s ease;
        }}
        .stage-description {{
            color: #666;
            font-size: 14px;
            line-height: 1.4;
        }}
        .stage-image {{
            margin-top: 10px;
            text-align: center;
        }}
        .stage-image img {{
            max-width: 100%;
            max-height: 150px;
            border-radius: 5px;
        }}
        .connections {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
        }}
        .connection {{
            background-color: #f9f9f9;
            padding: 10px;
            margin-bottom: 10px;
            border-radius: 5px;
            border-left: 4px solid #2196F3;
        }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #e0e0e0;
            color: #666;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>{project_data.get('name', 'RoadMap проекта')}</h1>
            <p>{project_data.get('description', 'Описание проекта')}</p>
        </div>
        
        <div class="stages">
"""
            
            # Добавляем этапы
            stages = project_data.get('stages', [])
            for stage in stages:
                status_class = "completed" if stage.get('completed', False) else "pending"
                status_text = "Завершен" if stage.get('completed', False) else "В процессе"
                progress = stage.get('progress', 0)
                
                html_content += f"""
            <div class="stage {status_class}">
                <div class="stage-title">{stage.get('title', 'Без названия')}</div>
                <div class="stage-status status-{status_class}">{status_text}</div>
                <div class="stage-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: {progress}%"></div>
                    </div>
                    <small>Прогресс: {progress}%</small>
                </div>
                <div class="stage-description">{stage.get('description', '')}</div>
"""
                
                # Добавляем изображение если есть
                if stage.get('image_path') and os.path.exists(stage.get('image_path')):
                    html_content += f"""
                <div class="stage-image">
                    <img src="{stage.get('image_path')}" alt="Изображение этапа">
                </div>
"""
                
                html_content += """
            </div>
"""
            
            html_content += """
        </div>
        
        <div class="connections">
            <h3>Связи между этапами:</h3>
"""
            
            # Добавляем связи
            connections = project_data.get('connections', [])
            for conn in connections:
                start_id = conn.get('start_id')
                end_id = conn.get('end_id')
                start_stage = next((s for s in stages if s.get('id') == start_id), None)
                end_stage = next((s for s in stages if s.get('id') == end_id), None)
                
                if start_stage and end_stage:
                    html_content += f"""
            <div class="connection">
                <strong>{start_stage.get('title', 'Этап')}</strong> → <strong>{end_stage.get('title', 'Этап')}</strong>
            </div>
"""
            
            html_content += f"""
        </div>
        
        <div class="footer">
            <p>Создано с помощью RoadMap</p>
            <p>Дата создания: {project_data.get('created_date', 'Не указана')}</p>
        </div>
    </div>
</body>
</html>
"""
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
                
            return True
            
        except Exception as e:
            raise Exception(f"Ошибка экспорта в HTML: {str(e)}")
            
    def get_file_info(self, file_path):
        """Получение информации о файле проекта"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            project_info = data.get('project_info', {})
            stages_count = len(data.get('stages', []))
            connections_count = len(data.get('connections', []))
            
            return {
                'name': project_info.get('name', 'Неизвестный проект'),
                'description': project_info.get('description', ''),
                'created_date': project_info.get('created_date', ''),
                'modified_date': project_info.get('modified_date', ''),
                'stages_count': stages_count,
                'connections_count': connections_count,
                'version': data.get('version', '1.0')
            }
            
        except Exception as e:
            raise Exception(f"Ошибка чтения информации о файле: {str(e)}")
            
    def validate_project_file(self, file_path):
        """Проверка корректности файла проекта"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            # Проверяем обязательные поля
            required_fields = ['version', 'stages']
            for field in required_fields:
                if field not in data:
                    return False, f"Отсутствует обязательное поле: {field}"
                    
            # Проверяем версию
            if data['version'] != '1.0':
                return False, f"Неподдерживаемая версия: {data['version']}"
                
            # Проверяем этапы
            stages = data.get('stages', [])
            for i, stage in enumerate(stages):
                if 'id' not in stage or 'title' not in stage:
                    return False, f"Некорректный этап {i}: отсутствуют обязательные поля"
                    
            return True, "Файл корректен"
            
        except json.JSONDecodeError:
            return False, "Некорректный JSON файл"
        except Exception as e:
            return False, f"Ошибка проверки файла: {str(e)}" 