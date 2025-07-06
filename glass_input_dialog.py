from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QLabel, QLineEdit, 
                             QPushButton, QHBoxLayout, QGraphicsDropShadowEffect, 
                             QWidget, QDialogButtonBox, QStylePainter, QStyle, QStyleOptionButton)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QPainter, QBrush

DIALOG_STYLESHEET = """
QDialog {
    background-color: rgba(0,0,0,160);
    border: 1.5px solid rgba(120,120,120,0.25);
    border-radius: 14px;
    font-family: 'Segoe UI', Arial, sans-serif;
}
QLabel {
    color: #fff;
    font-size: 10pt;
    padding-left: 4px;
    margin-bottom: 5px;
}
QLineEdit, QTextEdit {
    background-color: rgba(255,255,255,0.85);
    border: 1px solid #D0D0D0;
    border-radius: 7px;
    padding: 8px;
    font-size: 10pt;
    color: #222;
}
QLineEdit:focus, QTextEdit:focus {
    border: 1.5px solid #888;
}
QPushButton {
    background-color: rgba(255,255,255,0.75);
    color: #222;
    border: none;
    border-radius: 7px;
    padding: 7px 28px;
    font-size: 10pt;
    font-weight: bold;
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
"""

class GlassMenuButton(QPushButton):
    def paintEvent(self, event):
        opt = QStyleOptionButton()
        self.initStyleOption(opt)
        painter = QStylePainter(self)
        painter.drawControl(QStyle.CE_PushButtonBevel, opt)
        painter.drawControl(QStyle.CE_PushButtonLabel, opt)

class GlassInputDialog(QDialog):
    """
    Кастомный диалог для ввода текста со стилем "матового стекла",
    аналогичный другим элементам интерфейса приложения.
    """
    def __init__(self, parent=None, title="Введите значение", label="Значение:", text=""):
        super().__init__(parent)
        self.setWindowTitle(title)
        
        self.setStyleSheet(DIALOG_STYLESHEET)
        
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Dialog | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAutoFillBackground(False)
        self.setModal(True)
        
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(18, 18, 18, 18)
        
        self.label = QLabel(label)
        self.label.setStyleSheet("background-color: rgba(0,0,0,160); color: #fff; border-radius: 7px; padding: 4px 8px;")
        
        self.lineEdit = QLineEdit(text)
        
        self.button_box = QDialogButtonBox(self)
        self.ok_button = GlassMenuButton("Сохранить")
        self.cancel_button = GlassMenuButton("Отмена")
        
        self.button_box.addButton(self.ok_button, QDialogButtonBox.AcceptRole)
        self.button_box.addButton(self.cancel_button, QDialogButtonBox.RejectRole)
        
        self.layout.addWidget(self.label)
        self.layout.addWidget(self.lineEdit)
        self.layout.addSpacing(10)
        self.layout.addWidget(self.button_box)

        self.ok_button.clicked.connect(self.accept)
        self.cancel_button.clicked.connect(self.reject)
        self.lineEdit.returnPressed.connect(self.accept)
        
        self.ok_button.setStyleSheet(
            "background-color: rgba(255,255,255,0.75); color: #222; border: none; border-radius: 7px; padding: 7px 34px; font-size: 10pt; font-weight: bold;"
        )
        self.cancel_button.setStyleSheet(
            "background-color: #EAEAEA; color: #333; font-weight: normal; border-radius: 7px; padding: 7px 34px; font-size: 10pt;"
        )

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.setBrush(QBrush(QColor(0, 0, 0, 160)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 14, 14)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(120, 120, 120, 120))
        painter.drawRoundedRect(rect, 14, 14)
        super().paintEvent(event)

    def get_text(self):
        return self.lineEdit.text()

    @staticmethod
    def getText(parent, title, label, text=""):
        dialog = GlassInputDialog(parent, title, label, text)
        dialog.lineEdit.setFocus()
        dialog.lineEdit.selectAll()
        
        result = dialog.exec_()
        text_value = dialog.get_text()
        
        dialog.deleteLater()
        
        if result == QDialog.Accepted:
            return text_value, True
        return text_value, False 