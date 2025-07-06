import math
from PyQt5.QtCore import Qt, QPointF, pyqtSignal, QSize, QRectF, QRect
from PyQt5.QtGui import (QPainter, QColor, QConicalGradient, QLinearGradient, 
                       QPen, QBrush, QImage, QFont, QPainterPath)
from PyQt5.QtWidgets import (QDialog, QWidget, QVBoxLayout, QHBoxLayout, 
                             QFrame, QDialogButtonBox, QLabel, QPushButton, QSizePolicy, QStyleOptionButton, QStylePainter, QStyle, QScrollArea)

class ColorPicker(QWidget):
    """
    Основной виджет выбора цвета, включающий кольцо оттенков (hue)
    и квадрат насыщенности/яркости (saturation/value).
    """
    colorChanged = pyqtSignal(QColor)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(250, 250)
        
        self._hue = 0.0
        self._saturation = 1.0
        self._value = 1.0
        
        self._wheel_width = 25
        self._margin = 5
        
        self._sv_image = QImage()
        self._in_sv_rect = False
        self._in_hue_ring = False
        self._is_mouse_down = False
        self._sv_rect = QRectF()

    def sizeHint(self):
        return QSize(250, 250)
    
    def set_color(self, color):
        h, s, v, _ = color.getHsvF()
        if h < 0: h = 0 
        self._hue = h
        self._saturation = s
        self._value = v
        self._update_sv_image()
        self.update()
        self.colorChanged.emit(self.get_color())

    def get_color(self):
        return QColor.fromHsvF(self._hue, self._saturation, self._value)

    def _update_sv_image(self):
        if self._sv_rect.isEmpty():
            return
            
        size = self._sv_rect.size().toSize()
        if self._sv_image.isNull() or size != self._sv_image.size():
            self._sv_image = QImage(size, QImage.Format_ARGB32)

        painter = QPainter(self._sv_image)
        
        s_gradient = QLinearGradient(0, 0, size.width(), 0)
        s_gradient.setColorAt(0, Qt.white)
        s_gradient.setColorAt(1, QColor.fromHsvF(self._hue, 1.0, 1.0))
        painter.fillRect(self._sv_image.rect(), s_gradient)

        v_gradient = QLinearGradient(0, 0, 0, size.height())
        v_gradient.setColorAt(0, Qt.transparent)
        v_gradient.setColorAt(1, Qt.black)
        painter.fillRect(self._sv_image.rect(), v_gradient)
        painter.end()

    def paintEvent(self, event):
        outer_gap = 16  # отступ кольца от края виджета
        gap = 3         # зазор между квадратом и кольцом
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        size = min(self.width(), self.height())
        self._outer_rect = QRect(0, 0, size, size)
        self._outer_rect.moveCenter(self.rect().center())

        outer_radius = (size / 2.0) - outer_gap
        inner_radius = outer_radius - self._wheel_width
        sv_radius = inner_radius - gap
        sv_size = sv_radius * 2 / math.sqrt(2)
        sv_center = self._outer_rect.center()
        self._sv_rect = QRectF(0, 0, sv_size, sv_size)
        self._sv_rect.moveCenter(sv_center)

        self._draw_hue_wheel(painter, inner_radius, outer_radius)

        if self._sv_image.isNull():
            self._update_sv_image()
        painter.drawImage(self._sv_rect.topLeft(), self._sv_image)

        self._draw_selectors(painter)

    def _draw_hue_wheel(self, painter, inner_radius, outer_radius):
        gradient = QConicalGradient(self._outer_rect.center(), 0)
        for i in range(361):
            hue = i / 360.0
            gradient.setColorAt(i / 360.0, QColor.fromHsvF(hue, 1.0, 1.0))
        path = QPainterPath()
        center = self._outer_rect.center()
        path.addEllipse(center, outer_radius, outer_radius)
        path.addEllipse(center, inner_radius, inner_radius)
        painter.setBrush(gradient)
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)

    def _draw_selectors(self, painter):
        # Используем те же параметры, что и для кольца
        outer_gap = 16
        outer_radius = (self._outer_rect.width() / 2.0) - outer_gap
        inner_radius = outer_radius - self._wheel_width
        selector_radius = (outer_radius + inner_radius) / 2

        angle_rad = math.radians(self._hue * 360.0)
        center = self._outer_rect.center()
        hue_pos = QPointF(center.x() + selector_radius * math.cos(angle_rad),
                         center.y() - selector_radius * math.sin(angle_rad))
        
        painter.setPen(QPen(Qt.white, 2))
        painter.setBrush(self.get_color())
        painter.drawEllipse(hue_pos, 10, 10)

        sv_x = self._sv_rect.left() + self._saturation * self._sv_rect.width()
        sv_y = self._sv_rect.top() + (1.0 - self._value) * self._sv_rect.height()
        sv_pos = QPointF(sv_x, sv_y)
        selector_color = Qt.white if self._value < 0.5 else Qt.black
        painter.setPen(QPen(selector_color, 2))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(sv_pos, 6, 6)

    def mousePressEvent(self, event):
        self._is_mouse_down = True
        self._handle_mouse_event(event.pos())

    def mouseMoveEvent(self, event):
        if self._is_mouse_down:
            self._handle_mouse_event(event.pos())
            
    def mouseReleaseEvent(self, event):
        self._is_mouse_down = False
        self._in_hue_ring = False
        self._in_sv_rect = False

    def _handle_mouse_event(self, pos):
        size = min(self.width(), self.height())
        outer_gap = 16
        center = self.rect().center()
        dx = pos.x() - center.x()
        dy = pos.y() - center.y()
        radius = math.sqrt(dx**2 + dy**2)

        outer_r = (size / 2.0) - outer_gap
        inner_r = outer_r - self._wheel_width

        is_in_hue = inner_r <= radius <= outer_r
        is_in_sv = self._sv_rect.contains(pos)
        
        if self._is_mouse_down and not self._in_hue_ring and not self._in_sv_rect:
            if is_in_hue:
                self._in_hue_ring = True
            elif is_in_sv:
                self._in_sv_rect = True

        if self._in_hue_ring:
            angle = math.degrees(math.atan2(-dy, dx))
            positive_angle = (angle + 360) % 360
            self._hue = positive_angle / 360.0
            self._update_sv_image()
        elif self._in_sv_rect:
            x = max(0, min(pos.x() - self._sv_rect.left(), self._sv_rect.width()))
            y = max(0, min(pos.y() - self._sv_rect.top(), self._sv_rect.height()))
            
            self._saturation = x / self._sv_rect.width()
            self._value = 1.0 - (y / self._sv_rect.height())

        self.update()
        self.colorChanged.emit(self.get_color())

