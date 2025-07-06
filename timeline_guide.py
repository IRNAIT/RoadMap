from PyQt5.QtWidgets import QGraphicsObject, QGraphicsTextItem, QMenu, QInputDialog, QGraphicsItem, QStyle, QApplication
from PyQt5.QtCore import Qt, QRectF, QPointF, pyqtSignal, QTimer
from PyQt5.QtGui import QPen, QColor, QFont, QPainterPath, QTextOption, QPainterPathStroker
from glass_menu import GlassMenu
from glass_input_dialog import GlassInputDialog

TICK_OFFSET = 8

# --- Вспомогательные классы для подписей (из старой версии) ---

class TimelineLabelItem(QGraphicsTextItem):
    def __init__(self, text, orientation, parent=None):
        super().__init__(text, parent)
        self.orientation = orientation
        self.setDefaultTextColor(QColor('#000000'))
        font = QFont("Arial", 10, QFont.Bold)
        font.setItalic(True)
        self.setFont(font)
        self.setZValue(10001)
        self.setTextWidth(-1)
        self.custom_text = text
        self.tick1 = None
        self.tick2 = None
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setTextInteractionFlags(Qt.NoTextInteraction)
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)

        # Центрирование текста
        option = QTextOption(self.document().defaultTextOption())
        option.setAlignment(Qt.AlignHCenter)
        self.document().setDefaultTextOption(option)

    def boundingRect(self):
        # Добавляем невидимые поля в 5 пикселей для удобства нажатия
        return super().boundingRect().adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget=None):
        # Отключаем стандартную рамку выделения
        option.state &= ~QStyle.State_Selected
        super().paint(painter, option, widget)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:

            def edit_action():
                view = self.scene().views()[0] if self.scene() and self.scene().views() else None
                text, ok = GlassInputDialog.getText(view, 'Редактировать подпись', 'Введите текст:', self.custom_text)
                if ok:
                    self.set_text(text)

            def delete_action():
                parent = self.parentItem()
                if isinstance(parent, TimelineGuideItem):
                    parent.remove_label(self)

            actions = [
                ('Редактировать', edit_action),
                ('Удалить', delete_action)
            ]
            
            view = self.scene().views()[0] if self.scene() and self.scene().views() else None
            menu = GlassMenu(actions, parent=view)
            menu.show_at(event.screenPos())
            
            event.accept()
        else:
            super().mousePressEvent(event)

    def update_position(self):
        if not self.tick1 or not self.tick2:
            return

        p1 = self.tick1.pos()
        p2 = self.tick2.pos()
        OFFSET = 12
        guide = self.parentItem()
        if not guide:
            return

        if self.orientation == 'horizontal':
            x_new = min(p1.x(), p2.x())
            width = abs(p2.x() - p1.x())
            self.setTextWidth(width)
            # Позиционируем относительно линии, а не глобальных координат
            y_new = guide.line_path.pointAtPercent(0).y() - self.boundingRect().height() - OFFSET
            self.setPos(x_new, y_new)
        else: # vertical
            y_top = min(p1.y(), p2.y())
            height = abs(p1.y() - p2.y())
            self.document().setTextWidth(150) # Ограничиваем ширину
            self.setTextWidth(150)
            x_new = guide.line_path.pointAtPercent(0).x() - self.boundingRect().width() - OFFSET
            y_new = y_top + (height - self.boundingRect().height())/2
            self.setPos(x_new, y_new)
        self.update()

    def set_text(self, text):
        self.custom_text = text
        self.setPlainText(text)
        self.update_position()

