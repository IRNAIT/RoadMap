#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from PyQt5.QtWidgets import (QMenu, QColorDialog, QGraphicsView, QGraphicsScene, 
                             QGraphicsObject, QGraphicsItem, QFileDialog, QGraphicsTextItem,
                             QGraphicsLineItem, QGraphicsBlurEffect, QInputDialog, QGraphicsProxyWidget, QLabel, QVBoxLayout, QWidget, QGraphicsDropShadowEffect, QApplication, QDialog, QPushButton, QShortcut)
from PyQt5.QtCore import (Qt, QPointF, QRectF, pyqtSignal, pyqtProperty, 
                          QPropertyAnimation, QSequentialAnimationGroup, QTimer)
from PyQt5.QtGui import (QPainter, QPen, QColor, QBrush, QFont, QTextOption, 
                       QPainterPath, QLinearGradient, QPainterPathStroker, QPixmap, QImage, QFontMetrics, QKeySequence, QCursor, QTextDocument, QMouseEvent)
import math
import uuid
from color_picker import ColorPickerDialog
from glass_menu import GlassMenu
from timeline_guide import TimelineGuideItem, TimelineLabelItem, TickItem
from custom_rich_text_editor import ScrollableRichTextEditor, TextFragment, CustomTextEditDialog, TxtFileEditDialog

