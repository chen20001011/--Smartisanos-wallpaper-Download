import sys
import os
import requests
import json
from io import BytesIO
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QComboBox, QLineEdit, QFileDialog, QMessageBox, QScrollArea
)
from PyQt5.QtGui import QPixmap, QImage, QIcon
from PyQt5.QtCore import Qt, QUrl, QThread, pyqtSignal

# --- Constants ---
API_URL = "http://wallpaper-api.smartisan.com/app/index.php?r=paperapi/index/list&client_version=2&source={source}&limit=20&paper_id=0"
SOURCES = [
    "Artand", "Smartisan", "Unsplash", "Minimography", "Pexels",
    "Magdeleine", "Fancycrave", "Snapwiresnaps", "Memento",
    "纹理与材质壁纸", "壁纸摄影大赛精选"
]

# --- Worker Thread for Image Download ---
class ImageDownloader(QThread):
    finished = pyqtSignal(int, QPixmap) # index, pixmap
    error = pyqtSignal(int, str) # index, error_message

    def __init__(self, index, url):
        super().__init__()
        self.index = index
        self.url = url

    def run(self):
        try:
            response = requests.get(self.url, timeout=10)
            response.raise_for_status()
            image = QImage.fromData(response.content)
            if image.isNull():
                self.error.emit(self.index, "Invalid image data")
                return
            pixmap = QPixmap.fromImage(image)
            self.finished.emit(self.index, pixmap)
        except requests.exceptions.RequestException as e:
            self.error.emit(self.index, str(e))
        except Exception as e:
            self.error.emit(self.index, f"An unexpected error occurred: {e}")