class LabelButtonItem(QGraphicsObject):
    def __init__(self, tick1, tick2, orientation, parent=None):
        super().__init__(parent)
        self.tick1 = tick1
        self.tick2 = tick2
        self.orientation = orientation
        self.setZValue(9000)
        self.setAcceptedMouseButtons(Qt.LeftButton)
        self.update_position()

    def update_position(self):
        p1 = self.tick1.pos()
        p2 = self.tick2.pos()
        button_thickness = 16 # Увеличили толщину для удобства нажатия

        if self.orientation == 'horizontal':
            x = min(p1.x(), p2.x())
            y = p1.y() - button_thickness / 2
            width = abs(p2.x() - p1.x())
            height = button_thickness
            self.setPos(x, y)
            self._rect = QRectF(0, 0, width, height)
        else: # vertical
            x = p1.x() - button_thickness / 2
            y = min(p1.y(), p2.y())
            width = button_thickness
            height = abs(p2.y() - p1.y())
            self.setPos(x, y)
            self._rect = QRectF(0, 0, width, height)
        self.update()

    def boundingRect(self):
        return self._rect

    def paint(self, painter, option, widget=None):
        pass # Невидимый элемент

    def mousePressEvent(self, event):
        parent = self.parentItem()
        if parent and hasattr(parent, 'on_label_button_clicked'):
            parent.on_label_button_clicked(self)
        event.accept()

# --- Основные классы (обновленная логика) ---

