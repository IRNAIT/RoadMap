import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel, QHBoxLayout, QSizePolicy, QSpacerItem, QStyle, QApplication, QGraphicsDropShadowEffect, QFileDialog
from PyQt5.QtCore import QPropertyAnimation, Qt, QSize, QEvent, pyqtProperty, QRectF
from PyQt5.QtGui import QIcon, QPixmap, QPainter, QLinearGradient, QColor, QBrush, QPainterPath

AVATAR_PATH = 'avatar.png'

class LeftEdgeSensor(QWidget):
    def __init__(self, sidebar_menu, width=4, parent=None):
        super().__init__(parent)
        self.sidebar_menu = sidebar_menu
        self.setFixedWidth(width)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet('background: transparent;')
        self.setMouseTracking(True)

    def enterEvent(self, event):
        self.sidebar_menu.expand()
        super().enterEvent(event)

class GradientHeader(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(110)  # увеличена высота
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.logo = QLabel(self)
        self.logo.setPixmap(QPixmap(40, 40))
        self.logo.setFixedSize(40, 40)
        self.logo.move(24, 24)  # увеличен отступ
        self.logo.setStyleSheet('background: transparent;')
        # Светлая заглушка-логотип
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
        if os.path.exists(AVATAR_PATH):
            src = QPixmap(AVATAR_PATH)
            # Масштабируем с заполнением (обрезка по кругу)
            src = src.scaled(size, size, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
            # Обрезаем по кругу
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
            # Светлая заглушка-аватар с белой обводкой
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
                pix = QPixmap(file_path).scaled(56, 56, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
                pix.save(AVATAR_PATH)
                self.load_avatar()
        super().mousePressEvent(event)

class SidebarMenu(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._expanded_width = 240
        self._collapsed_width = 0
        self._is_expanded = True
        self.setFixedWidth(self._expanded_width)
        self.setObjectName('SidebarMenu')
        self.setStyleSheet('''
            #SidebarMenu {
                background: rgba(255,255,255,0.85);
                border-radius: 18px;
                border: 1.5px solid #c0c0c0;
            }
            QPushButton {
                background: rgba(255,255,255,0.75);
                color: #222;
                border: none;
                border-radius: 12px;
                font-size: 15px;
                padding: 12px 0px 12px 18px;
                text-align: left;
                margin-bottom: 4px;
                transition: background 0.2s;
            }
            QPushButton:hover {
                background: #fff;
                border: 2px solid #888;
                color: #111;
            }
            QLabel {
                color: #222;
                font-size: 15px;
                padding-left: 12px;
            }
        ''')
        # DropShadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setColor(QColor(180,180,200,120))
        shadow.setOffset(0, 0)
        self.setGraphicsEffect(shadow)
        self._init_ui()
        self._init_animation()
        self.setMouseTracking(True)
        self.installEventFilter(self)
        self._sensor = None

    def set_sensor(self, sensor):
        self._sensor = sensor

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 24)
        layout.setSpacing(0)

        self.header = GradientHeader(self)
        self.header.setFixedHeight(80)
        layout.addWidget(self.header)

        layout.addSpacing(32)  # spacing после header

        # Кнопки меню и остальное...
        self.btn_open = QPushButton(self.style().standardIcon(QStyle.SP_DirOpenIcon), '  Открыть проект', self)
        self.btn_save = QPushButton(self.style().standardIcon(QStyle.SP_DialogSaveButton), '  Сохранить проект', self)
        self.btn_export = QPushButton(self.style().standardIcon(QStyle.SP_DriveFDIcon), '  Экспорт в PNG', self)
        for btn in [self.btn_open, self.btn_save, self.btn_export]:
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

        # --- Аватар ---
        self.avatar = AvatarWidget(self)
        self.avatar.setParent(self)
        self.avatar.raise_()  # гарантируем, что он поверх
        # Позиционируем при инициализации
        self.avatar.move((QWidget.width(self) - self.avatar.width()) // 2, self.header.height() - self.avatar.height() // 2)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        # Центрируем аватар при изменении размера
        if hasattr(self, 'avatar') and hasattr(self, 'header'):
            self.avatar.move((QWidget.width(self) - self.avatar.width()) // 2, self.header.height() - self.avatar.height() // 2)

    def _init_animation(self):
        self._animation = QPropertyAnimation(self, b'width')
        self._animation.setDuration(250)
        self._animation.setStartValue(self._expanded_width)
        self._animation.setEndValue(self._collapsed_width)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Leave:
            self.collapse()
        return super().eventFilter(obj, event)

    def toggle(self):
        if self._is_expanded:
            self.collapse()
        else:
            self.expand()

    def expand(self):
        if not self._is_expanded:
            self._animation.stop()
            self._animation.setStartValue(QWidget.width(self))
            self._animation.setEndValue(self._expanded_width)
            self._animation.start()
            self._is_expanded = True

    def collapse(self):
        if self._is_expanded:
            self._animation.stop()
            self._animation.setStartValue(QWidget.width(self))
            self._animation.setEndValue(self._collapsed_width)
            self._animation.start()
            self._is_expanded = False

    def get_width(self):
        return QWidget.width(self)

    def set_width(self, value):
        self.setFixedWidth(int(value))

    width = pyqtProperty(int, fget=get_width, fset=set_width) 