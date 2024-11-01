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
import threading

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
    return "エラーが発生しまた。"

async def start_local_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=8000)
    server = uvicorn.Server(config)
    await server.serve()

def run_async_server():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(start_local_server())

# 別スレッドでサーバーを起動
server_thread = threading.Thread(target=run_async_server, daemon=True)
server_thread.start()

class YouTubeLoader(QThread):
    finished = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, url):
        super().__init__()
        self.url = url

    @staticmethod
    def extract_video_id(url):
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
            r'(?:embed\/)([0-9A-Za-z_-]{11})',
            r'^([0-9A-Za-z_-]{11})$'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def run(self):
        try:
            video_id = self.extract_video_id(self.url)
            if video_id:
                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1&controls=1&enablejsapi=1"
                self.finished.emit(embed_url)
            else:
                self.error.emit("無効なYouTube URL")
        except Exception as e:
            self.error.emit(str(e))

class PomodoroWorker(QThread):
    tick = pyqtSignal(int)
    finished = pyqtSignal()

    def __init__(self, time_left):
        super().__init__()
        self.time_left = time_left
        self.running = True

    def run(self):
        while self.time_left > 0 and self.running:
            self.tick.emit(self.time_left)
            self.time_left -= 1
            self.msleep(1000)
        if self.running:
            self.finished.emit()

    def stop(self):
        self.running = False

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
        try:
            # WebViewの設定
            self.web_view = QWebEngineView(self)
            
            # 基本的な設定を有効化
            settings = self.web_view.settings()
            settings.setAttribute(QWebEngineSettings.PluginsEnabled, True)
            settings.setAttribute(QWebEngineSettings.JavascriptEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalStorageEnabled, True)
            settings.setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, True)
            settings.setAttribute(QWebEngineSettings.AutoLoadImages, True)
            settings.setAttribute(QWebEngineSettings.WebGLEnabled, True)

            # サイズ設定
            self.web_view.setMinimumSize(400, 300)
            self.layout.addWidget(self.web_view)

        except Exception as e:
            logging.error(f"YouTube プレイヤーの設定中にエラー: {e}")
            raise

    def setup_youtube_controls(self):
        # YouTube URL入力フィールド
        self.youtube_url_input = QtWidgets.QLineEdit()
        self.youtube_url_input.setPlaceholderText("YouTubeのURLを入力してください")
        self.layout.addWidget(self.youtube_url_input)

        # コントロールボタンのレイアウト
        control_layout = QtWidgets.QHBoxLayout()

        # 貼り付けボタン
        self.paste_button = QtWidgets.QPushButton("貼り付け")
        self.paste_button.clicked.connect(self.paste_url)
        control_layout.addWidget(self.paste_button)

        # 読み込みボタン
        self.load_button = QtWidgets.QPushButton("読み込み")
        self.load_button.clicked.connect(self.load_youtube_video)
        control_layout.addWidget(self.load_button)

        self.layout.addLayout(control_layout)

    def load_youtube_video(self):
        try:
            url = self.youtube_url_input.text()
            if url:
                video_id = YouTubeLoader.extract_video_id(url)
                if video_id:
                    html = f'''
                    <html><body style="margin:0">
                        <div id="player"></div>
                        <script src="https://www.youtube.com/iframe_api"></script>
                        <script>
                            var player;
                            function onYouTubeIframeAPIReady() {{
                                player = new YT.Player('player', {{
                                    height: '100%',
                                    width: '100%',
                                    videoId: '{video_id}',
                                    playerVars: {{
                                        'autoplay': 1,
                                        'controls': 1
                                    }},
                                    events: {{
                                        'onReady': onPlayerReady
                                    }}
                                }});
                            }}
                            function onPlayerReady(event) {{
                                event.target.playVideo();
                            }}
                        </script>
                    </body></html>
                    '''
                    self.web_view.setHtml(html)
                else:
                    QtWidgets.QMessageBox.warning(self, "エラー", "無効なYouTube URLです")
        except Exception as e:
            logging.error(f"動画の読み込み中にエラー: {e}")
            QtWidgets.QMessageBox.warning(self, "エラー", f"動画の読み込みに失敗: {e}")

    def paste_url(self):
        clipboard = QtWidgets.QApplication.clipboard()
        self.youtube_url_input.setText(clipboard.text())

    def check_video_status(self):
        # 動画の状態を確認するJavaScriptを修正
        self.web_view.page().runJavaScript("""
            (function() {
                var video = document.querySelector('video');
                if (video) {
                    return {
                        'ended': video.ended,
                        'currentTime': video.currentTime,
                        'duration': video.duration
                    };
                }
                return null;
            })();
        """, self.handle_video_status)

    def handle_video_status(self, result):
        if result:
            logging.info(f"Video status: {result}")

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
            # Client ID入力用のダイアログを作成
            client_id, ok = QtWidgets.QInputDialog.getText(
                self,
                "Notion連携",
                "Notion Client IDを入力してください：",
                QtWidgets.QLineEdit.Normal
            )
            
            if ok and client_id:
                redirect_uri = "http://localhost:8000/notion/callback"
                auth_url = f"https://api.notion.com/v1/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code"
                webbrowser.open(auth_url)
            else:
                QtWidgets.QMessageBox.warning(self, "警告", "Client IDが入力されていません。")
            
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
        # プロファイルとリソースの適切なクリーンアップ
        try:
            self.stop_timer()
            if hasattr(self, 'video_check_timer'):
                self.video_check_timer.stop()
            
            # WebEngineViewのクリーンアップ
            if hasattr(self, 'web_view'):
                self.web_view.page().deleteLater()
                self.web_view.deleteLater()
                self.web_view = None
            
            # プロファイルのクリーンアップ
            if hasattr(self, 'profile'):
                self.profile.deleteLater()
                self.profile = None
                
        except Exception as e:
            logging.error(f"クリーンアップ中にエラーが発生: {e}")
        finally:
            super().closeEvent(event)

if __name__ == '__main__':
    try:
        app = QtWidgets.QApplication(sys.argv)
        timer = PomodoroTimer()
        timer.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.critical(f"アプリケーションの実行中にエラーが発生しました: {e}")
        QtWidgets.QMessageBox.critical(None, "致命的なエラー", f"アプリケーションの実行中にエラーが発生しました: {e}")
        sys.exit(1)
