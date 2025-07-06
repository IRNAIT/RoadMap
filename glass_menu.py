from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QApplication, QGraphicsBlurEffect, QLabel, QHBoxLayout, QStyleOptionButton, QStylePainter, QStyle
from PyQt5.QtCore import Qt, QPoint, QRect, QEvent
from PyQt5.QtGui import QColor, QPainter, QBrush, QFont
import re

class GlassMenuButton(QPushButton):
    def paintEvent(self, event):
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        painter = QStylePainter(self)
        # Фон и выделение
        painter.drawControl(QStyle.CE_PushButtonBevel, opt)
        # Текст и иконка поверх всего
        painter.drawControl(QStyle.CE_PushButtonLabel, opt)

class GlassMenu(QWidget):
    def __init__(self, actions, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setMouseTracking(True)
        self.selected_action = None
        self._setup_ui(actions)
        self.installEventFilter(self)

    def _setup_ui(self, actions):
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(14, 8, 14, 8)
        self.layout.setSpacing(5)
        self.buttons = []
        for action in actions:
            if action is None:
                separator = QLabel(self)
                separator.setFixedSize(150, 2)
                separator.setStyleSheet("background-color: rgba(255, 255, 255, 0.2); margin: 4px 0;")
                self.layout.addWidget(separator, 0, Qt.AlignHCenter)
                continue
            
            text, callback = action
            btn = GlassMenuButton(text, self)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet('''
                QPushButton {
                    background-color: rgba(255,255,255,0.75);
                    color: #222;
                    border: none;
                    border-radius: 7px;
                    font-size: 9pt;
                    font-family: 'Segoe UI', Arial, sans-serif;
                    padding: 5px 28px;
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
            btn.clicked.connect(lambda checked, cb=callback: self._on_action(cb))
            self.layout.addWidget(btn)
            self.buttons.append(btn)

    def _on_action(self, callback):
        self.selected_action = callback
        self.close()
        if callback:
            callback()

    def show_at(self, global_pos):
        self.adjustSize()
        self.move(global_pos)
        self.show()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1,1,-1,-1)
        painter.setBrush(QBrush(QColor(0,0,0,145)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 12, 12)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 12, 12)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.MouseButtonPress:
            if not self.rect().contains(self.mapFromGlobal(event.globalPos())):
                self.close()
        return super().eventFilter(obj, event)

class GlassDialog(QWidget):
    def __init__(self, text, buttons, parent=None):
        super().__init__(parent, Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Popup | Qt.NoDropShadowWindowHint)
        self.setMouseTracking(True)
        self.result = None
        self._setup_ui(text, buttons)
        self.installEventFilter(self)

    def _setup_ui(self, text, buttons):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 18, 24, 18)
        layout.setSpacing(16)
        label = QLabel(text, self)
        label.setStyleSheet('''
            color: #fff;
            font-size: 11pt;
            font-family: 'Segoe UI', Arial, sans-serif;
            background: transparent;
        ''')
        label.setWordWrap(True)
        layout.addWidget(label)
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)
        for btn_text, btn_result in buttons:
            # Переводим стандартные кнопки
            if btn_text.lower() in ("ok", "yes", "да"): btn_text = "Сохранить" if btn_result=="ok" else "Да"
            elif btn_text.lower() in ("cancel", "no", "нет"): btn_text = "Отмена" if btn_result=="cancel" else "Нет"
            btn = GlassMenuButton(btn_text, self)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setStyleSheet('''
                QPushButton {
                    background-color: rgba(255,255,255,0.75);
                    color: #222;
                    border: none;
                    border-radius: 7px;
                    font-size: 10pt;
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
            btn.clicked.connect(lambda checked, res=btn_result: self._on_action(res))
            btn_layout.addWidget(btn)
        layout.addLayout(btn_layout)

    def _on_action(self, result):
        self.result = result
        self.close()

    def exec_(self):
        self.setWindowModality(Qt.ApplicationModal)
        self.adjustSize()
        desktop = QApplication.desktop().screenGeometry()
        self.move(
            desktop.center().x() - self.width() // 2,
            desktop.center().y() - self.height() // 2
        )
        self.show()
        app = QApplication.instance()
        while self.isVisible():
            app.processEvents()
        return self.result

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1,1,-1,-1)
        painter.setBrush(QBrush(QColor(0,0,0,170)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 14, 14)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 14, 14)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.key() == Qt.Key_Escape:
            self.result = 'cancel'
            self.close()
        return super().eventFilter(obj, event) 