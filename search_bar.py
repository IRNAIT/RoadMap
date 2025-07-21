from PyQt5.QtWidgets import QWidget, QLineEdit, QVBoxLayout, QFrame, QLabel, QHBoxLayout, QPushButton
from PyQt5.QtCore import Qt, QPropertyAnimation, pyqtSignal, QRectF, QEvent, QEasingCurve
from PyQt5.QtGui import QPainter, QColor, QBrush, QPainterPath, QFont, QCursor

class GlassSearchBar(QWidget):
    search_triggered = pyqtSignal(str)
    tag_selected = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.animation = QPropertyAnimation(self, b"geometry")
        self.animation.setEasingCurve(QEasingCurve.OutCubic)
        self.animation.setDuration(300)
        self.line_edit = QLineEdit(self)
        self.line_edit.setPlaceholderText("Поиск по тегу, например: #идея или идея")
        self.line_edit.setStyleSheet("""
            QLineEdit {
                background-color: rgba(30, 30, 30, 180);
                border: 1px solid rgba(255, 255, 255, 50);
                border-radius: 15px;
                padding: 2px 8px 2px 8px;
                color: white;
                font-family: Finlandica;
                font-size: 10pt;
            }
        """)
        self.line_edit.setFixedHeight(24)
        self.close_btn = QPushButton("✕", self)
        self.close_btn.setCursor(Qt.PointingHandCursor)
        self.close_btn.setFixedSize(28, 28)
        self.close_btn.setStyleSheet("""
            QPushButton {
                background: transparent;
                border: none;
                color: #bbb;
                font-size: 18px;
                font-weight: bold;
                border-radius: 14px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,0.08);
                color: #fff;
            }
        """)
        self.close_btn.setFixedHeight(24)
        self.close_btn.clicked.connect(self.hide_widget)
        self.suggestion_frame = QFrame(self)
        self.suggestion_frame.setStyleSheet("""
            QFrame {
                background: rgba(30, 30, 30, 160);
                border-radius: 12px;
                border: 1px solid rgba(255,255,255,30);
            }
        """)
        self.suggestion_frame.setVisible(False)
        self.suggestion_layout = QVBoxLayout(self.suggestion_frame)
        self.suggestion_layout.setContentsMargins(8, 4, 8, 4)
        self.suggestion_layout.setSpacing(2)
        top_row = QHBoxLayout()
        top_row.addWidget(self.line_edit)
        top_row.addWidget(self.close_btn)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)
        top_row.setAlignment(Qt.AlignVCenter)
        layout = QVBoxLayout(self)
        layout.addLayout(top_row)
        layout.addWidget(self.suggestion_frame)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setAlignment(Qt.AlignVCenter)
        self.setLayout(layout)
        self.hide()
        self.line_edit.textChanged.connect(self.on_text_changed)
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 10, 10)
        painter.setBrush(QBrush(QColor(10, 10, 10, 180)))
        painter.setPen(Qt.NoPen)
        painter.drawPath(path)
    def show_widget(self):
        if not self.parent():
            return
        parent_rect = self.parent().geometry()
        width = int(parent_rect.width() * 0.28)
        height = 15  # Было 30, теперь 15
        start_x = parent_rect.x() + (parent_rect.width() - width) // 2
        start_y = parent_rect.y() - height
        end_x = start_x
        end_y = parent_rect.y() + 16
        self.setGeometry(start_x, start_y, width, height)
        self.setWindowOpacity(0.0)
        self.show()
        self.activateWindow()
        self.line_edit.setFocus()
        # Восстанавливаем текст поиска, если был
        if hasattr(self, '_last_search_text'):
            self.line_edit.setText(self._last_search_text)
        else:
            self.line_edit.clear()
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(self.geometry().translated(0, end_y - start_y))
        self.opacity_anim = QPropertyAnimation(self, b'windowOpacity')
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(0.0)
        self.opacity_anim.setEndValue(1.0)
        self.opacity_anim.start()
        self.animation.setDirection(QPropertyAnimation.Forward)
        self.animation.start()
    def hide_widget(self):
        self._last_search_text = self.line_edit.text()
        parent_rect = self.parent().geometry() if self.parent() else self.geometry()
        width = self.width()
        height = self.height()
        x = self.x()
        y = self.y()
        end_y = parent_rect.y() - height
        self.animation.setStartValue(self.geometry())
        self.animation.setEndValue(QRectF(x, end_y, width, height))
        self.animation.setDirection(QPropertyAnimation.Forward)
        self.animation.finished.connect(self._hide_and_reset)
        self.opacity_anim = QPropertyAnimation(self, b'windowOpacity')
        self.opacity_anim.setDuration(300)
        self.opacity_anim.setStartValue(1.0)
        self.opacity_anim.setEndValue(0.0)
        self.opacity_anim.start()
        try:
            self.animation.finished.disconnect(self._hide_and_reset)
        except TypeError:
            pass
        self.suggestion_frame.setVisible(False)
        self.search_triggered.emit("")
    def _hide_and_reset(self):
        self.setWindowOpacity(0.0)
        self.suggestion_frame.setVisible(False)
        self.hide()  # Теперь реально скрываем окно
        self.clearFocus()
        # Принудительно возвращаем фокус на рабочую область
        p = self.parent()
        if p and hasattr(p, 'roadmap_widget'):
            p.roadmap_widget.setFocus(Qt.OtherFocusReason)
        elif p:
            p.setFocus(Qt.OtherFocusReason)
    def on_text_changed(self, text):
        self.search_triggered.emit(text)
        self.show_suggestions(text)
    def _reposition_search_bar(self):
        if not self.parent():
            return
        parent_rect = self.parent().geometry()
        width = self.width()
        height = self.height()
        x = parent_rect.x() + (parent_rect.width() - width) // 2
        y = parent_rect.y() + 16
        self.move(x, y)
    def show_suggestions(self, text=None):
        if text is None:
            text = self.line_edit.text()
        parent = self.parent()
        if not parent or not hasattr(parent, 'roadmap_widget') or not text.strip():
            self.suggestion_frame.setVisible(False)
            self.suggestion_frame.setFixedHeight(0)
            self.setFixedHeight(36)
            self._reposition_search_bar()
            return
        tags = set()
        for item in parent.roadmap_widget.scene.items():
            if hasattr(item, 'tags') and item.tags:
                tags.update(item.tags)
        tags = sorted(tags, key=lambda x: x.lower())
        filtered = [t for t in tags if text.lower() in t.lower()] if text else tags
        for i in reversed(range(self.suggestion_layout.count())):
            w = self.suggestion_layout.itemAt(i).widget()
            if w:
                w.deleteLater()
        if not filtered:
            self.suggestion_frame.setVisible(False)
            self.suggestion_frame.setFixedHeight(0)
            self.setFixedHeight(36)
            self._reposition_search_bar()
            return
        for tag in filtered:
            lbl = QLabel(tag, self.suggestion_frame)
            lbl.setFixedHeight(30)
            lbl.setStyleSheet("""
                QLabel {
                    color: white;
                    background: rgba(60,60,60,120);
                    border-radius: 6px;
                    padding: 4px 8px 6px 8px;
                    font-family: Finlandica;
                    font-size: 9pt;
                }
                QLabel:hover {
                    background: rgba(120,120,120,180);
                }
            """)
            lbl.setCursor(Qt.PointingHandCursor)
            lbl.mousePressEvent = lambda e, t=tag: self.on_suggestion_clicked(t)
            self.suggestion_layout.addWidget(lbl)
        self.suggestion_frame.setVisible(True)
        self.suggestion_frame.setFixedHeight(30 * len(filtered))
        total_height = 36 + self.suggestion_frame.height() + self.layout().contentsMargins().top() + self.layout().contentsMargins().bottom()
        self.setFixedHeight(total_height)
        self._reposition_search_bar()
    def on_suggestion_clicked(self, tag):
        self.line_edit.setText(tag)
        self.suggestion_frame.setVisible(False)
        self.suggestion_frame.setFixedHeight(0)
        self.setFixedHeight(36)
        self._reposition_search_bar()
    def focusOutEvent(self, event):
        self.suggestion_frame.setVisible(False)
        super().focusOutEvent(event)
    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Escape:
            self.hide_widget()
        super().keyPressEvent(event)
