import re
import json
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLineEdit, QPushButton, QApplication, QScrollArea, QDialog, QHBoxLayout, QSizePolicy, QLabel, QMessageBox
from PyQt5.QtGui import QPainter, QFont, QColor, QKeyEvent, QFontMetrics, QClipboard
from PyQt5.QtCore import Qt, QRect, QPoint, pyqtSignal, QTimer
from glass_menu import GlassMenuButton

class TextFragment:
    def __init__(self, text, formats=None):
        self.text = text
        self.formats = formats or []

class CustomRichTextEditor(QWidget):
    scroll_needed = pyqtSignal()  # Сигнал для уведомления о необходимости скролла
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 200)
        self.font = QFont('Finlandica', 12)
        self.fragments = [TextFragment('')]
        self.cursor_pos = 0
        self.selection_start = None
        self.selection_end = None
        self.setFocusPolicy(Qt.StrongFocus)
        self.setMouseTracking(True)
        self._mouse_selecting = False
        self._rebuild_raw()
        # --- Курсор мигает ---
        self._cursor_visible = True
        self._cursor_timer = QTimer(self)
        self._cursor_timer.timeout.connect(self._blink_cursor)
        self._cursor_timer.start(500)
        self._last_keypress = 0
        # --- Стилизация ---
        self.setStyleSheet('''
            background-color: rgba(255,255,255,0.85);
            border-radius: 10px;
            border: 1.5px solid #c0c0c0;
        ''')

    @staticmethod
    def create_temp_editor():
        """Создает временный редактор без родителя для внутренних операций"""
        editor = CustomRichTextEditor()
        editor.setVisible(False)  # Скрываем временный редактор
        return editor

    def _rebuild_raw(self):
        self.raw_text = ''
        for frag in self.fragments:
            text = frag.text
            fmts = set(frag.formats)
            if fmts == {'bold', 'italic'}:
                text = f'***{text}***'
            else:
                for fmt in reversed(frag.formats):
                    if fmt == 'bold':
                        text = f'**{text}**'
                    elif fmt == 'italic':
                        text = f'*{text}*'
                    elif fmt == 'strike':
                        text = f'~~{text}~~'
                    elif fmt == 'underline':
                        text = f'__{text}__'
            self.raw_text += text

    def _split_text_into_words(self, text):
        """Разбивает текст на слова, сохраняя пробелы и знаки препинания"""
        import re
        # Разбиваем на слова, сохраняя пробелы и знаки препинания
        words = re.findall(r'\S+|\s+', text)
        return words

    def get_char_rects(self):
        margin_left = 10
        margin_top = 30
        margin_right = 10
        line_height = self.fontMetrics().height() + 4
        max_text_width = self.width() - margin_left - margin_right
        x, y = margin_left, margin_top
        pos = 0
        rects = []
        for frag in self.fragments:
            f = QFont('Finlandica', 12)
            if 'bold' in frag.formats:
                f.setWeight(QFont.Bold)
            if 'italic' in frag.formats:
                f.setItalic(True)
            if 'underline' in frag.formats:
                f.setUnderline(True)
            if 'strike' in frag.formats:
                f.setStrikeOut(True)
            metrics = QFontMetrics(f)
            words = self._split_text_into_words(frag.text)
            for word in words:
                word_width = metrics.width(word)
                if x + word_width > max_text_width and x > margin_left:
                    x = margin_left
                    y += line_height
                for ch in word:
                    char_width = metrics.width(ch)
                    rects.append((x, y, char_width, pos))
                    x += char_width
                    pos += 1
        # Добавляем "виртуальный" прямоугольник для конца текста
        rects.append((x, y, 2, pos))
        return rects

    def get_cursor_coordinates(self, pos):
        rects = self.get_char_rects()
        for x, y, w, p in rects:
            if p == pos:
                return x, y
        # Если не нашли — вернуть координаты конца текста
        return rects[-1][0], rects[-1][1]

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1,1,-1,-1)
        painter.setBrush(QColor(255,255,255,220))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 10, 10)
        layout = self.layout_text()
        sel_start = self.selection_start if self.selection_start is not None else self.cursor_pos
        sel_end = self.selection_end if self.selection_end is not None else self.cursor_pos
        sel_min, sel_max = min(sel_start, sel_end), max(sel_start, sel_end)
        # --- Выделение ---
        for item in layout:
            if sel_min <= item['pos'] < sel_max:
                m = item['metrics']
                painter.setBrush(QColor(180, 210, 255))
                painter.setPen(Qt.NoPen)
                painter.fillRect(item['x'], item['y'] - m.ascent(), m.width(item['char']), m.ascent() + m.descent(), QColor(180, 210, 255))
        # --- Текст ---
        for item in layout:
            m = item['metrics']
            painter.setFont(item['font'])
            painter.setPen(QColor('black'))
            painter.drawText(QPoint(item['x'], item['y']), item['char'])
        # --- Курсор ---
        if self._cursor_visible:
            cursor_drawn = False
            for item in layout:
                if item['pos'] == self.cursor_pos:
                    m = item['metrics']
                    painter.setPen(QColor('black'))
                    painter.drawLine(item['x'], item['y'] - m.ascent(), item['x'], item['y'] + m.descent())
                    cursor_drawn = True
                    break
            if not cursor_drawn and layout:
                # Если не нашли позицию — рисуем курсор в конце текста
                last = layout[-1]
                m = last['metrics']
                painter.setPen(QColor('black'))
                painter.drawLine(last['x'], last['y'] - m.ascent(), last['x'], last['y'] + m.descent())
        # --- Высота ---
        if layout:
            last = layout[-1]
            required_height = last['y'] + self.fontMetrics().height() + 0
            self.setMinimumHeight(required_height)
        self.scroll_needed.emit()

    def get_display_text(self):
        return ''.join(frag.text for frag in self.fragments)

    def keyPressEvent(self, event):
        self._cursor_visible = True
        self._cursor_timer.start(500)
        # Копирование, вырезание, вставка
        if event.modifiers() & Qt.ControlModifier:
            if event.key() == Qt.Key_C and self.has_selection():
                self.copy_selection()
                return
            elif event.key() == Qt.Key_X and self.has_selection():
                self.copy_selection()
                self.delete_selection()
                self._rebuild_raw()
                self.update()
                return
            elif event.key() == Qt.Key_V:
                self.paste_clipboard()
                self._rebuild_raw()
                self.update()
                return
        # Shift+Enter — мягкий перенос строки
        if event.key() in (Qt.Key_Return, Qt.Key_Enter):
            if event.modifiers() & Qt.ShiftModifier:
                self.insert_text('\n')
                self._rebuild_raw()
                self.update()
                return
            else:
                self.insert_text('\n\n')
                self._rebuild_raw()
                self.update()
                return
        # Управление курсором стрелками
        if event.key() == Qt.Key_Left:
            if self.has_selection():
                self.cursor_pos = min(self.selection_start, self.selection_end)
                self.selection_start = self.selection_end = self.cursor_pos
            elif self.cursor_pos > 0:
                self.cursor_pos -= 1
            self.update()
            return
        if event.key() == Qt.Key_Right:
            if self.has_selection():
                self.cursor_pos = max(self.selection_start, self.selection_end)
                self.selection_start = self.selection_end = self.cursor_pos
            elif self.cursor_pos < len(self.get_display_text()):
                self.cursor_pos += 1
            self.update()
            return
        if event.key() == Qt.Key_Up:
            if self.has_selection():
                self.cursor_pos = min(self.selection_start, self.selection_end)
                self.selection_start = self.selection_end = self.cursor_pos
            else:
                # Навигация по строкам
                line_info = self._get_cursor_line_info()
                if line_info['line_number'] > 0:
                    # Переходим на строку выше
                    target_line = line_info['line_number'] - 1
                    target_x = line_info['x_pos']
                    new_pos = self._get_pos_at_line_and_x(target_line, target_x)
                    self.cursor_pos = new_pos
                else:
                    # Уже на первой строке, переходим в начало
                    self.cursor_pos = 0
            self.selection_start = self.selection_end = self.cursor_pos
            self.update()
            return
        if event.key() == Qt.Key_Down:
            if self.has_selection():
                self.cursor_pos = max(self.selection_start, self.selection_end)
                self.selection_start = self.selection_end = self.cursor_pos
            else:
                # Навигация по строкам
                line_info = self._get_cursor_line_info()
                target_line = line_info['line_number'] + 1
                target_x = line_info['x_pos']
                new_pos = self._get_pos_at_line_and_x(target_line, target_x)
                if new_pos != self.cursor_pos:
                    self.cursor_pos = new_pos
                else:
                    # Уже на последней строке, переходим в конец
                    self.cursor_pos = len(self.get_display_text())
            self.selection_start = self.selection_end = self.cursor_pos
            self.update()
            return
        # Пробел — применить форматирование
        if event.key() == Qt.Key_Space:
            self.insert_text(' ')
            self.apply_formatting_by_markers()
            self._rebuild_raw()
            self.update()
            return
        # Backspace — возврат маркеров или удаление
        if event.key() == Qt.Key_Backspace:
            if self.has_selection():
                self.delete_selection()
                self._rebuild_raw()
                self.update()
                return
            if self.try_unformat_at_cursor():
                self._rebuild_raw()
                self.update()
            else:
                self.handle_backspace()
                self._rebuild_raw()
                self.update()
            return
        # Ввод обычного текста
        if event.text():
            if self.has_selection():
                self.delete_selection()
            self.insert_text(event.text())
            self._rebuild_raw()
            self.update()
            return
        super().keyPressEvent(event)

    def merge_plain_fragments(self):
        # Удаляем все полностью пустые фрагменты, кроме единственного
        self.fragments = [f for f in self.fragments if f.text or len(self.fragments) == 1]
        if not self.fragments:
            self.fragments = [TextFragment('')]
            return
        merged = []
        buffer = ''
        for frag in self.fragments:
            if not frag.formats:
                buffer += frag.text
            else:
                if buffer:
                    merged.append(TextFragment(buffer))
                    buffer = ''
                merged.append(frag)
        if buffer:
            merged.append(TextFragment(buffer))
        self.fragments = merged

    def insert_text(self, text):
        # Вставка текста в текущий фрагмент
        pos = self.cursor_pos
        for frag in self.fragments:
            if pos <= len(frag.text):
                frag.text = frag.text[:pos] + text + frag.text[pos:]
                self.cursor_pos += len(text)
                break
            else:
                pos -= len(frag.text)
        else:
            # Если не нашли подходящий фрагмент, создаем новый
            self.fragments.append(TextFragment(text))
            self.cursor_pos += len(text)
        self.merge_plain_fragments()

    def handle_backspace(self):
        if self.cursor_pos == 0:
            return
        display_text = self.get_display_text()
        # Удаляем символ слева от курсора
        new_text = display_text[:self.cursor_pos-1] + display_text[self.cursor_pos:]
        self.cursor_pos -= 1
        self.selection_start = self.selection_end = self.cursor_pos
        # Если текст стал пустым или состоит только из невидимых символов — сбрасываем к одному пустому фрагменту
        if not new_text.strip():
            self.fragments = [TextFragment('')]
            self.cursor_pos = 0
            self.selection_start = self.selection_end = 0
        else:
            self.fragments = [TextFragment(new_text)]
        parent = self.parent()
        if parent and hasattr(parent, 'force_scroll_to_cursor'):
            parent.force_scroll_to_cursor()

    def apply_formatting_by_markers(self):
        # Новый парсер: разбирает только те части текста, где есть маркеры, остальные фрагменты не трогает
        def parse_fragments(fragments):
            result = []
            changed = False
            for frag in fragments:
                # Если фрагмент уже форматирован (frag.formats не пустой), оставляем как есть
                if frag.formats:
                    result.append(frag)
                    continue
                # Если во фрагменте есть маркеры — парсим его
                text = frag.text
                def parse(text, active_formats=None):
                    if active_formats is None:
                        active_formats = []
                    patterns = [
                        (r'\*\*\*([^*]+)\*\*\*', ['bold', 'italic']),
                        (r'__([^_]+)__', ['underline']),
                        (r'\*\*([^*]+)\*\*', ['bold']),
                        (r'\*([^*]+)\*', ['italic']),
                        (r'~~([^~]+)~~', ['strike']),
                    ]
                    fragments = []
                    i = 0
                    found_marker = False
                    while i < len(text):
                        nearest = None
                        nearest_pat = None
                        nearest_fmts = None
                        nearest_start = None
                        for pat, fmts in patterns:
                            m = re.search(pat, text[i:])
                            if m:
                                start = m.start(0)
                                if nearest is None or start < nearest_start:
                                    nearest = m
                                    nearest_pat = pat
                                    nearest_fmts = fmts
                                    nearest_start = start
                        if nearest:
                            # Добавить обычный текст до маркера
                            if nearest_start > 0:
                                frag_text = text[i:i+nearest_start]
                                if frag_text:
                                    fragments.append(TextFragment(frag_text, active_formats.copy()))
                            found_marker = True
                            inner = nearest.group(1)
                            inner_frags = parse(inner, active_formats + nearest_fmts)[0]
                            fragments.extend(inner_frags)
                            i += nearest.start(0) + nearest.end(0)
                        else:
                            # Нет больше маркеров — добавляем остаток текста
                            frag_text = text[i:]
                            if frag_text:
                                fragments.append(TextFragment(frag_text, active_formats.copy()))
                            break
                    return fragments, found_marker
                new_frags, found_marker = parse(text)
                if found_marker:
                    result.extend(new_frags)
                    changed = True
                else:
                    result.append(frag)
            return result, changed
        # Применяем только к неформатированным фрагментам
        self.fragments, changed = parse_fragments(self.fragments)
        self.cursor_pos = len(self.get_display_text())

    def try_unformat_at_cursor(self):
        # Если выделение — снимаем форматирование с выделенного текста
        if self.has_selection():
            sel_min = min(self.selection_start, self.selection_end)
            sel_max = max(self.selection_start, self.selection_end)
            pos = 0
            new_fragments = []
            new_cursor_pos = None
            for frag in self.fragments:
                frag_len = len(frag.text)
                frag_start = pos
                frag_end = pos + frag_len
                if frag_end <= sel_min or frag_start >= sel_max:
                    new_fragments.append(frag)
                else:
                    left = max(sel_min - frag_start, 0)
                    right = max(frag_end - sel_max, 0)
                    frag_text = frag.text[left:frag_len-right] if right > 0 else frag.text[left:]
                    if frag_text:
                        markers, closing = self.get_combined_markers(frag.formats)
                        new_text = markers + frag_text + closing
                        new_fragments.append(TextFragment(new_text, []))
                        if new_cursor_pos is None:
                            new_cursor_pos = pos + len(markers) + len(frag_text)
                    if left > 0:
                        new_fragments.append(TextFragment(frag.text[:left], frag.formats.copy()))
                    if right > 0:
                        new_fragments.append(TextFragment(frag.text[-right:], frag.formats.copy()))
                pos += frag_len
            self.fragments = new_fragments if new_fragments else [TextFragment('')]
            self.cursor_pos = new_cursor_pos if new_cursor_pos is not None else sel_min
            self.selection_start = self.selection_end = self.cursor_pos
            return True
        # Если курсор вплотную к форматированному фрагменту — вернуть маркеры и снять формат
        pos = self.cursor_pos
        acc = 0
        for i, frag in enumerate(self.fragments):
            frag_len = len(frag.text)
            if acc <= pos < acc + frag_len and frag.formats:
                markers, closing = self.get_combined_markers(frag.formats)
                frag.text = markers + frag.text + closing
                frag.formats = []
                self.cursor_pos = acc + len(markers) + len(frag.text) - len(closing)
                self.selection_start = self.selection_end = self.cursor_pos
                return True
            if pos == acc + frag_len and frag.formats:
                markers, closing = self.get_combined_markers(frag.formats)
                frag.text = markers + frag.text + closing
                frag.formats = []
                self.cursor_pos = acc + len(markers) + len(frag.text) - len(closing)
                self.selection_start = self.selection_end = self.cursor_pos
                return True
            if pos == acc and frag.formats:
                markers, closing = self.get_combined_markers(frag.formats)
                frag.text = markers + frag.text + closing
                frag.formats = []
                self.cursor_pos = acc + len(markers) + len(frag.text) - len(closing)
                self.selection_start = self.selection_end = self.cursor_pos
                return True
            acc += frag_len
        return False

    def get_combined_markers(self, formats):
        # Для bold+italic — ***, для остальных комбинаций — вложенные маркеры
        fmts = set(formats)
        if fmts == {'bold', 'italic'}:
            return '***', '***'
        markers = ''.join({'bold': '**', 'italic': '*', 'strike': '~~', 'underline': '__'}[fmt] for fmt in formats)
        closing = ''.join({'bold': '**', 'italic': '*', 'strike': '~~', 'underline': '__'}[fmt] for fmt in reversed(formats))
        return markers, closing

    def get_raw_text(self):
        self._rebuild_raw()
        return self.raw_text

    def to_json(self):
        """Сериализует фрагменты в JSON-строку"""
        data = [
            {"text": frag.text, "formats": frag.formats} for frag in self.fragments
        ]
        return json.dumps(data, ensure_ascii=False)

    def from_json(self, json_str):
        """Восстанавливает фрагменты из JSON-строки"""
        try:
            data = json.loads(json_str)
            self.fragments = [TextFragment(item["text"], item["formats"]) for item in data]
            self.cursor_pos = sum(len(frag.text) for frag in self.fragments)
            self.selection_start = self.selection_end = self.cursor_pos
            self._rebuild_raw()
            self.update()
        except Exception as e:
            # Если не удалось — сбрасываем в обычный текст
            self.fragments = [TextFragment(json_str)]
            self.cursor_pos = len(json_str)
            self.selection_start = self.selection_end = self.cursor_pos
            self._rebuild_raw()
            self.update()

    def _get_scroll_offset(self):
        # scroll_offset больше не нужен, всегда возвращаем 0
        return 0

    def _mouse_pos_to_text_pos(self, mouse_x, mouse_y):
        layout = self.layout_text()
        min_dist = float('inf')
        best_pos = 0
        for item in layout:
            m = item['metrics']
            x, y, w = item['x'], item['y'], m.width(item['char'])
            if y - m.ascent() <= mouse_y <= y + m.descent():
                if x <= mouse_x < x + w:
                    return item['pos']
                if mouse_x < layout[0]['x']:
                    return 0
                if mouse_x > x + w:
                    best_pos = item['pos']
            dist = abs(mouse_y - y)
            if dist < min_dist:
                min_dist = dist
                best_pos = item['pos']
        return best_pos

    def _get_cursor_line_info(self):
        """Возвращает информацию о текущей строке курсора с учетом переноса по словам"""
        margin_left = 10
        margin_top = 30  # Вернул вертикальный отступ
        margin_right = 10
        line_height = self.fontMetrics().height() + 4
        max_text_width = self.width() - margin_left - margin_right
        
        x, y = margin_left, margin_top
        pos = 0
        current_line_start = 0
        current_line_y = margin_top
        
        for frag in self.fragments:
            f = QFont('Finlandica', 12)
            if 'bold' in frag.formats:
                f.setWeight(QFont.Bold)
            if 'italic' in frag.formats:
                f.setItalic(True)
            if 'underline' in frag.formats:
                f.setUnderline(True)
            if 'strike' in frag.formats:
                f.setStrikeOut(True)
            
            metrics = QFontMetrics(f)
            
            # Разбиваем текст фрагмента на слова
            words = self._split_text_into_words(frag.text)
            
            for word in words:
                word_width = metrics.width(word)
                
                # Проверяем, нужно ли перенести на новую строку
                if x + word_width > max_text_width and x > margin_left:
                    x = margin_left
                    y += line_height
                    current_line_start = pos
                    current_line_y = y
                
                # Проверяем позицию курсора
                for ch in word:
                    if pos == self.cursor_pos:
                        return {
                            'line_start': current_line_start,
                            'line_y': current_line_y,
                            'x_pos': x,
                            'line_number': (current_line_y - margin_top) // line_height
                        }
                    char_width = metrics.width(ch)
                    x += char_width
                    pos += 1
        
        return {
            'line_start': current_line_start,
            'line_y': current_line_y,
            'x_pos': x,
            'line_number': (current_line_y - margin_top) // line_height
        }

    def _get_pos_at_line_and_x(self, target_line, target_x):
        """Возвращает позицию в тексте для заданной строки и X-координаты с учетом переноса по словам"""
        margin_left = 10
        margin_top = 30  # Вернул вертикальный отступ
        margin_right = 10
        line_height = self.fontMetrics().height() + 4
        max_text_width = self.width() - margin_left - margin_right
        
        x, y = margin_left, margin_top
        pos = 0
        current_line = 0
        
        for frag in self.fragments:
            f = QFont('Finlandica', 12)
            if 'bold' in frag.formats:
                f.setWeight(QFont.Bold)
            if 'italic' in frag.formats:
                f.setItalic(True)
            if 'underline' in frag.formats:
                f.setUnderline(True)
            if 'strike' in frag.formats:
                f.setStrikeOut(True)
            
            metrics = QFontMetrics(f)
            
            # Разбиваем текст фрагмента на слова
            words = self._split_text_into_words(frag.text)
            
            for word in words:
                word_width = metrics.width(word)
                
                # Проверяем, нужно ли перенести на новую строку
                if x + word_width > max_text_width and x > margin_left:
                    x = margin_left
                    y += line_height
                    current_line += 1
                
                if current_line == target_line:
                    # Мы на нужной строке, ищем ближайшую позицию к target_x
                    if x <= target_x < x + word_width:
                        # Курсор внутри слова
                        for ch in word:
                            if x <= target_x < x + metrics.width(ch):
                                return pos
                            x += metrics.width(ch)
                            pos += 1
                        return pos
                    elif target_x < x:
                        return pos
                
                # Перемещаемся по символам слова
                for ch in word:
                    x += metrics.width(ch)
                    pos += 1
            
            # Если мы прошли нужную строку, возвращаем конец строки
            if current_line > target_line:
                return pos
        
        return len(self.get_display_text())

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            clicked_pos = self._mouse_pos_to_text_pos(event.x(), event.y())
            self.cursor_pos = clicked_pos
            self.selection_start = clicked_pos
            self.selection_end = clicked_pos
            self._mouse_selecting = True
            self.update()

    def mouseMoveEvent(self, event):
        if self._mouse_selecting:
            new_pos = self._mouse_pos_to_text_pos(event.x(), event.y())
            # Не сбрасываем выделение, если мышь вне текста, а ставим в начало/конец
            self.selection_end = new_pos
            self.cursor_pos = new_pos
            self.update()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            clicked_pos = self._mouse_pos_to_text_pos(event.x(), event.y())
            # Выделяем слово под курсором
            text = self.get_display_text()
            if not text:
                return
            # Найти границы слова
            left = clicked_pos
            right = clicked_pos
            while left > 0 and text[left-1].isalnum():
                left -= 1
            while right < len(text) and text[right].isalnum():
                right += 1
            self.selection_start = left
            self.selection_end = right
            self.cursor_pos = right
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            # Тройной клик — выделить всю строку (в нашем случае — весь текст)
            if event.type() == event.MouseButtonDblClick and hasattr(self, '_last_release_time'):
                import time
                now = time.time()
                if hasattr(self, '_last_release_time') and now - self._last_release_time < 0.5:
                    # Тройной клик
                    self.selection_start = 0
                    self.selection_end = len(self.get_display_text())
                    self.cursor_pos = self.selection_end
                    self.update()
                self._last_release_time = now
            else:
                self._mouse_selecting = False
                import time
                self._last_release_time = time.time()

    def has_selection(self):
        return self.selection_start is not None and self.selection_end is not None and self.selection_start != self.selection_end

    def delete_selection(self):
        if not self.has_selection():
            return
        sel_min = min(self.selection_start, self.selection_end)
        sel_max = max(self.selection_start, self.selection_end)
        pos = 0
        new_fragments = []
        for frag in self.fragments:
            frag_len = len(frag.text)
            frag_start = pos
            frag_end = pos + frag_len
            if frag_end <= sel_min or frag_start >= sel_max:
                new_fragments.append(frag)
            else:
                # Оставить невыделенные части
                left = max(sel_min - frag_start, 0)
                right = max(frag_end - sel_max, 0)
                if left > 0:
                    new_fragments.append(TextFragment(frag.text[:left], frag.formats))
                if right > 0:
                    new_fragments.append(TextFragment(frag.text[-right:], frag.formats))
            pos += frag_len
        self.fragments = new_fragments if new_fragments else [TextFragment('')]
        self.cursor_pos = sel_min
        self.selection_start = self.selection_end = self.cursor_pos

    def copy_selection(self):
        sel_min = min(self.selection_start, self.selection_end)
        sel_max = max(self.selection_start, self.selection_end)
        pos = 0
        fragments_to_copy = []
        for frag in self.fragments:
            frag_len = len(frag.text)
            frag_start = pos
            frag_end = pos + frag_len
            if frag_end <= sel_min or frag_start >= sel_max:
                pass
            else:
                left = max(sel_min - frag_start, 0)
                right = max(frag_end - sel_max, 0)
                frag_text = frag.text[left:frag_len-right] if right > 0 else frag.text[left:]
                if frag_text:
                    fragments_to_copy.append(TextFragment(frag_text, frag.formats.copy()))
            pos += frag_len
        # Сохраняем в буфер обмена как сериализованный текст с маркерами
        temp_editor = CustomRichTextEditor.create_temp_editor()
        temp_editor.fragments = fragments_to_copy
        temp_editor._rebuild_raw()
        clipboard = QApplication.clipboard()
        clipboard.setText(temp_editor.raw_text)

    def paste_clipboard(self):
        clipboard = QApplication.clipboard()
        text = clipboard.text()
        if not text:
            return
        # Если есть выделение — удаляем её
        if self.has_selection():
            self.delete_selection()
        # Вставляем текст как один фрагмент (с сохранением всех переносов)
        pos = self.cursor_pos
        new_fragments = []
        acc = 0
        inserted = False
        for frag in self.fragments:
            frag_len = len(frag.text)
            if not inserted and acc + frag_len >= pos:
                left = pos - acc
                if left > 0:
                    new_fragments.append(TextFragment(frag.text[:left], frag.formats.copy()))
                new_fragments.append(TextFragment(text))
                if left < frag_len:
                    new_fragments.append(TextFragment(frag.text[left:], frag.formats.copy()))
                inserted = True
            else:
                new_fragments.append(frag)
            acc += frag_len
        if not inserted:
            new_fragments.append(TextFragment(text))
        self.fragments = [f for f in new_fragments if f.text or len(new_fragments) == 1]
        self.merge_plain_fragments()
        self.cursor_pos = pos + len(text)
        self.selection_start = self.selection_end = self.cursor_pos
        parent = self.parent()
        if parent and hasattr(parent, 'force_scroll_to_cursor'):
            parent.force_scroll_to_cursor()

    def _blink_cursor(self):
        if self.hasFocus() and not self._mouse_selecting:
            self._cursor_visible = not self._cursor_visible
            self.update()
        else:
            self._cursor_visible = True
            self.update()

    def focusInEvent(self, event):
        self._cursor_timer.start(500)
        self._cursor_visible = True
        self.update()
        super().focusInEvent(event)

    def focusOutEvent(self, event):
        self._cursor_timer.stop()
        self._cursor_visible = False
        self.update()
        super().focusOutEvent(event)

    def layout_text(self):
        margin_left = 10
        margin_top = 30
        margin_right = 10
        line_height = self.fontMetrics().height() + 4
        max_text_width = self.width() - margin_left - margin_right
        x, y = margin_left, margin_top
        pos = 0
        line = 0
        layout = []
        tab_width = self.fontMetrics().width(' ') * 6
        for frag in self.fragments:
            f = QFont('Finlandica', 12)
            if 'bold' in frag.formats:
                f.setWeight(QFont.Bold)
            if 'italic' in frag.formats:
                f.setItalic(True)
            if 'underline' in frag.formats:
                f.setUnderline(True)
            if 'strike' in frag.formats:
                f.setStrikeOut(True)
            metrics = QFontMetrics(f)
            # Новый блок: разбиваем по \n
            lines = frag.text.split('\n')
            for line_idx, line_text in enumerate(lines):
                i = 0
                while i < len(line_text):
                    if line_text[i] == '\t':
                        layout.append({'x': x, 'y': y, 'char': '', 'pos': pos, 'line': line, 'font': f, 'metrics': metrics, 'frag': frag, 'tab': True})
                        x += tab_width
                        i += 1
                        pos += 1
                        continue
                    # Обычный текст
                    word = ''
                    while i < len(line_text) and line_text[i] != '\t':
                        word += line_text[i]
                        i += 1
                    if word:
                        for ch in word:
                            char_width = metrics.width(ch)
                            layout.append({'x': x, 'y': y, 'char': ch, 'pos': pos, 'line': line, 'font': f, 'metrics': metrics, 'frag': frag})
                            x += char_width
                            pos += 1
                # Если это не последняя строка — перенос
                if line_idx < len(lines) - 1:
                    # ВАЖНО: явно добавляем символ переноса строки в layout!
                    layout.append({'x': x, 'y': y, 'char': '\n', 'pos': pos, 'line': line, 'font': f, 'metrics': metrics, 'frag': frag})
                    pos += 1
                    x = margin_left
                    y += line_height
                    line += 1
        # "виртуальный" символ для конца текста
        layout.append({'x': x, 'y': y, 'char': '', 'pos': pos, 'line': line, 'font': self.font, 'metrics': QFontMetrics(self.font), 'frag': None})
        return layout

