#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QFileDialog, QMessageBox)
from PyQt5.QtCore import Qt, QTimer

from roadmap_widget import RoadMapWidget
from file_manager import FileManager
from glass_menu import GlassDialog

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

class RoadMapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("RoadMap")
        self.setGeometry(100, 100, 1200, 800)
        self.is_fullscreen = False
        
        self.file_manager = FileManager()
        self.roadmap_widget = RoadMapWidget()
        self.current_file_path = None
        
        self.setup_ui()
        self.setup_connections()
        
        self.autosave_timer = QTimer()
        self.autosave_timer.timeout.connect(self.autosave)
        self.autosave_timer.start(300000)

    def setup_ui(self):
        self.setCentralWidget(self.roadmap_widget)
        
    def setup_connections(self):
        self.roadmap_widget.new_project_requested.connect(self.new_project)
        self.roadmap_widget.open_project_requested.connect(self.open_project)
        self.roadmap_widget.save_project_requested.connect(self.save_project)
        self.roadmap_widget.save_as_project_requested.connect(self.save_project_as)
        self.roadmap_widget.export_png_requested.connect(self.export_to_png)
        
    def new_project(self):
        if self.confirm_action('Новый проект', 'Создать новый проект? Несохраненные изменения будут потеряны.'):
            self.roadmap_widget.clear()
            self.current_file_path = None
            
    def open_project(self):
        file_path, _ = QFileDialog.getOpenFileName(self, 'Открыть проект', '', 'RoadMap файлы (*.rm);;Все файлы (*)')
        if file_path:
            try:
                project_data = self.file_manager.load_project(file_path)
                self.roadmap_widget.load_project(project_data)
                self.current_file_path = file_path
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось загрузить проект: {str(e)}')
                
    def save_project(self):
        if not self.current_file_path:
            self.save_project_as()
        else:
            try:
                project_data = self.roadmap_widget.get_project_data()
                self.file_manager.save_project(self.current_file_path, project_data)
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить проект: {str(e)}')
                
    def save_project_as(self):
        file_path, _ = QFileDialog.getSaveFileName(self, 'Сохранить проект', '', 'RoadMap файлы (*.rm);;Все файлы (*)')
        if file_path:
            if not file_path.endswith('.rm'):
                file_path += '.rm'
            try:
                project_data = self.roadmap_widget.get_project_data()
                self.file_manager.save_project(file_path, project_data)
                self.current_file_path = file_path
            except Exception as e:
                QMessageBox.critical(self, 'Ошибка', f'Не удалось сохранить проект: {str(e)}')
                
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
        if event.key() == Qt.Key_F11:
            if self.is_fullscreen:
                self.showMaximized()
                self.is_fullscreen = False
            else:
                self.showFullScreen()
                self.is_fullscreen = True
        super().keyPressEvent(event)

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