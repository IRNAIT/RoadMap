#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox, QHBoxLayout, QWidget, QSizePolicy, QShortcut)
from PyQt5.QtCore import Qt, QTimer, QObject, QEvent
from PyQt5.QtGui import QKeySequence

import json
import base64
import os
from app_settings import load_settings, save_settings

from roadmap_widget import RoadMapWidget
from file_manager import FileManager
from glass_menu import GlassDialog
from glass_sidebar_menu import GlassSidebarMenu
from search_bar import GlassSearchBar

MESSAGE_BOX_STYLESHEET = """
QMessageBox {
    background-color: rgba(250, 250, 250, 0.98);
    border: 1px solid rgba(200, 200, 200, 0.8);
    border-radius: 10px;
    font-family: Arial, sans-serif;
}
QMessageBox QLabel {
    color: #333;
    font-size: 11pt;
    padding: 10px;
}
QPushButton {
    background-color: #0078D7;
    color: white;
    border: none;
    border-radius: 5px;
    padding: 9px 18px;
    font-size: 10pt;
    font-weight: bold;
    min-width: 80px;
}
QPushButton:hover {
    background-color: #005A9E;
}
QPushButton:pressed {
    background-color: #004578;
}
"""

SETTINGS_PATH = 'settings.json'

class LeftEdgeSensor(QWidget):
    def __init__(self, sidebar_menu, width=20, parent=None):
        super().__init__(parent)
        self.sidebar_menu = sidebar_menu
        self.setFixedWidth(width)
        self.setFixedHeight(3000)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, False)
        self.setStyleSheet('background: rgba(255,0,0,0.7);')
        self.setMouseTracking(True)
        # self.hide()  # УБРАНО!

    def enterEvent(self, event):
        self.sidebar_menu.expand()
        super().enterEvent(event)

class GlobalHotkeyFilter(QObject):
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_F and event.modifiers() & Qt.ShiftModifier:
                search_bar = self.main_window.search_bar
                # Показываем только если не видно или полностью прозрачно
                if not search_bar.isVisible() or search_bar.windowOpacity() < 0.05:
                    search_bar.show_widget()
                return True
            if event.key() == Qt.Key_G and event.modifiers() & Qt.ShiftModifier:
                self.main_window.roadmap_widget.toggle_grid()
                return True
            if event.key() == Qt.Key_Escape:
                search_bar = self.main_window.search_bar
                # Скрываем только если реально видно
                if search_bar.isVisible() and search_bar.windowOpacity() > 0.05:
                    search_bar.hide_widget()
                return True
        return super().eventFilter(obj, event)

class RoadMapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RoadMap")
        self.setGeometry(100, 100, 1200, 800)
        self.is_fullscreen = False
        
        self.file_manager = FileManager()
        self.roadmap_widget = RoadMapWidget()
        self.current_file_path = None
        
        self.main_widget = QWidget()
        self.main_layout = QHBoxLayout(self.main_widget)
        self.roadmap_widget = RoadMapWidget(self)
        self.main_layout.addWidget(self.roadmap_widget)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.setCentralWidget(self.main_widget)
        
        self.sidebar = GlassSidebarMenu(self)
        self.search_bar = GlassSearchBar(self)
        
        self.setup_connections()
        self.setup_hotkeys()
        self.load_settings_on_start()
        self.hotkey_filter = GlobalHotkeyFilter(self)
        QApplication.instance().installEventFilter(self.hotkey_filter)

    def setup_hotkeys(self):
        QShortcut(QKeySequence("Shift+G"), self, self.roadmap_widget.toggle_grid)
        QShortcut(QKeySequence("Shift+F"), self, self.search_bar.show_widget)

    def setup_connections(self):
        self.sidebar.add_stage_button.clicked.connect(self.roadmap_widget.add_new_stage)
        self.sidebar.add_image_stage_button.clicked.connect(self.roadmap_widget.add_new_image_stage)
        self.sidebar.add_txt_stage_button.clicked.connect(self.roadmap_widget.add_new_txt_stage)
        self.sidebar.save_project_requested.connect(self.save_project_as) # Используем save_as для кнопки
        self.sidebar.open_project_requested.connect(self.open_project)
        self.roadmap_widget.save_as_project_requested.connect(self.save_project_as)
        self.roadmap_widget.export_png_requested.connect(self.export_to_png)
        self.search_bar.search_triggered.connect(self.roadmap_widget.search_by_tag)
        
    def load_settings_on_start(self):
        """
        Централизованная загрузка настроек приложения (не проекта).
        На данный момент загружает только аватар.
        """
        if hasattr(self, 'sidebar') and hasattr(self.sidebar, 'avatar'):
            self.sidebar.avatar.load_avatar()

    def new_project(self):
        if self.confirm_action('Новый проект', 'Создать новый проект? Несохраненные изменения будут потеряны.'):
            self.roadmap_widget.clear()
            self.current_file_path = None
            
    def open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Открыть проект', '', 'JSON files (*.json)')
        if file_path:
            self.current_file_path = file_path
            with open(file_path, 'r', encoding='utf-8') as f:
                project_data = json.load(f)
            self.roadmap_widget.load_project(project_data)

    def save_project(self):
        if self.current_file_path:
            project_data = self.roadmap_widget.get_project_data()
            with open(self.current_file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)
        else:
            self.save_project_as()
            
    def save_project_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Сохранить проект как', '', 'JSON files (*.json)')
        if file_path:
            self.current_file_path = file_path
            project_data = self.roadmap_widget.get_project_data()
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(project_data, f, indent=2, ensure_ascii=False)

    def export_to_png(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Экспорт в PNG', '', 'PNG файлы (*.png)')
        if file_path:
            try:
                self.roadmap_widget.export_to_image(file_path, 'PNG')
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось экспортировать: {str(e)}')
                
    def autosave(self):
        if self.current_file_path:
            try:
                project_data = self.roadmap_widget.get_project_data()
                self.file_manager.save_project(self.current_file_path, project_data)
            except Exception:
                pass 
    
    def confirm_action(self, title, text):
        dlg = GlassDialog(text, [('Да', 'yes'), ('Нет', 'no')], parent=self)
        result = dlg.exec_()
        return result == 'yes'

    def closeEvent(self, event):
        dlg = GlassDialog('Сохранить изменения перед выходом?', [('Сохранить', 'yes'), ('Не сохранять', 'no'), ('Отмена', 'cancel')], parent=self)
        result = dlg.exec_()
        if result == 'yes':
            self.save_project()
            event.accept()
        elif result == 'no':
            event.accept()
        else:
            event.ignore()

    def keyPressEvent(self, event):
        if event.modifiers() & Qt.ShiftModifier and event.key() == Qt.Key_G:
            self.roadmap_widget.toggle_grid()
            return
        if event.key() == Qt.Key_F11:
            if self.is_fullscreen:
                self.showMaximized()
                self.is_fullscreen = False
            else:
                self.showFullScreen()
                self.is_fullscreen = True
        super().keyPressEvent(event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.sidebar.update_position()

def main():
    app = QApplication(sys.argv)
    app.setApplicationName('RoadMap')
    app.setApplicationVersion('1.0')
    app.setStyle('Fusion')
    
    window = RoadMapApp()
    window.showMaximized()
    
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()