class ConnectionGraphicsItem(QGraphicsObject):
    """Графический элемент для отрисовки 'умных', кликабельных соединительных линий."""
    
    half_clicked = pyqtSignal(object, str) # connection, 'start'/'end'
    half_hovered = pyqtSignal(object, str, bool) # connection, 'start'/'end', is_active

    def __init__(self, start_item, end_item, parent=None):
        super().__init__(parent)
        self.start_item = start_item
        self.end_item = end_item
        self.path = QPainterPath()
        self.setZValue(-1)
        self.setAcceptHoverEvents(True)
        self._last_hovered_half = None
        self.update_path()

    def boundingRect(self):
        extra = 3.0
        return self.path.boundingRect().adjusted(-extra, -extra, extra, extra)

    def shape(self):
        stroker = QPainterPathStroker()
        stroker.setWidth(10)
        return stroker.createStroke(self.path)

    def _get_hovered_half(self, scene_pos):
        min_dist_sq = float('inf')
        closest_t = 0
        for i in range(101):
            t = i / 100.0
            p = self.mapToScene(self.path.pointAtPercent(t))
            dist_sq = (p - scene_pos).manhattanLength()
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                closest_t = t
        return 'start' if closest_t < 0.5 else 'end'

    def hoverMoveEvent(self, event):
        if event.modifiers() == Qt.ShiftModifier:
            hovered_half = self._get_hovered_half(event.scenePos())
            if self._last_hovered_half != hovered_half:
                if self._last_hovered_half is not None:
                    self.half_hovered.emit(self, self._last_hovered_half, False)
                self._last_hovered_half = hovered_half
                self.half_hovered.emit(self, hovered_half, True)
        else:
            if self._last_hovered_half is not None:
                self.half_hovered.emit(self, self._last_hovered_half, False)
                self._last_hovered_half = None
        super().hoverMoveEvent(event)

    def hoverLeaveEvent(self, event):
        if self._last_hovered_half is not None:
            self.half_hovered.emit(self, self._last_hovered_half, False)
            self._last_hovered_half = None
        super().hoverLeaveEvent(event)

    def mousePressEvent(self, event):
        if event.modifiers() == Qt.ShiftModifier:
            hovered_half = self._get_hovered_half(event.scenePos())
            self.half_clicked.emit(self, hovered_half)
        else:
            super().mousePressEvent(event)
    
    def update_path(self):
        self.prepareGeometryChange()
        start_pos, end_pos = self._get_optimal_points()
        dx, dy = end_pos.x() - start_pos.x(), end_pos.y() - start_pos.y()
        ctrl1 = QPointF(start_pos.x() + dx * 0.5, start_pos.y())
        ctrl2 = QPointF(end_pos.x() - dx * 0.5, end_pos.y())
        new_path = QPainterPath()
        new_path.moveTo(start_pos)
        new_path.cubicTo(ctrl1, ctrl2, end_pos)
        self.path = new_path
        self.update()

    def paint(self, painter, option, widget=None):
        if self.start_item.isSelected(): start_color_base = self.start_item.animatedBorderColor
        else: start_color_base = QColor(self.start_item.stage_data.get('border_color', '#BDBDBD'))
        if self.end_item.isSelected(): end_color_base = self.end_item.animatedBorderColor
        else: end_color_base = QColor(self.end_item.stage_data.get('border_color', '#BDBDBD'))
        start_color = QColor(start_color_base)
        start_color.setAlphaF(start_color.alphaF() * self.start_item.opacity())
        end_color = QColor(end_color_base)
        end_color.setAlphaF(end_color.alphaF() * self.end_item.opacity())
        start_point, end_point = self.path.pointAtPercent(0), self.path.pointAtPercent(1)
        gradient = QLinearGradient(start_point, end_point)
        gradient.setColorAt(0.0, start_color)
        gradient.setColorAt(1.0, end_color)
        pen = QPen(QBrush(gradient), 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
        painter.setPen(pen)
        painter.drawPath(self.path)

    def _get_optimal_points(self):
        start_anchors = self.start_item.get_anchor_points()
        end_anchors = self.end_item.get_anchor_points()
        min_dist = float('inf')
        best_pair = (QPointF(), QPointF())
        for p1 in start_anchors:
            for p2 in end_anchors:
                dist = math.hypot(p1.x() - p2.x(), p1.y() - p2.y())
                if dist < min_dist:
                    min_dist = dist
                    best_pair = (p1, p2)
        return best_pair

class StageGraphicsItem(QGraphicsObject):
    stage_edit_requested = pyqtSignal(object)
    block_moved = pyqtSignal()
    item_selected = pyqtSignal(QGraphicsObject)
    item_deselected = pyqtSignal(QGraphicsObject)

    def __init__(self, stage_data, _recalculate=True):
        super().__init__()
        self.rich_text_editor = ScrollableRichTextEditor()  # Для поддержки форматирования
        self.stage_data = stage_data
        if 'id' not in self.stage_data:
            self.stage_data['id'] = str(uuid.uuid4())
        if 'type' not in self.stage_data: self.stage_data['type'] = 'text'
        self.setFlags(QGraphicsItem.ItemIsMovable | QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemSendsGeometryChanges)
        self.rect = QRectF(0, 0, 220, 100)
        self.font = QFont('Finlandica', 12)
        self.connections = []
        self._animated_border_color = QColor(self.stage_data.get('border_color', '#BDBDBD'))
        self.animation = self._create_animation()
        self.is_locked = False
        self.setFlag(QGraphicsObject.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)
        self._is_hovered = False
        self.resizing = False
        self.resize_handle_size = 15
        self.last_mouse_pos = QPointF()
        self._cached_doc = None
        self._cached_html = None
        self.setCacheMode(QGraphicsItem.DeviceCoordinateCache)
        if _recalculate:
            self.recalculate_size()
        self._magnet_timer = None
        self._magnet_candidate = None
        self._magnet_last_time = 0

    @pyqtProperty(QColor, user=True)
    def animatedBorderColor(self):
        return self._animated_border_color

    @animatedBorderColor.setter
    def animatedBorderColor(self, color):
        self._animated_border_color = color
        self.update()
        for conn in self.connections:
            conn.update()

    def _create_animation(self):
        anim1 = QPropertyAnimation(self, b"animatedBorderColor")
        anim1.setDuration(800)
        anim2 = QPropertyAnimation(self, b"animatedBorderColor")
        anim2.setDuration(800)
        seq_group = QSequentialAnimationGroup(self)
        seq_group.addAnimation(anim1)
        seq_group.addAnimation(anim2)
        seq_group.setLoopCount(-1)
        self.anim1, self.anim2 = anim1, anim2
        return seq_group

    def _start_pulsing_animation(self):
        base_color = QColor(self.stage_data.get('border_color', '#BDBDBD'))
        dark_color = base_color.darker(140)
        light_color = base_color.lighter(125)
        self.anim1.setStartValue(dark_color)
        self.anim1.setEndValue(light_color)
        self.anim2.setStartValue(light_color)
        self.anim2.setEndValue(dark_color)
        self.animation.start()
        self.animatedBorderColor = dark_color

    def add_connection(self, connection):
        self.connections.append(connection)

    def itemChange(self, change, value):
        res = super().itemChange(change, value)
        if change == QGraphicsItem.ItemPositionHasChanged:
            for conn in self.connections:
                conn.update_path()
            if self.scene() and self.scene().views():
                view = self.scene().views()[0]
                if isinstance(view, RoadMapWidget):
                    view.check_and_expand_scene(self)
            self.block_moved.emit()
        if change == QGraphicsItem.ItemSelectedChange:
            if value: self.item_selected.emit(self)
            else: self.item_deselected.emit(self)
        return res
        
    def get_anchor_points(self):
        center = self.scenePos() + self.rect.center()
        return [
            center + QPointF(0, -self.rect.height()/2), center + QPointF(0, self.rect.height()/2),
            center + QPointF(-self.rect.width()/2, 0), center + QPointF(self.rect.width()/2, 0),
        ]

    def get_stage_data(self):
        pos = self.pos()
        self.stage_data['position'] = {'x': pos.x(), 'y': pos.y()}
        self.stage_data['width'] = self.rect.width()
        self.stage_data['height'] = self.rect.height()
        return self.stage_data

    def recalculate_size(self):
        self.prepareGeometryChange()
        padding_vertical = 20; padding_horizontal = 15
        min_height = 80; default_width = 220; max_width = 450
        fm = QFontMetrics(self.font)
        text = self.stage_data.get('title', '')
        words = text.split()
        longest_word_width = max(fm.boundingRect(word).width() for word in words) if words else 0
        text_wrap_width = default_width - 2 * padding_horizontal
        new_width = longest_word_width + 2 * padding_horizontal + 5 if longest_word_width + 5 > text_wrap_width else default_width
        if new_width > max_width: new_width = max_width
        new_width = self.stage_data.get('width', new_width)
        final_text_wrap_width = new_width - 2 * padding_horizontal
        text_height = fm.boundingRect(QRectF(0, 0, final_text_wrap_width, 10000).toRect(), Qt.TextWordWrap, text).height()
        new_height = text_height + 2 * padding_vertical
        if new_height < min_height: new_height = min_height
        new_height = self.stage_data.get('height', new_height)
        self.rect = QRectF(0, 0, new_width, new_height)
        self.update()
        for conn in self.connections: conn.update_path()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self._is_hovered and self.get_resize_handle_rect().contains(event.pos()):
            self.resizing = True
            self.resize_start_mouse_pos = event.scenePos()
            self.resize_start_width = self.stage_data.get('width', self.rect.width())
            self.resize_start_height = self.stage_data.get('height', self.rect.height())
            if not self.is_locked:
                self.setFlag(QGraphicsItem.ItemIsMovable, False)
            event.accept()
            return
        if event.button() == Qt.LeftButton:
            self._drag_offset = event.pos()
            # --- Для группового перемещения: сохраняем стартовые позиции и стартовую мышь ---
            selected = self.scene().selectedItems() if self.isSelected() else []
            if len(selected) > 1:
                mouse_scene_pos = self.mapToScene(event.pos())
                for item in selected:
                    item._group_drag_start_pos = item.pos()
                    item._group_mouse_start = mouse_scene_pos
        if event.button() == Qt.RightButton:
            actions = []
            item_type = self.stage_data.get('type', 'text')
            def edit_action():
                if self.scene() and self.scene().views(): self.scene().views()[0].edit_stage(self)
            def color_action(): self.change_color()
            def lock_action():
                self.is_locked = not self.is_locked
                self.setFlag(QGraphicsItem.ItemIsMovable, not self.is_locked)
            def delete_action():
                if self.scene() and self.scene().views():
                    view = self.scene().views()[0]
                    view.save_undo_state()
                    items_to_delete = self.scene().selectedItems() or [self]
                    for item in items_to_delete:
                        if isinstance(item, StageGraphicsItem): view.delete_stage(item, save_state=False)
            if item_type == 'text': actions.append(('Редактировать текст', edit_action))
            elif item_type == 'image': actions.append(('Редактировать описание', edit_action))
            actions.append(('Изменить цвет рамки', color_action))
            actions.append(('Закрепить блок' if not self.is_locked else 'Снять закрепление', lock_action))
            actions.append(('Удалить', delete_action))
            menu = GlassMenu(actions, parent=self.scene().views()[0] if self.scene() and self.scene().views() else None)
            menu.show_at(event.screenPos())
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            dx = event.scenePos().x() - self.resize_start_mouse_pos.x()
            dy = event.scenePos().y() - self.resize_start_mouse_pos.y()
            self.prepareGeometryChange()
            current_width = self.resize_start_width
            current_height = self.resize_start_height
            new_width = current_width + dx
            new_height = current_height + dy
            fm = QFontMetrics(self.font)
            title = self.stage_data.get('title', '')
            words = title.split()
            longest_word_width = max(fm.horizontalAdvance(word) for word in words) if words else 0
            text_rect = fm.boundingRect(QRectF(0, 0, new_width - 30, 5000).toRect(), Qt.TextWordWrap, title)
            min_width = max(100, longest_word_width + 30 + 5)
            min_height = text_rect.height() + 40
            if new_width < min_width: new_width = min_width
            if new_height < min_height: new_height = min_height
            # --- Привязка размеров к сетке, если сетка включена ---
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view and getattr(view, 'show_grid', False):
                grid_size = 40
                magnet_radius = 5
                grid_w = round(new_width / grid_size) * grid_size
                grid_h = round(new_height / grid_size) * grid_size
                snapped = False
                if abs(new_width - grid_w) < magnet_radius:
                    new_width = grid_w
                    snapped = True
                if abs(new_height - grid_h) < magnet_radius:
                    new_height = grid_h
                    snapped = True
                if not snapped:
                    new_width = current_width + dx
                    new_height = current_height + dy
            self.stage_data['width'] = new_width
            self.stage_data['height'] = new_height
            self.recalculate_size()
            self.update()
            if self.scene():
                for conn in self.connections: conn.update_path()
            event.accept()
            return
        # --- Магнитизм к сетке с учётом центра и правого/нижнего края, поддержка групп ---
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        offset = getattr(self, '_drag_offset', QPointF(0, 0))
        new_pos = self.mapToScene(event.pos() - offset)
        if view and getattr(view, 'show_grid', False):
            grid_size = 40
            magnet_radius = 5
            x = new_pos.x()
            y = new_pos.y()
            width = self.boundingRect().width()
            height = self.boundingRect().height()
            candidates = [
                (x, y),  # левый верхний угол
                (x + width / 2, y + height / 2),  # центр
                (x + width, y + height)  # правый нижний угол
            ]
            snap_x, snap_y = 0, 0
            for cx, cy in candidates:
                grid_x = round(cx / grid_size) * grid_size
                grid_y = round(cy / grid_size) * grid_size
                if abs(cx - grid_x) < magnet_radius:
                    snap_x = grid_x - cx
                if abs(cy - grid_y) < magnet_radius:
                    snap_y = grid_y - cy
            x += snap_x
            y += snap_y
            self.setPos(QPointF(x, y))
            event.accept()
            return
        else:
            self.setPos(QPointF(new_pos.x(), new_pos.y()))
            event.accept()
            return

    def _apply_magnet(self, candidate):
        self._magnet_last_time = 1
        self.setPos(QPointF(*candidate))

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if hasattr(self, '_drag_offset'):
                del self._drag_offset
            # Очищаем смещения для группового перемещения
            selected = self.scene().selectedItems() if self.isSelected() else []
            for item in selected:
                if hasattr(item, '_group_drag_start_pos'):
                    del item._group_drag_start_pos
                if hasattr(item, '_group_mouse_start'):
                    del item._group_mouse_start
        if self.resizing:
            self.resizing = False
            if not self.is_locked:
                self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.recalculate_size()
            if hasattr(self, 'resize_start_mouse_pos'):
                del self.resize_start_mouse_pos
            if hasattr(self, 'resize_start_width'):
                del self.resize_start_width
            if hasattr(self, 'resize_start_height'):
                del self.resize_start_height
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def boundingRect(self):
        return self.rect

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor("#FFFFFF")
        border_width = 3
        border_color = self._animated_border_color if self.isSelected() else QColor(self.stage_data.get('border_color', '#BDBDBD'))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, border_width))
        painter.drawRoundedRect(self.boundingRect(), 10, 10)
        painter.setPen(QColor("#222222"))
        painter.setFont(self.font)
        raw_text = self.stage_data.get('title', '')
        html = parse_discord_to_html(raw_text)
        if self._cached_doc is None or self._cached_html != html or self._cached_doc.textWidth() != self.boundingRect().width() - 16:
            doc = QTextDocument()
            doc.setDefaultFont(self.font)
            doc.setHtml(html)
            doc.setTextWidth(self.boundingRect().width() - 16)
            self._cached_doc = doc
            self._cached_html = html
        doc = self._cached_doc
        painter.save()
        painter.translate(self.boundingRect().left() + 8, self.boundingRect().top() + 8)
        clip = QRectF(0, 0, self.boundingRect().width() - 16, self.boundingRect().height() - 16)
        doc.drawContents(painter, clip)
        painter.restore()
        if getattr(self, 'is_locked', False):
            lock_rect = QRectF(self.boundingRect().left() + 6, self.boundingRect().top() + 6, 18, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(180, 180, 180))
            painter.drawEllipse(lock_rect)
            painter.setPen(QPen(QColor(100, 100, 100), 2))
            painter.drawArc(lock_rect.adjusted(3, 2, -3, 8), 30 * 16, 120 * 16)
            body_rect = QRectF(lock_rect.left() + 4, lock_rect.top() + 9, 10, 7)
            painter.setBrush(QColor(100, 100, 100))
            painter.drawRect(body_rect)
        if self._is_hovered:
            handle_rect = self.get_resize_handle_rect()
            arrow_color = self._animated_border_color if self.isSelected() else QColor(self.stage_data.get('border_color', '#BDBDBD'))
            painter.setPen(QPen(arrow_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            start_point = handle_rect.bottomRight() - QPointF(4, 4)
            end_point = handle_rect.topLeft() + QPointF(4, 4)
            painter.drawLine(start_point, end_point)
            angle = math.atan2(start_point.y() - end_point.y(), start_point.x() - end_point.x())
            arrow_size = 6
            p1 = end_point + QPointF(math.cos(angle + math.pi / 6) * arrow_size, math.sin(angle + math.pi / 6) * arrow_size)
            p2 = end_point + QPointF(math.cos(angle - math.pi / 6) * arrow_size, math.sin(angle - math.pi / 6) * arrow_size)
            painter.drawLine(end_point, p1)
            painter.drawLine(end_point, p2)

    def get_resize_handle_rect(self):
        return QRectF(self.rect.right() - self.resize_handle_size,
                      self.rect.bottom() - self.resize_handle_size,
                      self.resize_handle_size,
                      self.resize_handle_size)

    def hoverEnterEvent(self, event):
        self._is_hovered = True
        self.update()
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self._is_hovered = False
        self.update()
        super().hoverLeaveEvent(event)

    def change_color(self):
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        if not view:
            return
        color_dialog = ColorPickerDialog(QColor(self.stage_data.get('border_color', '#BDBDBD')), history_colors=(view.color_history if view else None))
        
        color_dialog.eyedropper_activated.connect(lambda: view.start_eyedropper_mode(color_dialog))
        
        if color_dialog.exec_():
            color = color_dialog.selected_color()
            if not color.isValid(): return
            if self.scene():
                view = self.scene().views()[0]
                view.color_history = color_dialog._history_colors.copy()
                view.save_undo_state()
                selected = self.scene().selectedItems() or [self]
                for item in selected:
                    if isinstance(item, StageGraphicsItem):
                        item.update_color(color.name())
                        if item.animation:
                            item._start_pulsing_animation()

    def update_color(self, color_name):
        self.stage_data['border_color'] = color_name
        self._animated_border_color = QColor(color_name)
        if self.animation:
            self.animation.stop()
        self.update()
        if self.scene():
            for conn in list(self.connections):
                if conn.scene():
                    conn.update()

    def update_data(self, new_data):
        if 'formatted_title' in new_data:
            self.rich_text_editor.from_json(new_data['formatted_title'])
            self.stage_data['title'] = self.rich_text_editor.get_raw_text()
        else:
            self.stage_data['title'] = new_data.get('title', self.stage_data.get('title', ''))
        self.stage_data.pop('width', None)
        self.stage_data.pop('height', None)
        self.recalculate_size()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and not self.get_resize_handle_rect().contains(event.pos()):
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                mapped_event = QMouseEvent(event.type(), view.mapFromScene(self.mapToScene(event.pos())), event.button(), event.buttons(), event.modifiers())
                QApplication.sendEvent(view, mapped_event)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

class ImageStageGraphicsItem(StageGraphicsItem):
    """Специализированный блок для отображения изображения и описания под ним с возможностью изменения размера."""
    def __init__(self, stage_data):
        super().__init__(stage_data, _recalculate=False)
        self.rich_text_editor = ScrollableRichTextEditor()  # Для поддержки форматирования
        from PyQt5.QtGui import QImage
        self.original_image = QImage(self.stage_data.get('image_path'))
        self.pixmap = QPixmap.fromImage(self.original_image)
        if 'image_width' in self.stage_data and not self.original_image.isNull():
            new_w = self.stage_data['image_width']
            self.pixmap = QPixmap.fromImage(self.original_image.scaledToWidth(new_w, Qt.SmoothTransformation))
        self.padding = 15
        self.text_margin_top = 10
        self.description_font = QFont('Finlandica Bold', 9)
        self._cached_desc = None
        self._cached_desc_html = None
        self._cached_desc_width = None
        self.recalculate_size()

    def recalculate_size(self, new_image_width=None):
        from PyQt5.QtGui import QImage
        self.prepareGeometryChange()
        if not self.original_image.isNull() and new_image_width is not None:
            self.pixmap = QPixmap.fromImage(self.original_image.scaledToWidth(int(new_image_width), Qt.SmoothTransformation))
        image_width = self.pixmap.width()
        image_height = self.pixmap.height()
        fm = QFontMetrics(self.description_font)
        text_wrap_width = image_width if image_width > 150 else 220
        description = self.stage_data.get('description', '')
        text_zone_height = fm.boundingRect(QRectF(0, 0, text_wrap_width, 10000).toRect(), Qt.TextWordWrap, description).height()
        new_width = max(image_width, text_wrap_width) + 2 * self.padding
        new_height = self.padding + image_height + (self.text_margin_top if description and text_zone_height > 0 else 0) + text_zone_height + self.padding
        self.rect = QRectF(0, 0, new_width, new_height)
        self.update()
        for conn in self.connections:
            conn.update_path()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        bg_color = QColor("#FFFFFF")
        border_width = 3
        border_color = self._animated_border_color if self.isSelected() else QColor(self.stage_data.get('border_color', '#BDBDBD'))
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, border_width))
        painter.drawRoundedRect(self.boundingRect(), 10, 10)
        if not self.pixmap.isNull():
            image_x = (self.rect.width() - self.pixmap.width()) / 2
            image_y = self.padding
            painter.drawPixmap(int(image_x), int(image_y), self.pixmap)
        text_wrap_width = self.rect.width() - 2 * self.padding
        text_x = self.padding
        text_y = self.padding + self.pixmap.height() + self.text_margin_top
        remaining_height = self.rect.height() - text_y - self.padding
        description_rect = QRectF(text_x, text_y, text_wrap_width, remaining_height)
        painter.setPen(QColor("#222"))
        painter.setFont(self.description_font)
        desc = self.stage_data.get('description', '')
        desc_html = parse_discord_to_html(desc)
        if (
            self._cached_desc is None or
            self._cached_desc_html != desc_html or
            self._cached_desc_width != text_wrap_width
        ):
            doc = QTextDocument()
            doc.setDefaultFont(self.description_font)
            doc.setHtml(desc_html)
            doc.setTextWidth(text_wrap_width)
            self._cached_desc = doc
            self._cached_desc_html = desc_html
            self._cached_desc_width = text_wrap_width
        doc = self._cached_desc
        painter.save()
        painter.translate(description_rect.left(), description_rect.top())
        doc.drawContents(painter, QRectF(0, 0, description_rect.width(), description_rect.height()))
        painter.restore()
        if getattr(self, 'is_locked', False):
            lock_rect = QRectF(self.boundingRect().left() + 6, self.boundingRect().top() + 6, 18, 18)
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(180, 180, 180))
            painter.drawEllipse(lock_rect)
            painter.setPen(QPen(QColor(100, 100, 100), 2))
            painter.drawArc(lock_rect.adjusted(3, 2, -3, 8), 30 * 16, 120 * 16)
            body_rect = QRectF(lock_rect.left() + 4, lock_rect.top() + 9, 10, 7)
            painter.setBrush(QColor(100, 100, 100))
            painter.drawRect(body_rect)
        if self._is_hovered:
            handle_rect = self.get_resize_handle_rect()
            arrow_color = self._animated_border_color if self.isSelected() else QColor(self.stage_data.get('border_color', '#BDBDBD'))
            painter.setPen(QPen(arrow_color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            start_point = handle_rect.bottomRight() - QPointF(4, 4)
            end_point = handle_rect.topLeft() + QPointF(4, 4)
            painter.drawLine(start_point, end_point)
            angle = math.atan2(start_point.y() - end_point.y(), start_point.x() - end_point.x())
            arrow_size = 6
            p1 = end_point + QPointF(math.cos(angle + math.pi / 6) * arrow_size, math.sin(angle + math.pi / 6) * arrow_size)
            p2 = end_point + QPointF(math.cos(angle - math.pi / 6) * arrow_size, math.sin(angle - math.pi / 6) * arrow_size)
            painter.drawLine(end_point, p1)
            painter.drawLine(end_point, p2)

    def hoverMoveEvent(self, event):
        if self.get_resize_handle_rect().contains(event.pos()) and self._is_hovered:
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mouseMoveEvent(self, event):
        if self.resizing:
            delta = event.scenePos() - self.last_mouse_pos
            self.last_mouse_pos = event.scenePos()
            new_width = self.pixmap.width() + delta.x()
            if new_width < 50: new_width = 50
            self.recalculate_size(new_image_width=new_width)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.resizing:
            self.resizing = False
            if not self.is_locked:
                self.setFlag(QGraphicsItem.ItemIsMovable, True)
            self.stage_data['image_width'] = self.pixmap.width()
            self.recalculate_size()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def get_stage_data(self):
        data = super().get_stage_data()
        data['image_width'] = self.pixmap.width()
        return data

    def update_data(self, new_data):
        self.stage_data['description'] = new_data.get('description', self.stage_data.get('description', '')).strip()
        self.stage_data['title'] = new_data.get('title', '')
        self.stage_data.pop('width', None)
        self.stage_data.pop('height', None)
        self.recalculate_size()

class TxtStageGraphicsItem(StageGraphicsItem):
    def __init__(self, stage_data):
        super().__init__(stage_data, _recalculate=False)
        self.rich_text_editor = ScrollableRichTextEditor()  # Для поддержки форматирования
        self.icon = QPixmap(32, 32)
        self.icon.fill(Qt.transparent)
        painter = QPainter(self.icon)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setBrush(QColor('#E0E0E0'))
        painter.setPen(QPen(QColor('#888'), 2))
        painter.drawRoundedRect(2, 2, 28, 28, 6, 6)
        painter.setPen(QPen(QColor('#1976D2'), 3))
        painter.setFont(QFont('Finlandica Bold', 16, QFont.Bold))
        painter.drawText(self.icon.rect(), Qt.AlignCenter, 'TXT')
        painter.end()
        self.font = QFont("Finlandica", 12)
        self.preview_font = QFont("Finlandica Bold", 9)
        self._expanded = False
        self._cached_lines = None
        self._cached_title = None
        self.recalculate_size()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._click_pos = event.scenePos()
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                inv = view.transform().inverted()[0]
                self._drag_offset = inv.map(event.pos())
            else:
                self._drag_offset = event.pos()
            self.setSelected(True)
            self._dragged = False
            super().mousePressEvent(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if hasattr(self, '_click_pos') and (event.scenePos() - self._click_pos).manhattanLength() > 3:
            self._dragged = True
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                inv = view.transform().inverted()[0]
                offset = self._drag_offset
                new_pos = event.scenePos() - view.mapToScene(view.mapFromScene(self.pos()) + view.mapFromScene(offset))
                self.setPos(self.pos() + new_pos)
            else:
                new_pos = event.scenePos() - self._drag_offset
                self.setPos(new_pos)
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if not getattr(self, '_dragged', False):
                self._expanded = not getattr(self, '_expanded', False)
                self.recalculate_size()
                self.update()
            self._dragged = False
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def recalculate_size(self):
        self.prepareGeometryChange()
        icon_size = 40
        padding = 6
        max_width = 56
        fm = QFontMetrics(self.font)
        title = self.stage_data.get('title', 'Новый txt-файл')
        # Разбиваем на строки по ширине max_width
        lines = []
        current = ''
        for word in title.split():
            test = (current + ' ' + word).strip()
            if fm.width(test) <= max_width - 2 * padding:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        # Если не раскрыт — максимум 3 строки, последняя с многоточием
        if not getattr(self, '_expanded', False):
            if len(lines) > 3:
                lines = lines[:2] + [fm.elidedText(' '.join(lines[2:]), Qt.ElideRight, max_width - 2 * padding)]
        height = icon_size + len(lines) * fm.height() + 3 * padding
        self._txt_lines = lines
        self.rect = QRectF(0, 0, max_width, height)
        self._cached_lines = lines
        self._cached_title = title
        self.update()
        for conn in self.connections:
            conn.update_path()

    def paint(self, painter, option, widget=None):
        painter.setRenderHint(QPainter.Antialiasing)
        # Нет рамки и фона блока
        # Рисуем иконку-ярлык (лист с уголком)
        icon_x = int(self.rect.left() + (self.rect.width() - 40) / 2)
        icon_y = int(self.rect.top())
        # Лист
        paper_rect = QRectF(icon_x, icon_y, 40, 40)
        painter.setBrush(QColor('#FFFFFF'))
        painter.setPen(QPen(QColor('#CCCCCC'), 1.5))
        painter.drawRoundedRect(paper_rect, 6, 6)
        # Загнутый уголок
        painter.setBrush(QColor('#F0F0F0'))
        painter.setPen(Qt.NoPen)
        painter.drawPolygon(
            QPointF(icon_x + 40, icon_y),
            QPointF(icon_x + 32, icon_y),
            QPointF(icon_x + 40, icon_y + 8)
        )
        # Серый прямоугольник с TXT
        txt_rect = QRectF(icon_x + 7, icon_y + 15, 26, 14)
        painter.setBrush(QColor('#888888'))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(txt_rect, 4, 4)
        painter.setFont(QFont('Finlandica Bold', 8, QFont.Bold))
        painter.setPen(QColor('#FFFFFF'))
        painter.drawText(txt_rect, Qt.AlignCenter, 'TXT')
        # Подпись — только название файла
        painter.setFont(self.font)
        painter.setPen(QColor('#222'))
        fm = QFontMetrics(self.font)
        title = self.stage_data.get('title', 'Новый txt-файл')
        max_width = self.rect.width() - 12
        if self._cached_lines is None or self._cached_title != title:
            lines = []
            current = ''
            for word in title.split():
                test = (current + ' ' + word).strip()
                if fm.width(test) <= max_width:
                    current = test
                else:
                    if current:
                        lines.append(current)
                    current = word
            if current:
                lines.append(current)
            self._cached_lines = lines
            self._cached_title = title
        lines = self._cached_lines
        for i, line in enumerate(lines):
            text_x = int(self.rect.left() + 6)
            text_y = int(self.rect.top() + 40 + fm.ascent() + 4 + i * fm.height())
            painter.drawText(text_x, text_y, line)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and not self.get_resize_handle_rect().contains(event.pos()):
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            if view:
                mapped_event = QMouseEvent(event.type(), view.mapFromScene(self.mapToScene(event.pos())), event.button(), event.buttons(), event.modifiers())
                QApplication.sendEvent(view, mapped_event)
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            actions = []
            def edit_action():
                if self.scene() and self.scene().views():
                    self.scene().views()[0].edit_stage(self)
            def delete_action():
                if self.scene() and self.scene().views():
                    view = self.scene().views()[0]
                    view.save_undo_state()
                    items_to_delete = self.scene().selectedItems() or [self]
                    for item in items_to_delete:
                        if isinstance(item, StageGraphicsItem):
                            view.delete_stage(item, save_state=False)
            actions.append(('Редактировать txt', edit_action))
            actions.append(('Удалить', delete_action))
            menu = GlassMenu(actions, parent=self.scene().views()[0] if self.scene() and self.scene().views() else None)
            menu.show_at(event.screenPos())
            event.accept()
            return
        super().mousePressEvent(event)

    def get_stage_data(self):
        data = super().get_stage_data()
        data['note_text'] = self.stage_data.get('note_text', '')
        return data

    def update_data(self, new_data):
        if 'formatted_note_text' in new_data:
            self.rich_text_editor.from_json(new_data['formatted_note_text'])
            self.stage_data['note_text'] = self.rich_text_editor.get_raw_text()
        else:
            self.stage_data['note_text'] = new_data.get('note_text', self.stage_data.get('note_text', ''))
        self.stage_data['title'] = new_data.get('title', self.stage_data.get('title', ''))
        self.stage_data.pop('width', None)
        self.stage_data.pop('height', None)
        self.recalculate_size()

    def itemChange(self, change, value):
        res = super().itemChange(change, value)
        if change == QGraphicsItem.ItemSelectedChange:
            if not value:
                self._expanded = False
                self.recalculate_size()
        return res

    def shape(self):
        path = QPainterPath()
        # Область иконки
        icon_x = (self.rect.width() - 40) / 2
        icon_y = 0
        path.addRoundedRect(QRectF(icon_x, icon_y, 40, 40), 6, 6)
        # Область подписи (высота зависит от количества строк)
        fm = QFontMetrics(self.font)
        text_height = len(getattr(self, '_txt_lines', [])) * fm.height()
        text_y = 40 + 4
        path.addRect(QRectF(0, text_y, self.rect.width(), text_height))
        return path

    def contains(self, point):
        return self.shape().contains(point)

class GridGraphicsItem(QGraphicsItem):
    def __init__(self, scene_rect, grid_size=40, parent=None):
        super().__init__(parent)
        self.setZValue(-100)
        self.grid_size = grid_size
        self.scene_rect = scene_rect
        self.setFlag(QGraphicsItem.ItemIgnoresTransformations, False)
        self.setAcceptedMouseButtons(Qt.NoButton)
    def boundingRect(self):
        return self.scene_rect
    def paint(self, painter, option, widget=None):
        painter.setPen(QPen(QColor(220,220,220), 1))
        left = int(self.scene_rect.left())
        right = int(self.scene_rect.right())
        top = int(self.scene_rect.top())
        bottom = int(self.scene_rect.bottom())
        for x in range(left - left % self.grid_size, right, self.grid_size):
            painter.drawLine(x, top, x, bottom)
        for y in range(top - top % self.grid_size, bottom, self.grid_size):
            painter.drawLine(left, y, right, y)

class RoadMapWidget(QGraphicsView):
    stage_edit_requested = pyqtSignal(object); new_project_requested = pyqtSignal()
    open_project_requested = pyqtSignal(); save_project_requested = pyqtSignal()
    save_as_project_requested = pyqtSignal(); export_png_requested = pyqtSignal()
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRenderHint(QPainter.Antialiasing)
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.scene.setSceneRect(-5000, -5000, 10000, 10000)
        self.drawing_arrow_mode = False
        self.arrow_start_item = None
        self._drag_mode_before_arrow_draw = QGraphicsView.ScrollHandDrag
        self.focused_on_sources = []
        self.preview_items = set()
        self.undo_stack = []
        self.redo_stack = []
        self._is_dragging = False
        self._eyedropper_mode = False
        self._eyedropper_dialog = None
        self._drag_mode_before_eyedropper = self.dragMode()
        self.color_history = []
        self.timelines = []
        self.show_grid = False
        self.grid_item = None
        self.setup_ui()
        self.scene.selectionChanged.connect(self.handle_selection_changed)

    def setup_ui(self):
        self.setTransformationAnchor(QGraphicsView.AnchorUnderMouse)
        self.setDragMode(QGraphicsView.ScrollHandDrag)
        self.setStyleSheet("background-color: #FFFFFF; border: none;")
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setFocus()

    def focusOutEvent(self, event):
        self.setFocus()
        super().focusOutEvent(event)

    def add_connection(self, start_item, end_item, save_state=True):
        if save_state: self.save_undo_state()
        connection = ConnectionGraphicsItem(start_item, end_item)
        start_item.add_connection(connection)
        end_item.add_connection(connection)
        self.scene.addItem(connection)
        connection.half_clicked.connect(self.handle_half_click)
        connection.half_hovered.connect(self.handle_half_hover)

    def delete_connection(self, connection):
        self.save_undo_state()
        if connection in connection.start_item.connections:
            connection.start_item.connections.remove(connection)
        if connection in connection.end_item.connections:
            connection.end_item.connections.remove(connection)
        self.scene.removeItem(connection)

    def toggle_connection(self, item1, item2):
        for conn in list(item1.connections):
            if (conn.start_item == item1 and conn.end_item == item2) or \
               (conn.start_item == item2 and conn.end_item == item1):
                self.delete_connection(conn)
                return
        self.add_connection(item1, item2)
        
    def check_and_expand_scene(self, item):
        margin = 1500
        item_rect_in_scene = item.mapToScene(item.boundingRect()).boundingRect()
        required_rect = item_rect_in_scene.adjusted(-margin, -margin, margin, margin)
        current_rect = self.sceneRect()
        new_scene_rect = current_rect.united(required_rect)
        if new_scene_rect != current_rect:
            self.setSceneRect(new_scene_rect)
            
    def handle_selection_changed(self):
        if self.focused_on_sources: return
        selected_items = self.scene.selectedItems()
        for item in self.scene.items():
            if isinstance(item, StageGraphicsItem):
                if item in selected_items: item._start_pulsing_animation()
                else: item.animation.stop()

    def _get_reachable_nodes_undirected_excluding_edge(self, from_node, exclude_a, exclude_b):
        nodes = set()
        queue = [from_node]
        visited = {from_node}
        while queue:
            current = queue.pop(0)
            nodes.add(current)
            for conn in self.scene.items():
                if isinstance(conn, ConnectionGraphicsItem):
                    if ((conn.start_item == exclude_a and conn.end_item == exclude_b) or
                        (conn.start_item == exclude_b and conn.end_item == exclude_a)):
                        continue
                    if conn.start_item == current and conn.end_item not in visited:
                        visited.add(conn.end_item)
                        queue.append(conn.end_item)
                    if conn.end_item == current and conn.start_item not in visited:
                        visited.add(conn.start_item)
                        queue.append(conn.start_item)
        return nodes

    def _calculate_nodes_to_hide(self, connection, half):
        start_node, end_node = connection.start_item, connection.end_item
        if half == 'start':
            return self._get_reachable_nodes_undirected_excluding_edge(end_node, start_node, end_node)
        else:
            return self._get_reachable_nodes_undirected_excluding_edge(start_node, start_node, end_node)

    def handle_half_hover(self, connection, half, is_active):
        for item in self.preview_items:
            if isinstance(item, StageGraphicsItem) and item.scene():
                item.animation.stop()
        self.preview_items.clear()
        if not is_active or self.focused_on_sources: return
        nodes_to_hide = self._calculate_nodes_to_hide(connection, half)
        self.preview_items = nodes_to_hide
        for node in nodes_to_hide:
            if node.scene():
                node._start_pulsing_animation()

    def _reset_preview(self):
        for item in list(self.preview_items):
            if isinstance(item, StageGraphicsItem) and item.scene():
                if item.animation: item.animation.stop()
            elif isinstance(item, QGraphicsLineItem) and item.scene() == self.scene:
                self.scene.removeItem(item)
        self.preview_items.clear()

    def handle_half_click(self, connection, half):
        self._reset_preview()
        focus_source = (connection, half)

        if focus_source in self.focused_on_sources:
            self.reset_focus()
            return
        else:
            self.focused_on_sources.append(focus_source)

        if not self.focused_on_sources:
            self.reset_focus()
            return

        all_nodes_to_hide = set()
        # Фильтруем неактуальные источники фокуса (если связь была удалена)
        self.focused_on_sources = [s for s in self.focused_on_sources if s[0].scene()]
        
        for conn, h in self.focused_on_sources:
            nodes_to_hide_for_source = self._calculate_nodes_to_hide(conn, h)
            all_nodes_to_hide.update(nodes_to_hide_for_source)

        all_nodes = {item for item in self.scene.items() if isinstance(item, StageGraphicsItem)}
        active_nodes = all_nodes - all_nodes_to_hide
        self._apply_focus(active_nodes)

    def reset_focus(self):
        self.focused_on_sources.clear()
        self._reset_preview()
        all_items = list(self.scene.items())
        for item in all_items:
            if isinstance(item, StageGraphicsItem):
                item.setOpacity(1.0)
                if item.animation: item.animation.stop()
        for item in all_items:
            if isinstance(item, ConnectionGraphicsItem) and item.scene(): item.update()
        self.handle_selection_changed()
        self.scene.update()

    def _apply_focus(self, active_nodes):
        all_items = list(self.scene.items())
        for item in all_items:
            if isinstance(item, StageGraphicsItem):
                is_lonely = len(item.connections) == 0
                is_active = item in active_nodes or is_lonely
                item.setOpacity(1.0 if is_active else 0.3)
                if item.animation: item.animation.stop()
                if is_active: item._start_pulsing_animation()
        for item in all_items:
            if isinstance(item, ConnectionGraphicsItem) and item.scene(): item.update()
        self.scene.update()

    def mousePressEvent(self, event):
        self.setFocus()
        if self._eyedropper_mode:
            item_at_pos = self.itemAt(event.pos())
            color_to_set = None

            if isinstance(item_at_pos, StageGraphicsItem):
                color_to_set = QColor(item_at_pos.stage_data.get('border_color', '#BDBDBD'))
            
            if color_to_set and self._eyedropper_dialog:
                self._eyedropper_dialog.eyedropper_color_picked(color_to_set)
                self.end_eyedropper_mode()
            else:
                if self._eyedropper_dialog:
                    self._eyedropper_dialog.show()
                self.end_eyedropper_mode()

            event.accept()
            return

        self._reset_preview()
        if self.drawing_arrow_mode:
            item = self.itemAt(event.pos())
            if isinstance(item, StageGraphicsItem):
                if not self.arrow_start_item:
                    self.arrow_start_item = item
                elif self.arrow_start_item != item:
                    self.toggle_connection(self.arrow_start_item, item)
                    self.arrow_start_item = None
            elif isinstance(item, TimelineGuideItem):
                # Добавляем блок в таймлайн
                if self.arrow_start_item and self.arrow_start_item not in item.associated_items:
                    item.add_block(self.arrow_start_item)
                    self.arrow_start_item = None
            # Не вызываем super, чтобы не было лишних событий
            return
        else:
            if event.button() == Qt.LeftButton: self._is_dragging = True
            super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton:
            if self._is_dragging:
                self._is_dragging = False
                self.save_undo_state()
            super().mouseReleaseEvent(event)
        else:
            super().mouseReleaseEvent(event)

    def add_stage(self, stage_data=None, position=None, save_state=True):
        if save_state: self.save_undo_state()
        if stage_data is None:
            stage_data = {'id': str(uuid.uuid4()), 'title': 'Новый этап', 'border_color': '#BDBDBD',
                          'position': self.mapToScene(position) if position else QPointF(50, 50)}
        item_type = stage_data.get('type', 'text')
        if item_type == 'image':
            item = ImageStageGraphicsItem(stage_data)
        elif item_type == 'txt':
            item = TxtStageGraphicsItem(stage_data)
        else:
            item = StageGraphicsItem(stage_data)
        pos_data = stage_data.get('position')
        pos = QPointF(pos_data.get('x', 0), pos_data.get('y', 0)) if isinstance(pos_data, dict) else pos_data
        item.setPos(pos)
        self.scene.addItem(item)
        self.scene.clearSelection()
        item.setSelected(True)
        return item
        
    def delete_stage(self, item, save_state=True):
        if save_state: self.save_undo_state()
        if self.focused_on_sources: self.reset_focus()
        connections_to_remove = list(item.connections)
        for conn in connections_to_remove:
            if conn.scene():
                if conn in conn.start_item.connections: conn.start_item.connections.remove(conn)
                if conn in conn.end_item.connections: conn.end_item.connections.remove(conn)
                self.scene.removeItem(conn)
        for timeline in list(self.timelines):
            if hasattr(timeline, 'associated_items') and item in timeline.associated_items:
                timeline.on_block_deleted(item)
        if item.scene(): self.scene.removeItem(item)

    def edit_stage(self, stage_item):
        self.save_undo_state()
        data = stage_item.get_stage_data().copy()
        # Определяем тип этапа
        stage_type = data.get('type', '')
        if stage_type == 'txt':
            # Собираем все существующие названия txt-файлов (кроме текущего)
            all_titles = [item.stage_data.get('title', '') for item in self.scene.items() if hasattr(item, 'stage_data') and item.stage_data.get('type') == 'txt' and item is not stage_item]
            initial_title = data.get('title', '')
            if initial_title == 'Новый txt-файл':
                initial_title = ''
            dialog = TxtFileEditDialog(
                initial_title=initial_title,
                initial_text=data.get('note_text', ''),
                existing_titles=all_titles,
                parent=self
            )
            # --- интеграция форматирования ---
            if 'formatted_note_text' in data:
                dialog.editor.from_json(data['formatted_note_text'])
            if dialog.exec_() == dialog.Accepted:
                new_title = dialog.get_title()
                # Сохраняем форматированный текст
                formatted_note_text = dialog.get_formatted_json()
                data['title'] = new_title
                data['note_text'] = dialog.get_text()
                data['formatted_note_text'] = formatted_note_text
                stage_item.update_data(data)
        elif stage_type == 'image':
            # Для изображений редактируем description
            text = data.get('description', '')
            dialog = CustomTextEditDialog(text, self)
            if 'formatted_description' in data:
                dialog.editor.from_json(data['formatted_description'])
            if dialog.exec_() == dialog.Accepted:
                new_text = dialog.get_text()
                formatted_description = dialog.get_formatted_json()
                data['description'] = new_text
                data['formatted_description'] = formatted_description
                stage_item.update_data(data)
        else:
            text = data.get('note_text', data.get('title', ''))
            # Если это стартовый текст — очищаем поле для ввода
            if text == 'Новый этап':
                text = ''
            dialog = CustomTextEditDialog(text, self)
            if 'formatted_title' in data:
                dialog.editor.from_json(data['formatted_title'])
            if dialog.exec_() == dialog.Accepted:
                new_text = dialog.get_text()
                formatted_title = dialog.get_formatted_json()
                if 'note_text' in data:
                    data['note_text'] = new_text
                    data['formatted_note_text'] = formatted_title
                else:
                    data['title'] = new_text
                    data['formatted_title'] = formatted_title
                stage_item.update_data(data)

    def wheelEvent(self, event):
        zoom_in_factor = 1.25
        zoom_out_factor = 1 / zoom_in_factor
        current_zoom = self.transform().m11()

        if event.angleDelta().y() > 0: # Zoom In
            if current_zoom > 10.0:
                return
            self.scale(zoom_in_factor, zoom_in_factor)
        else: # Zoom Out
            if current_zoom < 0.05: # Предел минимального отдаления
                return
            items_rect = self.scene.itemsBoundingRect()
            padding = 2000
            padded_rect = items_rect.adjusted(-padding, -padding, padding, padding)
            new_scene_rect = self.sceneRect().united(padded_rect)
            if new_scene_rect != self.sceneRect():
                self.setSceneRect(new_scene_rect)
            self.scale(zoom_out_factor, zoom_out_factor)
        
    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier and event.key() == Qt.Key_G:
            self.toggle_grid()
            return
        if event.matches(QKeySequence.Paste):
            clipboard = QApplication.clipboard()
            text = clipboard.text()
            if text.strip():
                # Получаем позицию мыши относительно сцены
                mouse_pos = QCursor.pos()
                view_pos = self.mapFromGlobal(mouse_pos)
                scene_pos = self.mapToScene(view_pos)
                stage_data = {'type': 'txt', 'title': 'Вставка', 'note_text': text, 'position': scene_pos}
                self.add_stage(stage_data)
                return
        if event.key() == Qt.Key_Escape and self._eyedropper_mode:
            if self._eyedropper_dialog:
                self._eyedropper_dialog.show()
            self.end_eyedropper_mode()
            return
        if event.key() == Qt.Key_Control and not self.drawing_arrow_mode:
            self.drawing_arrow_mode = True
            self._drag_mode_before_arrow_draw = self.dragMode()
            self.setDragMode(QGraphicsView.NoDrag)
            self.setCursor(Qt.CrossCursor)
        elif event.key() == Qt.Key_Z and (event.modifiers() & Qt.ControlModifier):
            if event.modifiers() & Qt.ShiftModifier:
                if self.redo_stack:
                    state = self.redo_stack.pop()
                    self.undo_stack.append(self.get_project_data())
                    self.load_project(state)
            else:
                if self.undo_stack:
                    state = self.undo_stack.pop()
                    self.redo_stack.append(self.get_project_data())
                    self.load_project(state)
            return
        elif event.key() == Qt.Key_Delete:
            self.delete_selected()
            return
        super().keyPressEvent(event)
        
    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Control:
            self.drawing_arrow_mode = False
            self.arrow_start_item = None
            self._reset_preview()
            self.setDragMode(self._drag_mode_before_arrow_draw)
            self.setCursor(Qt.ArrowCursor) 
        super().keyReleaseEvent(event)
        
    def mouseMoveEvent(self, event):
        if self.drawing_arrow_mode and self.arrow_start_item:
            self._reset_preview()
            end_pos = self.mapToScene(event.pos())
            line = QGraphicsLineItem(self.arrow_start_item.scenePos().x(), self.arrow_start_item.scenePos().y(), end_pos.x(), end_pos.y())
            line.setPen(QPen(Qt.black, 2, Qt.DashLine))
            self.scene.addItem(line)
            self.preview_items.add(line)
        super().mouseMoveEvent(event)
        
    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.setDragMode(QGraphicsView.RubberBandDrag if self.dragMode() == QGraphicsView.ScrollHandDrag else QGraphicsView.ScrollHandDrag)
            event.accept()
        else:
            super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self._last_context_pos = event.pos()
        actions = []
        def create_stage(): self.add_stage_at_pos(self._last_context_pos)
        def create_image_stage(): self.add_image_stage_at_pos(self._last_context_pos)
        def create_txt_stage(): self.add_txt_stage_at_pos(self._last_context_pos)
        def import_txt():
            file_path, _ = QFileDialog.getOpenFileName(self, 'Импортировать txt', '', 'Текстовые файлы (*.txt)')
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                stage_data = {'type': 'txt', 'title': file_path.split('/')[-1], 'note_text': content, 'position': self.mapToScene(self._last_context_pos)}
                self.add_stage(stage_data)
        def show_timeline(): self.show_timeline()
        selected = self.get_selected_items()
        if len(selected) >= 2:
            actions.append(("Показать таймлайн", show_timeline))
        else:
            actions.append(("Создать текстовый этап", create_stage))
            actions.append(("Создать изображение", create_image_stage))
            actions.append(("Создать txt-файл", create_txt_stage))
            actions.append(("Импортировать txt", import_txt))
            # actions.append(None)  # Можно убрать разделитель, если не нужно
            # Удалены: Открыть проект, Сохранить проект, Экспорт в PNG
        menu = GlassMenu(actions, parent=self)
        menu.show_at(event.globalPos())
        
    def clear(self): 
        self.reset_focus()
        self.scene.clear()
        self.timelines.clear()
        
    def get_project_data(self):
        stages = []
        connections = []
        for item in self.scene.items():
            if isinstance(item, StageGraphicsItem):
                stage_data = item.get_stage_data()
                pos = stage_data.get('position', {})
                if isinstance(pos, dict):
                    pos['x'] = round(pos.get('x', 0), 2)
                    pos['y'] = round(pos.get('y', 0), 2)
                stages.append(stage_data)
        stages.sort(key=lambda x: x.get('id', ''))
        for item in self.scene.items():
            if isinstance(item, ConnectionGraphicsItem):
                conn_data = {'from': item.start_item.stage_data['id'], 'to': item.end_item.stage_data['id']}
                connections.append(conn_data)
        connections.sort(key=lambda x: (x['from'], x['to']))
        scene_rect = self.sceneRect()
        return {
            'stages': stages, 
            'connections': connections,
            'scene_rect': {
                'x': scene_rect.x(), 'y': scene_rect.y(),
                'width': scene_rect.width(), 'height': scene_rect.height()
            },
            'color_history': [color.name() for color in self.color_history]
        }

    def states_are_equal(self, state1, state2):
        if not state1 or not state2: return False
        if len(state1.get('stages', [])) != len(state2.get('stages', [])): return False
        if len(state1.get('connections', [])) != len(state2.get('connections', [])): return False
        if state1.get('stages', []) != state2.get('stages', []): return False
        if state1.get('connections', []) != state2.get('connections', []): return False
        return True

    def save_undo_state(self):
        current_state = self.get_project_data()
        if not self.undo_stack or not self.states_are_equal(current_state, self.undo_stack[-1]):
            self.undo_stack.append(current_state)
            if len(self.undo_stack) > 20:
                self.undo_stack.pop(0)
            self.redo_stack.clear()

    def load_project(self, project_data):
        self.clear()
        scene_rect_data = project_data.get('scene_rect')
        if scene_rect_data:
            self.setSceneRect(QRectF(
                scene_rect_data.get('x', -5000), scene_rect_data.get('y', -5000),
                scene_rect_data.get('width', 10000), scene_rect_data.get('height', 10000)
            ))
        color_history_data = project_data.get('color_history')
        if color_history_data:
            self.color_history = [QColor(name) for name in color_history_data]
        else:
            self.color_history = []
        items_by_id = {}
        stages = sorted(project_data.get('stages', []), key=lambda x: x.get('id', ''))
        for stage_d in stages:
            item = self.add_stage(stage_d, save_state=False)
            items_by_id[item.stage_data['id']] = item
            if 'border_color' in stage_d: item.update_color(stage_d['border_color'])
        connections = sorted(project_data.get('connections', []), key=lambda x: (x.get('from', ''), x.get('to', '')))
        for conn_d in connections:
            start_item = items_by_id.get(conn_d.get('from'))
            end_item = items_by_id.get(conn_d.get('to'))
            if start_item and end_item and start_item.scene() and end_item.scene():
                self.add_connection(start_item, end_item, save_state=False)

    def export_to_image(self, file_path, format='PNG'):
        if not self.scene.items(): return
        self.scene.clearSelection()
        rect = self.scene.itemsBoundingRect()
        padding = 20
        rect.adjust(-padding, -padding, padding, padding)
        scale_factor = 1.5
        image_size = (rect.size() * scale_factor).toSize()
        image = QImage(image_size, QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        self.scene.render(painter, QRectF(image.rect()), rect)
        painter.end()
        image.save(file_path, format)

    def add_stage_at_pos(self, pos):
        stage_data = {'type': 'text', 'title': 'Новый этап', 'position': self.mapToScene(pos)}
        self.add_stage(stage_data)

    def add_image_stage_at_pos(self, pos):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Выбрать изображение', '', 'Изображения (*.png *.jpg *.jpeg *.webp *.gif)')
        if file_path:
            stage_data = {'type': 'image', 'title': '', 'description': '', 'image_path': file_path, 'position': self.mapToScene(pos)}
            self.add_stage(stage_data)

    def add_txt_stage_at_pos(self, pos):
        stage_data = {'type': 'txt', 'title': 'Новый txt-файл', 'note_text': '', 'position': self.mapToScene(pos)}
        self.add_stage(stage_data)

    def delete_selected(self):
        self.save_undo_state()
        selected = [item for item in self.scene.selectedItems() if isinstance(item, StageGraphicsItem)]
        for item in selected:
            self.delete_stage(item, save_state=False)

    def show_timeline(self):
        selected = self.get_selected_items()
        if len(selected) > 1:
            timeline = TimelineGuideItem(selected, self.scene, self)
            self.scene.addItem(timeline)
            self.timelines.append(timeline)

    def get_selected_items(self):
        return [item for item in self.scene.items() if isinstance(item, StageGraphicsItem) and item.isSelected()]

    def remove_timeline(self, timeline_to_remove):
        if timeline_to_remove in self.timelines: self.timelines.remove(timeline_to_remove)
        if timeline_to_remove.scene() == self.scene: self.scene.removeItem(timeline_to_remove)

    def start_eyedropper_mode(self, dialog):
        self._eyedropper_dialog = dialog
        self._eyedropper_mode = True
        self._drag_mode_before_eyedropper = self.dragMode()
        self.setDragMode(QGraphicsView.NoDrag)
        self.setCursor(Qt.CrossCursor)

    def end_eyedropper_mode(self):
        self._eyedropper_mode = False
        self._eyedropper_dialog = None
        self.setDragMode(self._drag_mode_before_eyedropper)
        self.setCursor(Qt.ArrowCursor)

    def toggle_grid(self):
        self.show_grid = not self.show_grid
        if self.show_grid:
            if self.grid_item:
                self.scene.removeItem(self.grid_item)
            self.grid_item = GridGraphicsItem(self.scene.sceneRect())
            self.scene.addItem(self.grid_item)
        else:
            if self.grid_item:
                self.scene.removeItem(self.grid_item)
                self.grid_item = None
        self.scene.update()
        self.viewport().update()

def parse_discord_to_html(text):
    import re
    # Сначала моноширинный, потом зачёркнутый, потом жирный+курсив, потом жирный, потом курсив
    text = re.sub(r'`([^`]+)`', r'<span style="font-family:Consolas; background:#f4f4f4;">\1</span>', text)
    text = re.sub(r'~~([^~]+)~~', r'<s>\1</s>', text)
    text = re.sub(r'\*\*\*([^*]+)\*\*\*', r'<b><i>\1</i></b>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'\*([^*]+)\*', r'<i>\1</i>', text)
    text = re.sub(r'_([^_]+)_', r'<i>\1</i>', text)
    # --- Фикс начальных пробелов ---
    def replace_leading_spaces(line):
        return re.sub(r'^ +', lambda m: '&nbsp;' * len(m.group(0)), line)
    text = '\n'.join(replace_leading_spaces(line) for line in text.split('\n'))
    return text.replace('\n', '<br>')