class GlassMenuButton(QPushButton):
    def __init__(self, text, parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(34)
        self.setMinimumWidth(90)
        self.setFont(QFont('Segoe UI', 10, QFont.Bold))
        self._padding_lr = 18
        self._padding_tb = 7
        self.setStyleSheet('''
    QLabel { ... }
    QPushButton { ... }
    QScrollArea, QScrollArea > QWidget, QScrollArea QWidget, QScrollArea > QViewport, QScrollArea QViewport, QAbstractScrollArea, QAbstractScrollArea > QViewport {
        background: transparent;
        border: none;
    }
    QScrollBar:horizontal { ... }
    /* ... */
''')

    def paintEvent(self, event):
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect()
        # Определяем состояние
        hovered = self.underMouse()
        pressed = self.isDown()
        enabled = self.isEnabled()
        # Цвета
        if pressed:
            bg = QColor('#f0f0f0')
            border = QColor('#888')
            text = QColor('#111')
        elif hovered:
            bg = QColor('#ffffff')
            border = QColor('#888')
            text = QColor('#111')
        else:
            if enabled:
                if self.text() == 'Отмена':
                    bg = QColor('#EAEAEA')
                    border = QColor(0,0,0,0)
                    text = QColor('#333')
                else:
                    bg = QColor(255,255,255,192)
                    border = QColor(0,0,0,0)
                    text = QColor('#222')
            else:
                bg = QColor(220,220,220,180)
                border = QColor(0,0,0,0)
                text = QColor('#888')
        # Фон
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect.adjusted(1,1,-1,-1), 7, 7)
        # Рамка
        if border.alpha() > 0:
            painter.setPen(QPen(border, 1.5))
            painter.setBrush(Qt.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1,1,-1,-1), 7, 7)
        # Текст
        painter.setPen(text)
        font = self.font()
        painter.setFont(font)
        text_rect = rect.adjusted(self._padding_lr, self._padding_tb, -self._padding_lr, -self._padding_tb)
        painter.drawText(text_rect, Qt.AlignCenter, self.text())