class ScrollableRichTextEditor(QScrollArea):
    def __init__(self, parent=None, width=400, height=300):
        super().__init__(parent)
        self.editor = CustomRichTextEditor()
        self.setWidget(self.editor)
        self.setWidgetResizable(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setFixedSize(width, height)
        self.max_editor_height = 10 * (self.editor.fontMetrics().height() + 4) + 40
        self.editor.setMaximumHeight(self.max_editor_height)
        self.editor.scroll_needed.connect(self._check_scroll_needed)
        self._autoscroll_enabled = True
        self._autoscroll_timer = QTimer(self)
        self._autoscroll_timer.setSingleShot(True)
        self._autoscroll_timer.timeout.connect(self._enable_autoscroll)
        # self.setTabChangesFocus(False)  # Удаляем, чтобы не было ошибки
        # --- Стилизация контейнера ---
        self.setStyleSheet('''
            QScrollArea {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
        ''')

    def wheelEvent(self, event):
        # При прокрутке колесом мыши временно отключаем автоскролл
        self._autoscroll_enabled = False
        self._autoscroll_timer.start(700)  # 700 мс без автоскролла
        super().wheelEvent(event)

    def _enable_autoscroll(self):
        self._autoscroll_enabled = True

    def _check_scroll_needed(self):
        if not self._autoscroll_enabled:
            return
        if not hasattr(self.editor, 'cursor_pos'):
            return
        # Получаем информацию о позиции курсора
        line_info = self.editor._get_cursor_line_info()
        if not line_info:
            return
        cursor_y = line_info['line_y']
        viewport_height = self.viewport().height()
        scroll_pos = self.verticalScrollBar().value()
        # Проверяем, виден ли курсор
        if cursor_y < scroll_pos + 50:  # 50px отступ сверху
            # Курсор выше видимой области, прокручиваем вверх
            self.verticalScrollBar().setValue(max(0, cursor_y - 50))
        elif cursor_y > scroll_pos + viewport_height - 50:  # 50px отступ снизу
            # Курсор ниже видимой области, прокручиваем вниз
            new_scroll_pos = cursor_y - viewport_height + 50
            max_scroll = self.verticalScrollBar().maximum()
            self.verticalScrollBar().setValue(min(new_scroll_pos, max_scroll))
        # Если курсор в поле зрения — ничего не делаем
    
    def get_display_text(self):
        return self.editor.get_display_text()
    
    def get_raw_text(self):
        return self.editor.get_raw_text()
    
    def set_text(self, text):
        """Устанавливает текст в редактор"""
        self.editor.fragments = [TextFragment(text)]
        self.editor.cursor_pos = len(text)
        self.editor.selection_start = self.editor.selection_end = self.editor.cursor_pos
        self.editor._rebuild_raw()
        self.editor.apply_formatting_by_markers()  # Автоматически применяем форматирование по маркерам
        self.editor.update()
        self.force_scroll_to_cursor()
    
    def keyPressEvent(self, event):
        # Всегда передаём Tab (и любые клавиши) только во внутренний редактор
        self.editor.keyPressEvent(event)
        # Не вызываем super().keyPressEvent(event), чтобы Tab не прокручивал

    def focusInEvent(self, event):
        # Передаем фокус редактору
        self.editor.setFocus()
        super().focusInEvent(event)

    def paintEvent(self, event):
        # Затемнённый фон с закруглением, как у ColorPickerDialog
        painter = QPainter(self.viewport())
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.viewport().rect().adjusted(1,1,-1,-1)
        painter.setBrush(QColor(0,0,0,145))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 14, 14)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 14, 14)
        super().paintEvent(event)

    def force_scroll_to_cursor(self):
        """Принудительно прокручивает к курсору, игнорируя блокировку автоскролла."""
        prev = self._autoscroll_enabled
        self._autoscroll_enabled = True
        self._check_scroll_needed()
        self._autoscroll_enabled = prev

    def to_json(self):
        return self.editor.to_json()

    def from_json(self, json_str):
        self.editor.from_json(json_str)

