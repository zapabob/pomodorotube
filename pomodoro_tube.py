# -*- coding: utf-8 -*-
import sys
from PyQt5 import QtWidgets, QtCore, QtGui
from PyQt5.QtWebEngineWidgets import QWebEngineView, QWebEngineSettings, QWebEngineProfile, QWebEnginePage
from PyQt5.QtCore import QUrl, QThread, pyqtSignal, QTimer
from PyQt5.QtGui import QPainter, QPainterPath, QColor, QFont
import datetime
import pytz
import winsound
import json
import requests
import os
import webbrowser
from urllib.parse import urlencode
from notion_client import AsyncClient
import asyncio
import ctypes
from fastapi import FastAPI, HTTPException
import uvicorn
import aiofiles
import logging
import re

# ロギングの設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

myappid = 'Pomodoro_tube v1.1.0'
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)

app = FastAPI()

@app.get("/notion/callback")
async def handle_callback(code: str = None):
    if code:
        # コードを使って認証処理を行う
        return "認証が完了しました。このページを閉じてアプリに戻ってください。"
    return "エラーが発生しました。"

async def start_local_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

# メインアプリケーションのコード内で呼び出す
asyncio.ensure_future(start_local_server())

class YouTubeLoader(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    def run(self):
        try:
            video_id = self.extract_video_id(self.url)
            if video_id:
                embed_url = f"https://www.youtube.com/embed/{video_id}"
                self.finished.emit(embed_url)
            else:
                self.error.emit("無効なYouTube URLです")
        except Exception as e:
            self.error.emit(str(e))

    @staticmethod
    def extract_video_id(url):
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return match.group(1) if match else None

class PomodoroWorker(QThread):
    tick = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, duration):
        super().__init__()
        self.duration = duration
        self.is_running = True

    def run(self):
        while self.duration > 0 and self.is_running:
            self.tick.emit(self.duration)
            self.msleep(1000)  # 1秒待機
            self.duration -= 1
        self.finished.emit()

    def stop(self):
        self.is_running = False

class CircularProgressBar(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.value = 0
        self.width = 200
        self.height = 200
        self.progress_width = 10
        self.progress_color = QColor(0, 255, 0)
        self.max_value = 100
        self.font_size = 12
        self.suffix = "%"
        self.text_color = QColor(0, 0, 0)
        self.setFixedSize(self.width, self.height)

    def set_value(self, value):
        self.value = value
        self.update()

    def paintEvent(self, event):
        width = self.width - self.progress_width
        height = self.height - self.progress_width
        value = self.value * 360

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.translate(self.width / 2, self.height / 2)
        painter.rotate(270)

        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QBrush(self.progress_color))
        path = QPainterPath()
        path.arcMoveTo(-width / 2, -height / 2, width, height, 0)
        path.arcTo(-width / 2, -height / 2, width, height, 0, -value)
        painter.drawPath(path)

        painter.setPen(QtGui.QPen(self.text_color))
        painter.setFont(QFont('Segoe UI', self.font_size))
        painter.rotate(-270)
        painter.drawText(QtCore.QRect(-50, -50, 100, 100), QtCore.Qt.AlignCenter, f"{int(self.value * 100)}{self.suffix}")