class TickItem(QGraphicsObject):
    def __init__(self, guide, block=None, side=None, relative_offset=None, original_scene_pos=None):
        super().__init__(guide)
        self.guide = guide
        self.block = block
        self.side = side
        self.relative_offset = relative_offset
        self.length = 24
        self.setAcceptedMouseButtons(Qt.LeftButton | Qt.RightButton)
        self.setFlag(QGraphicsItem.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.ItemIsFocusable, True)
        self.setZValue(10000)
        # Для custom_ticks сохраняем исходную позицию
        if block is None and relative_offset is not None:
            self.original_scene_pos = original_scene_pos
        else:
            self.original_scene_pos = None
        self.update_position()

    def update_position(self):
        self.prepareGeometryChange()
        guide_line_path = self.guide.line_path
        guide_line_start = guide_line_path.pointAtPercent(0)
        guide_line_end = guide_line_path.pointAtPercent(1)
        if self.relative_offset is not None:
            # Для custom_ticks: сначала пробуем позицию по relative_offset
            if self.block is None and self.original_scene_pos is not None:
                # 1. Позиция по relative_offset
                if self.guide.orientation == 'horizontal':
                    length = guide_line_end.x() - guide_line_start.x()
                    rel_x = guide_line_start.x() + self.relative_offset * length
                    rel_pos = QPointF(rel_x, guide_line_start.y())
                else:
                    length = guide_line_end.y() - guide_line_start.y()
                    rel_y = guide_line_start.y() + self.relative_offset * length
                    rel_pos = QPointF(guide_line_start.x(), rel_y)
                dist = (rel_pos - self.original_scene_pos).manhattanLength()
                # 2. Если близко к original_scene_pos, используем relative_offset
                if dist <= 20:
                    self.setPos(rel_pos)
                    return
                # 3. Иначе ищем ближайшую точку на линии
                min_dist = float('inf')
                best_t = 0.0
                for i in range(101):
                    t = i / 100.0
                    p = guide_line_path.pointAtPercent(t)
                    d = (QPointF(p) - self.original_scene_pos).manhattanLength()
                    if d < min_dist:
                        min_dist = d
                        best_t = t
                self.relative_offset = best_t
            # Позиция по относительному смещению (после возможного обновления)
            if self.guide.orientation == 'horizontal':
                length = guide_line_end.x() - guide_line_start.x()
                new_x = guide_line_start.x() + self.relative_offset * length
                self.setPos(new_x, guide_line_start.y())
            else:
                length = guide_line_end.y() - guide_line_start.y()
                new_y = guide_line_start.y() + self.relative_offset * length
                self.setPos(guide_line_start.x(), new_y)
        elif self.block:
            # Позиция штриха, привязанного к блоку (в абсолютных координатах)
            rect = self.block.sceneBoundingRect()
            if self.guide.orientation == 'horizontal':
                y = guide_line_start.y()
                x = (rect.left() - TICK_OFFSET) if self.side == 'left' else (rect.right() + TICK_OFFSET)
                self.setPos(x, y)
            else:
                x = guide_line_start.x()
                y = (rect.top() - TICK_OFFSET) if self.side == 'top' else (rect.bottom() + TICK_OFFSET)
                self.setPos(x, y)
        
        # Проверка выхода за пределы линии
        if self.relative_offset is not None:
            if self.guide.orientation == 'horizontal':
                if not (guide_line_start.x() <= self.x() <= guide_line_end.x()):
                    self.guide.remove_tick(self)
            else:
                if not (guide_line_start.y() <= self.y() <= guide_line_end.y()):
                    self.guide.remove_tick(self)

    def boundingRect(self):
        return QRectF(-6, -self.length / 2, 12, self.length) if self.guide.orientation == 'horizontal' else QRectF(-self.length / 2, -6, self.length, 12)

    def paint(self, painter, option, widget=None):
        painter.setPen(QPen(QColor('#222'), 2))
        if self.guide.orientation == 'horizontal':
            painter.drawLine(0, -self.length // 2, 0, self.length // 2)
        else:
            painter.drawLine(-self.length // 2, 0, self.length // 2, 0)
    
    def mouseDoubleClickEvent(self, event):
        # Для custom_ticks сохраняем оригинальную позицию
        if self.block is None and self.relative_offset is not None and self.original_scene_pos is None:
            self.original_scene_pos = self.scenePos()
        self.guide.request_tick_deletion(self)
        event.accept()

    def contextMenuEvent(self, event):
        def delete_tick_action():
            self.guide.request_tick_deletion(self)

        actions = [
            ('Удалить штрих', delete_tick_action)
        ]
        
        view = self.scene().views()[0] if self.scene() and self.scene().views() else None
        menu = GlassMenu(actions, parent=view)
        menu.show_at(event.screenPos())
        event.accept()

class TimelineGuideItem(QGraphicsObject):
    def __init__(self, blocks, scene, view):
        super().__init__()
        self.scene_ref = scene
        self.view_ref = view
        self.associated_items = list(blocks)
        self.orientation = self._determine_orientation()
        self.setZValue(1999)

        self.item_ticks = {}
        self.custom_ticks = []
        self.labels = []
        self.label_buttons = []
        self._shift_active = False
        self._drag_active = False # Для перемещения линии
        
        self.offset = 20
        self.line_path = QPainterPath()
        
        self.setFlags(QGraphicsItem.ItemIsSelectable | QGraphicsItem.ItemIsFocusable)
        self.setAcceptHoverEvents(True)
        self._drag_start_mouse = None
        self._drag_start_offset = 0

        for block in self.associated_items:
            if hasattr(block, 'block_moved'):
                block.block_moved.connect(self.update_line)

        self.update_line()
        self._create_initial_ticks()
        self.setFocus()
    
    def boundingRect(self):
        # Возвращаем область, включающую линию и небольшие поля для удобства
        return self.shape().boundingRect().adjusted(-5, -5, 5, 5)

    def paint(self, painter, option, widget=None):
        pen = QPen(QColor("#333"), 3, Qt.SolidLine)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawPath(self.line_path)

    @property
    def all_ticks(self):
        ticks = list(self.custom_ticks)
        for d in self.item_ticks.values():
            ticks.extend(d.values())
        return ticks

    def _determine_orientation(self):
        if not self.associated_items: return 'horizontal'
        rect = QRectF()
        for item in self.associated_items:
            rect = rect.united(item.sceneBoundingRect())
        return 'horizontal' if rect.width() > rect.height() else 'vertical'

    def _create_initial_ticks(self):
        # Удаляем старые автоматические штрихи (не трогаем custom_ticks)
        for ticks in list(self.item_ticks.values()):
            for tick in ticks.values():
                if tick.scene():
                    self.scene_ref.removeItem(tick)
                tick.deleteLater()
        self.item_ticks.clear()
        # Создаём новые автоматические штрихи только для блоков
        for item in self.associated_items:
            side1 = 'left' if self.orientation == 'horizontal' else 'top'
            side2 = 'right' if self.orientation == 'horizontal' else 'bottom'
            self.item_ticks[item.stage_data['id']] = {
                'start': TickItem(self, block=item, side=side1),
                'end': TickItem(self, block=item, side=side2)
            }

    def on_block_deleted(self, block):
        """Вызывается, когда связанный блок удаляется."""
        if block in self.associated_items:
            try:
                block.block_moved.disconnect(self.update_line)
            except (TypeError, RuntimeError):
                pass # Соединение могло уже не существовать
            self.associated_items.remove(block)

        # Удаляем штрихи и метки, связанные с этим блоком
        if block.stage_data['id'] in self.item_ticks:
            ticks_to_remove = list(self.item_ticks[block.stage_data['id']].values())
            
            # Сначала удаляем все метки, связанные с этими штрихами
            for tick in ticks_to_remove:
                # Находим и удаляем все метки, где этот штрих является tick1 или tick2
                labels_to_remove = [label for label in self.labels if label.tick1 == tick or label.tick2 == tick]
                for label in labels_to_remove:
                    self.remove_label(label)
                
                # Находим и удаляем все кнопки меток, где этот штрих является tick1 или tick2
                buttons_to_remove = [btn for btn in self.label_buttons if btn.tick1 == tick or btn.tick2 == tick]
                for btn in buttons_to_remove:
                    if btn in self.label_buttons:
                        self.label_buttons.remove(btn)
                        if btn.scene():
                            self.scene_ref.removeItem(btn)
                        btn.deleteLater()
                
                # Удаляем сам штрих
                if tick.scene():
                    self.scene_ref.removeItem(tick)
                tick.deleteLater()
            
            del self.item_ticks[block.stage_data['id']]

        if len(self.associated_items) < 2:
            self.destroy()
        else:
            self.update_line()
            self.rebuild_labels()

    def destroy(self):
        """Полностью удаляет временную шкалу и все ее компоненты."""
        # Отписываемся от всех сигналов
        for block in self.associated_items:
            try:
                block.block_moved.disconnect(self.update_line)
            except (TypeError, RuntimeError):
                pass
        
        # Удаляем все дочерние элементы
        for item in self.childItems():
            self.scene_ref.removeItem(item)
            item.deleteLater()
        
        # Очищаем списки
        self.item_ticks.clear()
        self.custom_ticks.clear()
        self.labels.clear()
        self.label_buttons.clear()
        self.associated_items.clear()

        # Удаляем саму линию из виджета и сцены
        if self.view_ref and hasattr(self.view_ref, 'remove_timeline'):
            self.view_ref.remove_timeline(self)
        elif self.scene():
            self.scene().removeItem(self)
        self.deleteLater()

    def update_line(self):
        self.prepareGeometryChange()
        if len(self.associated_items) < 2:
            self.destroy()
            return
        overall_rect = QRectF()
        for item in self.associated_items:
            overall_rect = overall_rect.united(item.sceneBoundingRect())
        
        # Позиция самой направляющей не меняется, меняется только путь ее линии
        self.setPos(0, 0)
        
        if self.orientation == 'horizontal':
            # Y-координата линии зависит от самого верхнего блока и нашего смещения
            line_y = overall_rect.top() - self.offset 
            p1 = QPointF(overall_rect.left() - TICK_OFFSET, line_y)
            p2 = QPointF(overall_rect.right() + TICK_OFFSET, line_y)
        else:
            # X-координата линии зависит от самого левого блока и нашего смещения
            line_x = overall_rect.left() - self.offset
            p1 = QPointF(line_x, overall_rect.top() - TICK_OFFSET)
            p2 = QPointF(line_x, overall_rect.bottom() + TICK_OFFSET)
        
        self.line_path = QPainterPath(p1)
        self.line_path.lineTo(p2)

        for tick in self.all_ticks:
            tick.update_position()
        
        for label in self.labels:
             label.update_position()
        
        self.rebuild_labels()
        self.update()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton and self.shape().contains(event.pos()):
            self._drag_active = True
            self._drag_start_mouse = event.scenePos()
            self._drag_start_offset = self.offset
            event.accept()
        elif event.button() == Qt.RightButton and self.shape().contains(event.pos()):
            # Проверяем, был ли клик на дочернем элементе
            item_at = self.scene().itemAt(event.scenePos(), self.view_ref.transform())
            if item_at == self:
                def delete_guide_action():
                    self.destroy()

                actions = [
                    ('Удалить таймлайн', delete_guide_action)
                ]
                
                view = self.view_ref
                menu = GlassMenu(actions, parent=view)
                menu.show_at(event.screenPos())
                event.accept()
            else:
                # Если клик был на дочернем элементе, передаем ему событие
                super().mousePressEvent(event)
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_active:
            delta = event.scenePos() - self._drag_start_mouse
            if self.orientation == 'horizontal':
                # Инвертируем дельту, т.к. двигаем мышь вверх (y уменьшается), а отступ должен расти
                self.offset = self._drag_start_offset - delta.y()
            else:
                self.offset = self._drag_start_offset - delta.x()
            self.update_line()
            event.accept()
        else:
            super().mouseMoveEvent(event)
    
    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self._drag_active:
            self._drag_active = False
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def mouseDoubleClickEvent(self, event):
        # Проверяем клик по "толстой" форме линии
        if self.shape().contains(event.pos()):
            # Игнорируем клик, если он пришелся на дочерний элемент (штрих или кнопку)
            item_at = None
            for child in self.childItems():
                if child.isVisible() and child.shape().contains(child.mapFromParent(event.pos())):
                    item_at = child
                    break
            
            if item_at:
                super().mouseDoubleClickEvent(event)
                return

            modifiers = QApplication.keyboardModifiers()
            self._shift_active = (modifiers == Qt.ShiftModifier)
            pos = event.pos()
            p1 = self.line_path.pointAtPercent(0)
            p2 = self.line_path.pointAtPercent(1)
            relative_offset = 0.0
            if self.orientation == 'horizontal':
                line_length = p2.x() - p1.x()
                if line_length > 0:
                    relative_offset = (pos.x() - p1.x()) / line_length
            else:
                line_length = p2.y() - p1.y()
                if line_length > 0:
                    relative_offset = (pos.y() - p1.y()) / line_length
            # Передаём оригинальную позицию сцены
            scene_pos = self.mapToScene(pos)
            self.custom_ticks.append(TickItem(self, relative_offset=max(0.0, min(1.0, relative_offset)), original_scene_pos=scene_pos))
            self.rebuild_labels()
        super().mouseDoubleClickEvent(event)
    
    def on_label_button_clicked(self, btn):
        tick1 = btn.tick1
        tick2 = btn.tick2
        
        # Немедленно удаляем ВСЕ кнопки, чтобы избежать артефактов
        self.set_buttons_active(False)

        text, ok = GlassInputDialog.getText(self.view_ref, 'Новая подпись', 'Введите текст:')
        
        if ok and text:
            label = TimelineLabelItem(text, self.orientation, self)
            label.tick1 = tick1
            label.tick2 = tick2
            self.labels.append(label)
            label.update_position()
        
        # После закрытия диалога восстанавливаем кнопки, если Shift все еще нажат
        modifiers = QApplication.keyboardModifiers()
        if modifiers == Qt.ShiftModifier:
            self.set_buttons_active(True)

    def set_buttons_active(self, active):
        self._shift_active = active
        self.rebuild_labels()
        self.update()

    def rebuild_labels(self):
        for btn in self.label_buttons:
            if btn.scene():
                self.scene_ref.removeItem(btn)
            btn.deleteLater()
        self.label_buttons.clear()

        if self._shift_active:
            # Создаем множество пар штрихов, которые уже заняты метками
            occupied_pairs = set()
            for label in self.labels:
                if label.tick1 and label.tick2:
                    occupied_pairs.add(frozenset([label.tick1, label.tick2]))

            key_func = (lambda t: t.pos().x()) if self.orientation == 'horizontal' else (lambda t: t.pos().y())
            sorted_ticks = sorted(self.all_ticks, key=key_func)
            
            for i in range(len(sorted_ticks) - 1):
                tick1 = sorted_ticks[i]
                tick2 = sorted_ticks[i+1]
                
                # Проверяем, не занята ли эта пара штрихов
                if frozenset([tick1, tick2]) not in occupied_pairs:
                    btn = LabelButtonItem(tick1, tick2, self.orientation, self)
                    self.label_buttons.append(btn)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Shift:
            self.set_buttons_active(True)
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key_Shift:
            self.set_buttons_active(False)
        super().keyReleaseEvent(event)

    def contextMenuEvent(self, event):
        # Логика перенесена в mousePressEvent для консистентности
        # и правильной обработки кликов на дочерних элементах
        pass

    def itemChange(self, change, value):
        if change == QGraphicsItem.ItemSelectedChange and value == True:
            if self.scene():
                for item in self.associated_items:
                    if hasattr(item, 'block_moved'):
                        try:
                            item.block_moved.connect(self.update_line)
                        except (TypeError, RuntimeError):
                            pass
            else:
                for item in self.associated_items:
                    if hasattr(item, 'block_moved'):
                        try:
                            item.block_moved.disconnect(self.update_line)
                        except (TypeError, RuntimeError):
                            pass
        return super().itemChange(change, value)

    def _remove_labels_for_tick(self, tick_to_remove):
        for label in list(self.labels):
            if label.tick1 == tick_to_remove or label.tick2 == tick_to_remove:
                if label.scene():
                    self.scene_ref.removeItem(label)
                self.labels.remove(label)

    def request_tick_deletion(self, tick_to_delete):
        if tick_to_delete.relative_offset is not None:
            QTimer.singleShot(0, lambda: self._perform_remove_custom_tick(tick_to_delete))
            return
        if tick_to_delete.block is None or not self.associated_items: return
        if self.orientation == 'horizontal':
            leftmost_block = min(self.associated_items, key=lambda b: b.sceneBoundingRect().left())
            rightmost_block = max(self.associated_items, key=lambda b: b.sceneBoundingRect().right())
            if (tick_to_delete.block == leftmost_block and tick_to_delete.side == 'left') or \
               (tick_to_delete.block == rightmost_block and tick_to_delete.side == 'right'): return
        else:
            topmost_block = min(self.associated_items, key=lambda b: b.sceneBoundingRect().top())
            bottommost_block = max(self.associated_items, key=lambda b: b.sceneBoundingRect().bottom())
            if (tick_to_delete.block == topmost_block and tick_to_delete.side == 'top') or \
               (tick_to_delete.block == bottommost_block and tick_to_delete.side == 'bottom'): return
        QTimer.singleShot(0, lambda: self._perform_remove_block_tick(tick_to_delete))

    def _perform_remove_custom_tick(self, tick):
        self._remove_labels_for_tick(tick)
        self.custom_ticks.remove(tick)
        if tick.scene():
            self.scene_ref.removeItem(tick)
        del tick
        self.rebuild_labels()

    def _perform_remove_block_tick(self, tick):
        block = tick.block
        if not block: return
        block_id = block.stage_data['id']
        if block_id not in self.item_ticks: return
        
        self._remove_labels_for_tick(tick)
        key_to_remove = 'start' if self.item_ticks[block_id].get('start') == tick else ('end' if self.item_ticks[block_id].get('end') == tick else None)
        if key_to_remove:
            del self.item_ticks[block_id][key_to_remove]
        if tick.scene():
            self.scene_ref.removeItem(tick)
        self.rebuild_labels()
        self.update()

    def shape(self):
        path = QPainterPath()
        stroker = QPainterPathStroker()
        stroker.setWidth(20)
        path.addPath(stroker.createStroke(self.line_path))
        for btn in self.label_buttons:
             path.addRect(btn.boundingRect())
        return path

    def remove_label(self, label_to_remove):
        """Удаляет метку и восстанавливает кнопку для ее создания."""
        if label_to_remove in self.labels:
            # Восстанавливаем кнопку для этого сегмента
            if label_to_remove.tick1 and label_to_remove.tick2:
                # Убедимся, что оба штриха еще существуют
                if label_to_remove.tick1.scene() and label_to_remove.tick2.scene():
                     btn = LabelButtonItem(label_to_remove.tick1, label_to_remove.tick2, self.orientation, self)
                     self.label_buttons.append(btn)

            # Удаляем саму метку
            self.labels.remove(label_to_remove)
            if label_to_remove.scene():
                self.scene_ref.removeItem(label_to_remove)
            label_to_remove.deleteLater()

    def add_block(self, block):
        """Добавляет блок в таймлайн, если его там ещё нет, и перестраивает всё необходимое."""
        if block in self.associated_items:
            return
        self.associated_items.append(block)
        if hasattr(block, 'block_moved'):
            block.block_moved.connect(self.update_line)
        self._create_initial_ticks()
        self.update_line()
        self.rebuild_labels()