class ColorPickerDialog(QDialog):
    """
    Диалоговое окно для выбора цвета, использующее виджет ColorPicker.
    """
    eyedropper_activated = pyqtSignal()
    STANDARD_COLORS = [
        QColor('#ff0000'), QColor('#00ff00'), QColor('#0000ff'), QColor('#ffff00'), QColor('#a020f0'),
        QColor('#00ffff'), QColor('#ffa500'), QColor('#800080'), QColor('#808080'), QColor('#4682b4'),
        QColor('#ffc0cb'), QColor('#008080'), QColor('#e6e6fa'), QColor('#ff7f50'), QColor('#3cb371'),
        QColor('#b0c4de'), QColor('#d2b48c'), QColor('#f08080'), QColor('#dda0dd'), QColor('#ff6347')
    ]

    def __init__(self, initial_color=Qt.white, history_colors=None, parent=None):
        super().__init__(parent)
        if not history_colors or len(history_colors) < 1:
            history_colors = self.STANDARD_COLORS.copy()
        else:
            history_colors = list(history_colors)[-20:]
            i = 0
            while len(history_colors) < 20 and i < len(self.STANDARD_COLORS):
                c = self.STANDARD_COLORS[i]
                if c not in history_colors:
                    history_colors.append(c)
                i += 1
        self._history_colors = history_colors
        self.setWindowTitle("Выбор цвета")
        self.setMinimumWidth(300)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(self.windowFlags() | Qt.FramelessWindowHint)
        self.background_widget = QWidget(self)
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)
        outer_layout.addWidget(self.background_widget)
        main_layout = QVBoxLayout(self.background_widget)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)

        self.setStyleSheet('''
            QLabel {
                color: #fff;
                font-size: 10pt;
                font-family: Arial;
                background-color: transparent;
                border: none;
            }
            QPushButton {
                background-color: rgba(255,255,255,0.75);
                color: #222;
                border: none;
                border-radius: 7px;
                padding: 7px 22px;
                font-size: 10pt;
                font-family: Arial;
            }
            QPushButton:hover {
                background-color: #fff;
                border: 1.5px solid #888;
                color: #111;
            }
            QPushButton:pressed {
                background-color: #f0f0f0;
                border: 1.5px solid #888;
                color: #111;
            }
            QScrollArea {
                background: transparent;
                border: none;
                border-radius: 0px;
            }
            QScrollBar:horizontal {
                background: transparent;
                height: 4px;
                margin: 0px 18px 0 18px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255,255,255,0.45);
                min-width: 24px;
                border-radius: 2px;
            }
            QScrollBar::handle:horizontal:hover {
                background: rgba(255,255,255,0.7);
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
                border: none;
                width: 0px;
            }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: none;
            }
        ''')
        self.color_picker = ColorPicker()
        self.color_picker.set_color(QColor(initial_color))
        preview_layout = QHBoxLayout()
        self.preview_old = self._create_swatch(QColor(initial_color))
        self.preview_new = self._create_swatch(QColor(initial_color))
        preview_layout.addWidget(self.preview_old)
        preview_layout.addWidget(self.preview_new)

        self.eyedropper_btn = QPushButton("💧")
        self.eyedropper_btn.setFixedSize(60, 60)
        self.eyedropper_btn.setToolTip("Выбрать цвет с элемента")
        font = self.eyedropper_btn.font()
        font.setPointSize(20)
        self.eyedropper_btn.setFont(font)
        self.eyedropper_btn.setStyleSheet("""
            QPushButton {
                background-color: rgba(0, 0, 0, 0.2);
                color: white;
                border: 1.5px solid #c0c0c0;
                border-radius: 8px;
            }
            QPushButton:hover {
                background-color: rgba(0, 0, 0, 0.3);
            }
            QPushButton:pressed {
                background-color: rgba(0, 0, 0, 0.35);
            }
        """)
        self.eyedropper_btn.clicked.connect(self._activate_eyedropper)
        preview_layout.addWidget(self.eyedropper_btn)

        main_layout.addLayout(preview_layout)
        main_layout.addWidget(self.color_picker)
        # --- История выбора цветов ---
        self.history_scroll_area = QScrollArea(self.background_widget)
        self.history_scroll_area.setWidgetResizable(True)
        self.history_scroll_area.setFixedHeight(38)
        self.history_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.history_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.history_scroll_area.viewport().setStyleSheet("background: transparent;")

        self.history_content_widget = QWidget()
        self.history_layout = QHBoxLayout(self.history_content_widget)
        self.history_layout.setContentsMargins(6, 4, 6, 4)
        self.history_layout.setSpacing(6)
        
        self.history_scroll_area.setWidget(self.history_content_widget)

        self._update_history_buttons()
        main_layout.addWidget(self.history_scroll_area)
        # ---
        self.button_box = QDialogButtonBox(self)
        self.save_btn = GlassMenuButton("Сохранить", self)
        self.cancel_btn = GlassMenuButton("Отмена", self)
        self.button_box.addButton(self.save_btn, QDialogButtonBox.AcceptRole)
        self.button_box.addButton(self.cancel_btn, QDialogButtonBox.RejectRole)
        main_layout.addWidget(self.button_box)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.color_picker.colorChanged.connect(self._on_color_picked)
        self._mouse_pressed = False
        self._mouse_press_pos = QPointF(0, 0)
        self.background_widget.paintEvent = self._paint_background_widget

    def _update_history_buttons(self):
        while self.history_layout.count():
            item = self.history_layout.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        for color in self._history_colors:
            btn = QPushButton("")
            btn.setStyleSheet(f"background-color: {color.name()}; border: 1.5px solid rgba(255,255,255,0); border-radius: 7px;")
            btn.setFixedSize(24, 24)
            btn.clicked.connect(lambda checked, c=color: self.color_picker.set_color(c))
            self.history_layout.addWidget(btn)

    def _on_color_picked(self, color):
        self._update_preview(QColor(color))

    def _paint_background_widget(self, event):
        painter = QPainter(self.background_widget)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.background_widget.rect().adjusted(1,1,-1,-1)
        painter.setBrush(QBrush(QColor(0,0,0,145)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 14, 14)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 14, 14)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._mouse_pressed = True
            self._mouse_press_pos = event.globalPos() - self.pos()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._mouse_pressed and event.buttons() == Qt.LeftButton:
            self.move(event.globalPos() - self._mouse_press_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._mouse_pressed = False
            event.accept()

    def _create_swatch(self, color):
        swatch = QLabel()
        swatch.setMinimumSize(60, 60)
        swatch.setStyleSheet(f"background-color: {color.name()}; border: 1.5px solid #c0c0c0; border-radius: 8px;")
        return swatch

    def _update_preview(self, color):
        self.preview_new.setStyleSheet(f"background-color: {color.name()}; border: 1px solid #c0c0c0; border-radius: 8px;")

    def selected_color(self):
        return self.color_picker.get_color()

    def accept(self):
        color = self.selected_color()
        # Если цвет уже есть в истории, просто перемещаем его в начало, не добавляя дубликат
        self._history_colors = [c for c in self._history_colors if c.name() != color.name()]
        self._history_colors.insert(0, color)
        self._history_colors = self._history_colors[:20]
        self._update_history_buttons()
        super().accept()

    def _activate_eyedropper(self):
        self.hide()
        self.eyedropper_activated.emit()

    def eyedropper_color_picked(self, color):
        self.color_picker.set_color(color)
        self.show()
        self.activateWindow()