class CustomTextEditDialog(QDialog):
    def __init__(self, initial_text='', parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(320)
        # --- Фон и оформление ---
        self._background_widget = QWidget(self)
        self._background_widget.setObjectName('background')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._background_widget)
        bg_layout = QVBoxLayout(self._background_widget)
        bg_layout.setContentsMargins(18, 18, 18, 18)
        bg_layout.setSpacing(18)
        # --- Редактор ---
        self.editor = ScrollableRichTextEditor(width=380, height=180)
        self.editor.set_text(initial_text)
        bg_layout.addWidget(self.editor)
        # --- Кнопки ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(18)
        btn_layout.addStretch(1)
        self.ok_btn = GlassMenuButton('Сохранить', self)
        self.cancel_btn = GlassMenuButton('Отмена', self)
        self.ok_btn.setFixedHeight(38)
        self.cancel_btn.setFixedHeight(38)
        self.ok_btn.setMinimumWidth(130)
        self.cancel_btn.setMinimumWidth(130)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch(1)
        bg_layout.addLayout(btn_layout)
        bg_layout.addSpacing(6)
        self.ok_btn.clicked.connect(self.accept)
        self.cancel_btn.clicked.connect(self.reject)
        # --- Стили ---
        self.setStyleSheet('''
            #background {
                background: #757575;
                border-radius: 16px;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.75);
                color: #222;
                border: none;
                border-radius: 7px;
                font-size: 11pt;
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 7px 34px;
            }
            QPushButton:hover {
                background-color: #fff;
                border: 2px solid #888;
                color: #111;
            }
            QPushButton:pressed {
                background-color: #f0f0f0;
                border: 2px solid #888;
                color: #111;
            }
        ''')
        self._background_widget.paintEvent = self._paint_background

    def _paint_background(self, event):
        painter = QPainter(self._background_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self._background_widget.rect().adjusted(1,1,-1,-1)
        painter.setBrush(QColor(110,110,110,235))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 16, 16)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 16, 16)

    def get_text(self):
        return self.editor.get_display_text()

    def get_formatted_json(self):
        return self.editor.to_json()