# --- Main Application Window ---
class WallpaperDownloaderApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SmartisanOS 壁纸下载器 (Python 版)")
        self.setWindowIcon(QIcon(self.resource_path("hyw.ico")))
        self.setGeometry(100, 100, 1300, 800)
        self.setMinimumSize(1300, 800)

        self.current_page = 0
        self.wallpaper_data = []
        self.image_threads = []
        self.download_path = os.path.join(os.path.expanduser("~"), "SmartisanOS_Wallpapers")
        os.makedirs(self.download_path, exist_ok=True)

        self.init_ui()
        self.load_wallpapers()

    def resource_path(self, relative_path):
        """ Get absolute path to resource, works for dev and for PyInstaller """
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")

        return os.path.join(base_path, relative_path)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)

        # --- Left Panel (Wallpapers) ---
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        main_layout.addWidget(left_panel, 10)

        # Top controls (Sort, Page)
        top_controls_layout = QHBoxLayout()
        self.sort_combo = QComboBox()
        self.sort_combo.addItems(SOURCES)
        self.sort_combo.currentTextChanged.connect(self.sort_changed)
        self.page_label = QLabel(f"第 {self.current_page + 1} 页")
        self.first_page_btn = QPushButton("首页")
        self.first_page_btn.clicked.connect(lambda: self.change_page(0))
        self.prev_page_btn = QPushButton("上一页")
        self.prev_page_btn.clicked.connect(lambda: self.change_page(self.current_page - 1))
        self.next_page_btn = QPushButton("下一页")
        self.next_page_btn.clicked.connect(lambda: self.change_page(self.current_page + 1))

        top_controls_layout.addWidget(self.sort_combo)
        top_controls_layout.addWidget(self.page_label)
        top_controls_layout.addWidget(self.first_page_btn)
        top_controls_layout.addWidget(self.prev_page_btn)
        top_controls_layout.addWidget(self.next_page_btn)
        left_layout.addLayout(top_controls_layout)

        # Wallpaper preview area
        self.preview_layout = QHBoxLayout()
        self.pic_labels = [QLabel(), QLabel(), QLabel()]
        for label in self.pic_labels:
            label.setAlignment(Qt.AlignCenter)
            label.setFixedSize(300, 300)
            self.preview_layout.addWidget(label)
        left_layout.addLayout(self.preview_layout)

        # --- Right Panel (Info and Download) ---
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        main_layout.addWidget(right_panel, 1)

        self.name_label = QLabel("名称: ")
        self.author_label = QLabel("作者: ")
        self.source_label = QLabel("来源: ")
        self.desc_label = QLabel("描述: ")

        right_layout.addStretch(1)
        right_layout.addWidget(self.name_label)
        right_layout.addWidget(self.author_label)
        right_layout.addWidget(self.source_label)
        right_layout.addWidget(self.desc_label)

        # Download path
        download_path_layout = QHBoxLayout()
        self.location_edit = QLineEdit(self.download_path)
        self.location_edit.setReadOnly(True)
        self.choose_location_btn = QPushButton("选择路径")
        self.choose_location_btn.clicked.connect(self.choose_download_path)
        download_path_layout.addWidget(QLabel("下载位置:"))
        download_path_layout.addWidget(self.location_edit)
        download_path_layout.addWidget(self.choose_location_btn)
        right_layout.addLayout(download_path_layout)

        # Download button
        self.download_btn = QPushButton("下载当前页壁纸 (3张)")
        self.download_btn.setFixedSize(200, 50)
        self.download_btn.clicked.connect(self.start_download)
        right_layout.addWidget(self.download_btn, 0, Qt.AlignCenter)
        right_layout.addStretch(1)

        # Smartisan Logo (Placeholder)
        smartisan_logo = QLabel("SmartisanOS")
        smartisan_logo.setAlignment(Qt.AlignHCenter)
        right_layout.addWidget(smartisan_logo)

    def sort_changed(self, text):
        self.current_page = 0
        self.load_wallpapers()

    def change_page(self, new_page):
        if new_page < 0:
            QMessageBox.warning(self, "提示", "已经是第一页了！")
            return
        
        # Check if we have enough data for the next page
        if new_page * 3 >= len(self.wallpaper_data) and len(self.wallpaper_data) > 0:
            QMessageBox.warning(self, "提示", "没有更多壁纸了！")
            return

        self.current_page = new_page
        self.update_ui()

    def load_wallpapers(self):
        source = self.sort_combo.currentText()
        url = API_URL.format(source=source)
        
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if data.get('code') == 0 and 'data' in data:
                self.wallpaper_data = data['data']
                self.update_ui()
            else:
                QMessageBox.critical(self, "错误", f"API返回错误: {data.get('msg', '未知错误')}")
                self.wallpaper_data = []
                self.update_ui(clear=True)
                
        except requests.exceptions.RequestException as e:
            QMessageBox.critical(self, "网络错误", f"无法连接到壁纸API: {e}")
            self.wallpaper_data = []
            self.update_ui(clear=True)
        except json.JSONDecodeError:
            QMessageBox.critical(self, "数据错误", "API返回了无效的JSON数据。")
            self.wallpaper_data = []
            self.update_ui(clear=True)

    def update_ui(self, clear=False):
        self.page_label.setText(f"第 {self.current_page + 1} 页")
        
        # Clear previous images
        for label in self.pic_labels:
            label.clear()
            label.setText("加载中...")

        if clear or not self.wallpaper_data:
            self.name_label.setText("名称: ")
            self.author_label.setText("作者: ")
            self.source_label.setText("来源: ")
            self.desc_label.setText("描述: ")
            for label in self.pic_labels:
                label.setText("无数据")
            return

        start_index = self.current_page * 3
        
        # Update info for the first wallpaper on the page
        if start_index < len(self.wallpaper_data):
            first_wallpaper = self.wallpaper_data[start_index]
            self.name_label.setText(f"名称: {first_wallpaper.get('id', 'N/A')}")
            self.author_label.setText(f"作者: {first_wallpaper.get('author', 'N/A')}")
            self.source_label.setText(f"来源: {self.sort_combo.currentText()}")
            self.desc_label.setText(f"描述: {first_wallpaper.get('desc', 'N/A')}")
        else:
            self.name_label.setText("名称: ")
            self.author_label.setText("作者: ")
            self.source_label.setText("来源: ")
            self.desc_label.setText("描述: ")

        # Load images for the three slots
        for i in range(3):
            data_index = start_index + i
            if data_index < len(self.wallpaper_data):
                url = self.wallpaper_data[data_index].get('url')
                if url:
                    self.pic_labels[i].setText("加载中...")
                    downloader = ImageDownloader(i, url)
                    downloader.finished.connect(self.image_loaded)
                    downloader.error.connect(self.image_error)
                    self.image_threads.append(downloader)
                    downloader.start()
                else:
                    self.pic_labels[i].setText("URL无效")
            else:
                self.pic_labels[i].setText("无壁纸")

    def image_loaded(self, index, pixmap):
        if index < len(self.pic_labels):
            scaled_pixmap = pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.pic_labels[index].setPixmap(scaled_pixmap)
        
        # Clean up the finished thread
        for thread in self.image_threads:
            if not thread.isRunning():
                self.image_threads.remove(thread)
                thread.deleteLater()
                break

    def image_error(self, index, error_message):
        if index < len(self.pic_labels):
            self.pic_labels[index].setText(f"加载失败: {error_message[:20]}...")
        
        # Clean up the finished thread
        for thread in self.image_threads:
            if not thread.isRunning():
                self.image_threads.remove(thread)
                thread.deleteLater()
                break

    def choose_download_path(self):
        new_path = QFileDialog.getExistingDirectory(self, "选择下载路径", self.download_path)
        if new_path:
            self.download_path = new_path
            self.location_edit.setText(self.download_path)

    def start_download(self):
        if not self.wallpaper_data:
            QMessageBox.warning(self, "警告", "当前没有可下载的壁纸数据。")
            return

        start_index = self.current_page * 3
        download_count = 0
        
        for i in range(3):
            data_index = start_index + i
            if data_index < len(self.wallpaper_data):
                wallpaper = self.wallpaper_data[data_index]
                url = wallpaper.get('url')
                wallpaper_id = wallpaper.get('id')
                
                if url and wallpaper_id:
                    filename = os.path.join(self.download_path, f"{wallpaper_id}.jpg")
                    try:
                        response = requests.get(url, timeout=20)
                        response.raise_for_status()
                        with open(filename, 'wb') as f:
                            f.write(response.content)
                        download_count += 1
                    except requests.exceptions.RequestException as e:
                        print(f"下载 {wallpaper_id} 失败: {e}")
        
        if download_count > 0:
            QMessageBox.information(self, "下载完成", f"成功下载 {download_count} 张壁纸到:\n{self.download_path}")
        else:
            QMessageBox.warning(self, "下载失败", "没有壁纸被成功下载，请检查网络连接或下载路径。")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # Create a dummy icon file for PyInstaller to bundle
    # In a real scenario, this would be a proper icon file
    try:
        with open("hyw.ico", "w") as f:
            f.write("")
    except:
        pass
    
    ex = WallpaperDownloaderApp()
    ex.show()
    sys.exit(app.exec_())
