from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QSizePolicy, QSpacerItem, QStyle, QGraphicsDropShadowEffect, QFileDialog
from PyQt5.QtCore import QPropertyAnimation, Qt, QSize, QEvent, pyqtProperty, QRectF, pyqtSignal, QPoint
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QLinearGradient, QColor, QBrush, QPainterPath
import os
import base64
import json
from app_settings import load_settings, save_settings

AVATAR_PATH = 'avatar.png'

class GlassSidebarMenu(QWidget):
    open_project_requested = pyqtSignal()
    save_project_requested = pyqtSignal()
    export_png_requested = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Tool)
        self._expanded_width = 240
        self._collapsed_width = 0
        self._is_expanded = False
        self.setFixedWidth(self._collapsed_width)
        self.setObjectName('GlassSidebarMenu')
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setMouseTracking(True)
        self._init_ui()
        self._init_animation()
        self.installEventFilter(self)
        self._sensor = None
        self.hide()

    def update_position(self):
        parent = self.parent()
        if parent:
            # Выравниваем по левому краю родительского окна
            top_left = parent.mapToGlobal(QPoint(0, 0))
            self.move(top_left)
            self.setFixedHeight(parent.height())

    def set_sensor(self, sensor):
        self._sensor = sensor

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(0)

        self.header = GradientHeader(self)
        self.header.setFixedHeight(80)
        layout.addWidget(self.header)

        layout.addSpacing(32)

        self.btn_open = QPushButton(self.style().standardIcon(QStyle.SP_DirOpenIcon), '  Открыть проект', self)
        self.btn_save = QPushButton(self.style().standardIcon(QStyle.SP_DialogSaveButton), '  Сохранить проект', self)
        self.btn_export = QPushButton(self.style().standardIcon(QStyle.SP_DriveFDIcon), '  Экспорт в PNG', self)
        for btn in [self.btn_open, self.btn_save, self.btn_export]:
            btn.setIconSize(QSize(28, 28))
            btn.setMinimumHeight(48)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(btn)

        # --- Подключаем кнопки к сигналам ---
        self.btn_open.clicked.connect(self.open_project_requested)
        self.btn_save.clicked.connect(self.save_project_requested)
        self.btn_export.clicked.connect(self.export_png_requested)

        layout.addSpacerItem(QSpacerItem(20, 20, QSizePolicy.Minimum, QSizePolicy.Fixed))

        # --- Кнопки добавления элементов ---
        self.add_stage_button = QPushButton(self.style().standardIcon(QStyle.SP_FileIcon), "  Новый блок", self)
        self.add_image_stage_button = QPushButton(self.style().standardIcon(QStyle.SP_ComputerIcon), "  Изображение", self)
        self.add_txt_stage_button = QPushButton(self.style().standardIcon(QStyle.SP_DriveNetIcon), "  Текстовый файл", self)
        
        for btn in [self.add_stage_button, self.add_image_stage_button, self.add_txt_stage_button]:
            btn.setIconSize(QSize(28, 28))
            btn.setMinimumHeight(48)
            btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            layout.addWidget(btn)

        layout.addSpacerItem(QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding))

        self.btn_theme = QPushButton(self.style().standardIcon(QStyle.SP_BrowserReload), '  Сменить тему', self)
        self.btn_theme.setIconSize(QSize(28, 28))
        self.btn_theme.setMinimumHeight(48)
        self.btn_theme.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        layout.addWidget(self.btn_theme)

        self.avatar = AvatarWidget(self)
        self.avatar.setParent(self)
        self.avatar.raise_()
        self.avatar.move((self._expanded_width - self.avatar.width()) // 2, self.header.height() - self.avatar.height() // 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, 'avatar') and hasattr(self, 'header'):
            self.avatar.move((QWidget.width(self) - self.avatar.width()) // 2, self.header.height() - self.avatar.height() // 2)

    def _init_animation(self):
        self._animation = QPropertyAnimation(self, b'width')
        self._animation.setDuration(250)
        self._animation.setStartValue(self._collapsed_width)
        self._animation.setEndValue(self._expanded_width)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Leave:
            self.collapse()
        return super().eventFilter(obj, event)

    def expand(self):
        if not self._is_expanded:
            self._animation.stop()
            self._animation.setStartValue(QWidget.width(self))
            self._animation.setEndValue(self._expanded_width)
            self._animation.start()
            self._is_expanded = True
            self.show()

    def collapse(self):
        if self._is_expanded:
            self._animation.stop()
            self._animation.setStartValue(QWidget.width(self))
            self._animation.setEndValue(self._collapsed_width)
            self._animation.start()
            self._is_expanded = False
            # Скрываем после анимации
            self._animation.finished.connect(self._hide_if_collapsed)

    def _hide_if_collapsed(self):
        if not self._is_expanded:
            self.hide()
        self._animation.finished.disconnect(self._hide_if_collapsed)

    def get_width(self):
        return QWidget.width(self)

    def set_width(self, value):
        self.setFixedWidth(int(value))

    width = pyqtProperty(int, fget=get_width, fset=set_width)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(QColor(255,255,255,220)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 18, 18)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(192, 192, 192, 120))
        painter.drawRoundedRect(rect, 18, 18)
        super().paintEvent(event)

class GradientHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.logo = QLabel(self)
        self.logo.setPixmap(QPixmap(40, 40))
        self.logo.setFixedSize(40, 40)
        self.logo.move(24, 24)
        self.logo.setStyleSheet('background: transparent;')
        pix = QPixmap(40, 40)
        pix.fill(Qt.transparent)
        painter = QPainter(pix)
        grad = QLinearGradient(0, 0, 40, 40)
        grad.setColorAt(0, QColor('#e0e0ff'))
        grad.setColorAt(1, QColor('#f7eaff'))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(0, 0, 40, 40)
        painter.end()
        self.logo.setPixmap(pix)

    def paintEvent(self, event):
        painter = QPainter(self)
        grad = QLinearGradient(0, 0, self.width(), self.height())
        grad.setColorAt(0, QColor(255,255,255,220))
        grad.setColorAt(1, QColor(230,230,255,180))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.NoPen)
        painter.drawRect(self.rect())

