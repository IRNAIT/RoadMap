from PyQt5.QtWidgets import QGraphicsObject
from PyQt5.QtCore import QRectF, QPropertyAnimation, QEasingCurve, pyqtProperty
from PyQt5.QtGui import QPainter, QColor, QBrush, QLinearGradient, QRadialGradient
from PyQt5.QtCore import Qt
class SearchGlowGraphicsItem(QGraphicsObject):
    GLOW_MARGIN = 5
    def __init__(self, target_block, parent=None):
        super().__init__(parent)
        self.target_block = target_block
        self.setZValue(target_block.zValue() - 1)
        self.opacity_val = 0.0
        self._pulse_anim = None
        self.setAcceptedMouseButtons(Qt.NoButton)
        self.setFlag(QGraphicsObject.ItemIgnoresTransformations, False)
        self.update_geometry()
        self.start_pulse()
        # Получаем цвет рамки блока
        self.glow_color = QColor(getattr(target_block, 'stage_data', {}).get('border_color', '#000000'))
    def update_geometry(self):
        rect = self.target_block.boundingRect()
        self.setPos(self.target_block.pos())
        self._rect = rect.adjusted(-self.GLOW_MARGIN, -self.GLOW_MARGIN, self.GLOW_MARGIN, self.GLOW_MARGIN)
        self._radius = getattr(self.target_block, 'border_radius', 10) + self.GLOW_MARGIN
    @pyqtProperty(float)
    def glowOpacity(self):
        return self.opacity_val
    @glowOpacity.setter
    def glowOpacity(self, value):
        self.opacity_val = value
        self.update()
    def start_pulse(self):
        if self._pulse_anim:
            self._pulse_anim.stop()
        self._pulse_anim = QPropertyAnimation(self, b'glowOpacity')
        self._pulse_anim.setDuration(1200)
        self._pulse_anim.setStartValue(0.7)
        self._pulse_anim.setEndValue(0.2)
        self._pulse_anim.setEasingCurve(QEasingCurve.InOutSine)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.start()
    def stop_pulse(self):
        if self._pulse_anim:
            self._pulse_anim.stop()
        self.opacity_val = 0.0
        self.update()
    def boundingRect(self):
        return self._rect
    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.target_block.boundingRect()
        radius = getattr(self.target_block, 'border_radius', 10)
        base_alpha = int(255 * self.opacity_val)
        layers = 4
        max_margin = self.GLOW_MARGIN
        for i in range(layers, 0, -1):
            margin = max_margin * i / layers
            alpha = int(base_alpha * (0.35 * i / layers))  # Было 0.18, стало 0.35
            color = QColor(self.glow_color)
            color.setAlpha(alpha)
            painter.setPen(Qt.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(rect.adjusted(-margin, -margin, margin, margin), radius + margin, radius + margin) 