class PomodoroTimer(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setup_ui()
        self.setup_timers()
        self.load_settings()

    def setup_ui(self):
        self.setWindowTitle('Pomodoro Timer')
        self.setGeometry(100, 100, 600, 400)

        self.layout = QtWidgets.QVBoxLayout()
        
        self.setup_timer_display()
        self.setup_task_list()
        self.setup_buttons()
        self.setup_youtube_player()
        self.setup_youtube_controls()

        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        central_widget.setLayout(self.layout)

    def setup_timer_display(self):
        self.label = QtWidgets.QLabel('25:00')
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setStyleSheet("font-size: 72px;")
        self.layout.addWidget(self.label)

        self.progress_bar = QtWidgets.QProgressBar()
        self.layout.addWidget(self.progress_bar)

        self.current_time_label = QtWidgets.QLabel()
        self.layout.addWidget(self.current_time_label)

    def setup_task_list(self):
        self.task_input = QtWidgets.QLineEdit()
        self.task_input.setPlaceholderText("タスクを入力してください")
        self.layout.addWidget(self.task_input)

        self.add_task_button = QtWidgets.QPushButton('タスクを追加')
        self.add_task_button.clicked.connect(self.add_task)
        self.layout.addWidget(self.add_task_button)

        self.task_list = QtWidgets.QListWidget()
        self.layout.addWidget(self.task_list)

    def setup_buttons(self):
        self.button_layout = QtWidgets.QHBoxLayout()

        self.start_button = QtWidgets.QPushButton('開始')
        self.start_button.clicked.connect(self.start_timer)
        self.button_layout.addWidget(self.start_button)

        self.stop_button = QtWidgets.QPushButton('ストップ')
        self.stop_button.clicked.connect(self.stop_timer)
        self.button_layout.addWidget(self.stop_button)

        self.reset_button = QtWidgets.QPushButton('リセット')
        self.reset_button.clicked.connect(self.reset_timer)
        self.button_layout.addWidget(self.reset_button)

        self.layout.addLayout(self.button_layout)

        self.notion_button = QtWidgets.QPushButton('Notionと連携')
        self.notion_button.clicked.connect(self.connect_to_notion)
        self.layout.addWidget(self.notion_button)

    def setup_youtube_player(self):
        # カスタムプロファイルを作成
        self.profile = QWebEngineProfile("YouTubeProfile")
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.ForcePersistentCookies)
        self.profile.setPersistentStoragePath("./youtube_data")  # 永続的なストレージパスを設定

        # WebViewの設定
        self.web_view = QWebEngineView()
        page = QWebEnginePage(self.profile, self.web_view)
        self.web_view.setPage(page)

        # 必要な設定を有効化
        settings = self.web_view.settings()
        settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
        settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
        settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)

        # YouTubeのURLを設定（ここではホームページを表示）
        youtube_url = "https://www.youtube.com"
        self.web_view.setUrl(QUrl(youtube_url))

        self.layout.addWidget(self.web_view)

    def setup_youtube_controls(self):
        self.youtube_url_input = QtWidgets.QLineEdit()
        self.youtube_url_input.setPlaceholderText("YouTubeのURLを入力してください")
        self.layout.addWidget(self.youtube_url_input)

        button_layout = QtWidgets.QHBoxLayout()

        self.paste_button = QtWidgets.QPushButton("貼り付け")
        self.paste_button.clicked.connect(self.paste_url)
        button_layout.addWidget(self.paste_button)

        self.clear_button = QtWidgets.QPushButton("クリア")
        self.clear_button.clicked.connect(self.clear_url)
        button_layout.addWidget(self.clear_button)

        self.load_button = QtWidgets.QPushButton("読み込み")
        self.load_button.clicked.connect(self.load_youtube_video)
        button_layout.addWidget(self.load_button)

        self.loop_button = QtWidgets.QPushButton("ループ再生")
        self.loop_button.setCheckable(True)
        self.loop_button.clicked.connect(self.toggle_loop)
        button_layout.addWidget(self.loop_button)

        self.layout.addLayout(button_layout)

    def setup_timers(self):
        self.time_update_timer = QTimer()
        self.time_update_timer.timeout.connect(self.update_current_time)
        self.time_update_timer.start(1000)
        self.update_current_time()

        self.work_sound = 'SystemHand'
        self.break_sound = 'SystemAsterisk'

        self.pomodoro_worker = None
        self.time_left = 1500
        self.pomodoro_count = 0
        self.is_break = False
        self.tasks = []

    def start_timer(self):
        if self.pomodoro_worker is None or not self.pomodoro_worker.isRunning():
            self.pomodoro_worker = PomodoroWorker(self.time_left)
            self.pomodoro_worker.tick.connect(self.update_timer_display)
            self.pomodoro_worker.finished.connect(self.on_timer_finished)
            self.pomodoro_worker.start()
            self.start_button.setText("停止")
        else:
            self.stop_timer()

    def stop_timer(self):
        if self.pomodoro_worker:
            self.pomodoro_worker.stop()
            self.pomodoro_worker = None
        self.start_button.setText("開始")
        self.web_view.page().runJavaScript("document.getElementsByTagName('video')[0].pause();")

    def reset_timer(self):
        self.stop_timer()
        self.time_left = 1500
        self.update_timer_display(self.time_left)
        self.web_view.page().runJavaScript("document.getElementsByTagName('video')[0].currentTime = 0;")
        self.pomodoro_count = 0
        self.is_break = False

    def update_timer_display(self, time_left):
        self.time_left = time_left
        self.label.setText(self.format_time(self.time_left))
        self.progress_bar.setValue(int((1 - (self.time_left / 1500)) * 100))

    def on_timer_finished(self):
        self.start_button.setText("開始")
        self.pomodoro_count += 1
        self.play_sound()
        self.switch_mode()

    def switch_mode(self):
        if not self.is_break:
            if self.pomodoro_count % 4 == 0:
                self.time_left = 900  # 15分の長休憩
                self.label.setText("長休憩開始！")
            else:
                self.time_left = 300  # 5分の短休憩
                self.label.setText("短休憩開始！")
            self.is_break = True
        else:
            self.time_left = 1500  # 25分の作業時間
            self.label.setText("作業開始！")
            self.is_break = False
        self.start_timer()

    def play_sound(self):
        sound = self.break_sound if self.is_break else self.work_sound
        try:
            winsound.PlaySound(sound, winsound.SND_ALIAS)
        except Exception as e:
            logging.error(f"サウンド再生エラー: {e}")

    def format_time(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02}:{seconds:02}"

    def update_current_time(self):
        try:
            jst = pytz.timezone('Asia/Tokyo')
            current_time = datetime.datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
            self.current_time_label.setText(f"日本標準時: {current_time}")
        except Exception as e:
            logging.error(f"時刻更新エラー: {e}")

    def add_task(self):
        task = self.task_input.text()
        if task and len(self.tasks) < 5:
            self.tasks.append(task)
            self.task_list.addItem(task)
            self.task_input.clear()
        elif len(self.tasks) >= 5:
            QtWidgets.QMessageBox.warning(self, "警告", "タスクは最大5つまでです。")

    def connect_to_notion(self):
        try:
            client_id = "あなたのNotion Client ID"
            redirect_uri = "http://localhost:8000/notion/callback"
            auth_url = f"https://api.notion.com/v1/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
            webbrowser.open(auth_url)
        except Exception as e:
            logging.error(f"Notionへの接続に失敗しました: {e}")
            QtWidgets.QMessageBox.warning(self, "エラー", f"Notionへの接続に失敗しました: {e}")

    def load_settings(self):
        if not os.path.exists('settings.json'):
            # デフォルト設定を作成
            default_settings = {
                "setting1": "default_value1",
                "setting2": "default_value2"
            }
            with open('settings.json', 'w') as f:
                json.dump(default_settings, f)
            print("デフォルト設定ファイルを作成しました。")
        
        with open('settings.json', 'r') as f:
            settings = json.load(f)
        self.notion_token = settings.get("notion_token", "")
        self.notion_database_id = settings.get("notion_database_id", "")
        logging.info("設定を読み込みました")

    async def save_settings(self):
        settings = {
            "notion_token": self.notion_token,
            "notion_database_id": self.notion_database_id,
        }
        try:
            async with aiofiles.open("settings.json", mode="w") as f:
                await f.write(json.dumps(settings, indent=4))
            logging.info("設定を保存しました")
        except IOError as e:
            logging.error(f"設定の保存に失敗しました: {e}")
            raise HTTPException(status_code=500, detail=f"設定の保存に失敗しました: {e}")

    def closeEvent(self, event):
        self.stop_timer()
        super().closeEvent(event)

    def paste_url(self):
        clipboard = QtWidgets.QApplication.clipboard()
        self.youtube_url_input.setText(clipboard.text())

    def clear_url(self):
        self.youtube_url_input.clear()

    def load_youtube_video(self):
        url = self.youtube_url_input.text()
        if url:
            # 動画IDを抽出
            video_id = self.extract_video_id(url)
            if video_id:
                embed_url = f"https://www.youtube.com/embed/{video_id}"
                self.web_view.setUrl(QUrl(embed_url))
            else:
                QtWidgets.QMessageBox.warning(self, "エラー", "無効なYouTube URLです")

    @staticmethod
    def extract_video_id(url):
        import re
        match = re.search(r"(?:v=|\/)([0-9A-Za-z_-]{11}).*", url)
        return match.group(1) if match else None

    def toggle_loop(self):
        is_looping = self.loop_button.isChecked()
        self.web_view.page().runJavaScript(f"document.getElementsByTagName('video')[0].loop = {str(is_looping).lower()};")

if __name__ == '__main__':
    try:
        app = QtWidgets.QApplication(sys.argv)
        timer = PomodoroTimer()
        timer.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.critical(f"アプリケーションの実行中に致命的なエラーが発生しました: {e}")
        QtWidgets.QMessageBox.critical(None, "致命的なエラー", f"アプリケーションの実行中にエラーが発生しました: {e}")
        sys.exit(1)