class TxtFileEditDialog(QDialog):
    def __init__(self, initial_title='', initial_text='', existing_titles=None, parent=None):
        super().__init__(parent)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setModal(True)
        self.setMinimumWidth(420)
        self.setMinimumHeight(380)
        self._existing_titles = set(existing_titles) if existing_titles else set()
        # --- Фон и оформление ---
        self._background_widget = QWidget(self)
        self._background_widget.setObjectName('background')
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._background_widget)
        bg_layout = QVBoxLayout(self._background_widget)
        bg_layout.setContentsMargins(18, 18, 18, 18)
        bg_layout.setSpacing(18)
        # --- Название файла ---
        title_layout = QHBoxLayout()
        title_label = QLabel('Имя файла:')
        self.title_edit = QLineEdit()
        self.title_edit.setText(initial_title.replace('.txt', ''))
        title_layout.addWidget(title_label)
        title_layout.addWidget(self.title_edit)
        bg_layout.addLayout(title_layout)
        # --- Редактор текста ---
        self.editor = ScrollableRichTextEditor(width=380, height=180)
        self.editor.set_text(initial_text)
        bg_layout.addWidget(self.editor)
        # --- Кнопки ---
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(18)
        btn_layout.addStretch(1)
        self.ok_btn = GlassMenuButton('Сохранить', self)
        self.cancel_btn = GlassMenuButton('Отмена', self)
        self.ok_btn.setFixedHeight(38)
        self.cancel_btn.setFixedHeight(38)
        self.ok_btn.setMinimumWidth(130)
        self.cancel_btn.setMinimumWidth(130)
        btn_layout.addWidget(self.ok_btn)
        btn_layout.addWidget(self.cancel_btn)
        btn_layout.addStretch(1)
        bg_layout.addLayout(btn_layout)
        bg_layout.addSpacing(6)
        self.ok_btn.clicked.connect(self._on_accept)
        self.cancel_btn.clicked.connect(self.reject)
        self.setStyleSheet('''
            #background {
                background: #757575;
                border-radius: 16px;
            }
            QLabel {
                color: #fff;
                font-size: 10pt;
                font-family: Arial;
                background-color: transparent;
                border: none;
            }
            QLineEdit {
                background: #fff;
                border-radius: 7px;
                padding: 6px 12px;
                font-size: 11pt;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.75);
                color: #222;
                border: none;
                border-radius: 7px;
                font-size: 11pt;
                font-family: 'Segoe UI', Arial, sans-serif;
                padding: 7px 34px;
            }
            QPushButton:hover {
                background-color: #fff;
                border: 2px solid #888;
                color: #111;
            }
            QPushButton:pressed {
                background-color: #f0f0f0;
                border: 2px solid #888;
                color: #111;
            }
        ''')
        self._background_widget.paintEvent = self._paint_background

    def set_existing_titles(self, titles):
        self._existing_titles = set(titles)

    def _paint_background(self, event):
        painter = QPainter(self._background_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self._background_widget.rect().adjusted(1,1,-1,-1)
        painter.setBrush(QColor(110,110,110,235))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 16, 16)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 16, 16)

    def get_title(self):
        t = self.title_edit.text().strip()
        if not t.lower().endswith('.txt'):
            t += '.txt'
        return t

    def get_text(self):
        return self.editor.get_display_text()

    def get_formatted_json(self):
        return self.editor.to_json()

    def _on_accept(self):
        title = self.get_title()
        if title in self._existing_titles:
            QMessageBox.warning(self, 'Ошибка', f'Файл с именем "{title}" уже существует!')
            return
        if not title or title == '.txt':
            QMessageBox.warning(self, 'Ошибка', 'Введите имя файла!')
            return
        self.accept()

if __name__ == '__main__':
    import sys
    app = QApplication(sys.argv)
    w = ScrollableRichTextEditor()
    # Редактор уже имеет фиксированный размер 400x300
    w.show()
    sys.exit(app.exec_()) 