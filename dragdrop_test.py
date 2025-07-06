import sys
from PyQt5.QtWidgets import QApplication, QGraphicsView, QGraphicsScene, QGraphicsRectItem
from PyQt5.QtCore import Qt, QRectF

class TestView(QGraphicsView):
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.viewport().setFocusPolicy(Qt.StrongFocus)
        self.viewport().dragEnterEvent = self.dragEnterEvent
        self.viewport().dropEvent = self.dropEvent
        self.setWindowTitle('Drag&Drop Test')
        self.setGeometry(200, 200, 400, 300)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.txt'):
                    event.acceptProposedAction()
                    return
        event.ignore()

    def dropEvent(self, event):
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                file_path = url.toLocalFile()
                if file_path.lower().endswith('.txt'):
                    print('Dropped:', file_path)
                    rect = QGraphicsRectItem(QRectF(50, 50, 100, 50))
                    rect.setBrush(Qt.yellow)
                    self.scene().addItem(rect)
                    event.acceptProposedAction()
                    return
        event.ignore()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    view = TestView()
    view.show()
    sys.exit(app.exec_()) 