class AvatarWidget(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(56, 56)
        self.setStyleSheet('background: transparent;')
        self.setCursor(Qt.PointingHandCursor)
        self.load_avatar()

    def load_avatar(self):
        size = 56
        settings = load_settings()
        avatar_b64 = settings.get('avatar_b64')
        if avatar_b64:
            try:
                img_bytes = base64.b64decode(avatar_b64)
                pixmap = QPixmap()
                pixmap.loadFromData(img_bytes)
                src = pixmap.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                mask = QPixmap(size, size)
                mask.fill(Qt.transparent)
                painter = QPainter(mask)
                path = QPainterPath()
                path.addEllipse(QRectF(0, 0, size, size))
                painter.setRenderHint(QPainter.Antialiasing)
                painter.setClipPath(path)
                painter.drawPixmap(0, 0, src)
                painter.end()
                self.setPixmap(mask)
                return
            except Exception:
                pass
        # Фоллбек: если нет base64, пробуем файл
        if os.path.exists(AVATAR_PATH):
            src = QPixmap(AVATAR_PATH)
            src = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            mask = QPixmap(size, size)
            mask.fill(Qt.transparent)
            painter = QPainter(mask)
            path = QPainterPath()
            path.addEllipse(QRectF(0, 0, size, size))
            painter.setRenderHint(QPainter.Antialiasing)
            painter.setClipPath(path)
            painter.drawPixmap(0, 0, src)
            painter.end()
            self.setPixmap(mask)
        else:
            pix = QPixmap(size, size)
            pix.fill(Qt.transparent)
            painter = QPainter(pix)
            painter.setBrush(QColor('#fff'))
            painter.setPen(QColor('#c0c0c0'))
            painter.drawEllipse(0, 0, size, size)
            painter.setBrush(QColor('#e0e0ff'))
            painter.setPen(Qt.NoPen)
            painter.drawEllipse(5, 5, size-10, size-10)
            painter.end()
            self.setPixmap(pix)

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            file_path, _ = QFileDialog.getOpenFileName(self, 'Выбрать аватар', '', 'Изображения (*.png *.jpg *.jpeg *.bmp *.gif)')
            if file_path:
                with open(file_path, 'rb') as f:
                    img_bytes = f.read()
                avatar_b64 = base64.b64encode(img_bytes).decode('utf-8')
                settings = load_settings()
                settings['avatar_b64'] = avatar_b64
                save_settings(settings)
                self.load_avatar()
        super().mousePressEvent(event) 