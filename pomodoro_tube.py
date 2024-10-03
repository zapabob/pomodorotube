import sys
from PyQt5 import QtWidgets, QtCore, QtGui
import datetime
import pytz
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl
import winsound

class PomodoroTimer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('ポモドーロタイマー')
        self.setGeometry(100, 100, 400, 500)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_timer)
        self.time_left = 1500  # 25分
        self.pomodoro_count = 0
        self.is_break = False
        self.is_looping = False  # ループ再生の状態を追跡

        self.setup_ui()
        self.setup_youtube_player()
        self.setup_timers()

    def setup_ui(self):
        self.layout = QtWidgets.QVBoxLayout()

        # タイマー表示
        self.label = QtWidgets.QLabel(self.format_time(self.time_left))
        self.label.setStyleSheet("font-size: 48px;")
        self.layout.addWidget(self.label)

        # 現在時刻表示
        self.current_time_label = QtWidgets.QLabel()
        self.current_time_label.setStyleSheet("font-size: 24px;")
        self.layout.addWidget(self.current_time_label)

        # コントロールボタン
        self.start_button = QtWidgets.QPushButton('スタート')
        self.start_button.clicked.connect(self.start_timer)
        self.layout.addWidget(self.start_button)

        self.stop_button = QtWidgets.QPushButton('ストップ')
        self.stop_button.clicked.connect(self.stop_timer)
        self.layout.addWidget(self.stop_button)

        self.reset_button = QtWidgets.QPushButton('リセット')
        self.reset_button.clicked.connect(self.reset_timer)
        self.layout.addWidget(self.reset_button)

        # YouTube URL入力
        self.url_layout = QtWidgets.QHBoxLayout()
        self.url_input = QtWidgets.QLineEdit()
        self.url_input.setPlaceholderText("YouTube URLを入力してください")
        self.url_layout.addWidget(self.url_input)

        self.paste_button = QtWidgets.QPushButton('貼り付け')
        self.paste_button.clicked.connect(self.paste_url)
        self.url_layout.addWidget(self.paste_button)

        self.clear_button = QtWidgets.QPushButton('クリア')
        self.clear_button.clicked.connect(self.clear_url)
        self.url_layout.addWidget(self.clear_button)

        self.load_button = QtWidgets.QPushButton('読み込み')
        self.load_button.clicked.connect(self.load_video)
        self.url_layout.addWidget(self.load_button)

        self.layout.addLayout(self.url_layout)

        self.setLayout(self.layout)

    def setup_youtube_player(self):
        self.web_view = QWebEngineView()
        self.web_view.setUrl(QUrl("https://www.youtube.com/embed/jfKfPfyJRdk?autoplay=1&mute=1&loop=1&playlist=jfKfPfyJRdk"))
        self.web_view.setFixedSize(400, 225)  # 16:9のアスペクト比
        self.layout.addWidget(self.web_view)

        # 動画コントロール
        self.repeat_button = QtWidgets.QPushButton('ループ再生')
        self.repeat_button.setCheckable(True)
        self.repeat_button.clicked.connect(self.toggle_repeat)
        self.layout.addWidget(self.repeat_button)

        self.next_button = QtWidgets.QPushButton('次へ')
        self.next_button.clicked.connect(self.next_video)
        self.layout.addWidget(self.next_button)

    def setup_timers(self):
        # 現在時刻を更新するタイマー
        self.time_update_timer = QtCore.QTimer()
        self.time_update_timer.timeout.connect(self.update_current_time)
        self.time_update_timer.start(1000)  # 1秒ごとに更新
        self.update_current_time()  # 初期表示

        # サウンド設定
        self.work_sound = 'SystemHand'  # 作業開始時のサウンド
        self.break_sound = 'SystemAsterisk'  # 休憩開始時のサウンド

    def format_time(self, seconds):
        minutes, seconds = divmod(seconds, 60)
        return f"{minutes:02}:{seconds:02}"

    def update_timer(self):
        if self.time_left > 0:
            self.time_left -= 1
            self.label.setText(self.format_time(self.time_left))
        else:
            self.timer.stop()
            if not self.is_break:
                self.pomodoro_count += 1
                if self.pomodoro_count % 4 == 0:
                    self.time_left = 900  # 15分の長休憩
                    self.label.setText("長休憩開始！")
                else:
                    self.time_left = 300  # 5分の短休憩
                    self.label.setText("短休憩開始！")
                self.is_break = True
                winsound.PlaySound(self.break_sound, winsound.SND_ALIAS)
            else:
                self.time_left = 1500  # 25分の作業時間
                self.label.setText("作業開始！")
                self.is_break = False
                winsound.PlaySound(self.work_sound, winsound.SND_ALIAS)
            self.start_timer()

    def start_timer(self):
        self.timer.start(1000)  # 1秒ごとに更新
        self.web_view.page().runJavaScript("document.getElementsByTagName('video')[0].play();")
        if not self.is_break:
            winsound.PlaySound(self.work_sound, winsound.SND_ALIAS)

    def stop_timer(self):
        self.timer.stop()
        self.web_view.page().runJavaScript("document.getElementsByTagName('video')[0].pause();")

    def reset_timer(self):
        self.time_left = 1500  # 25分にリセット
        self.label.setText(self.format_time(self.time_left))
        self.web_view.page().runJavaScript("document.getElementsByTagName('video')[0].currentTime = 0;")
        self.pomodoro_count = 0
        self.is_break = False

    def update_current_time(self):
        jst = pytz.timezone('Asia/Tokyo')
        current_time = datetime.datetime.now(jst).strftime('%Y-%m-%d %H:%M:%S')
        self.current_time_label.setText(f"現在時刻: {current_time}")

    def paste_url(self):
        clipboard = QtWidgets.QApplication.clipboard()
        self.url_input.setText(clipboard.text())

    def clear_url(self):
        self.url_input.clear()

    def load_video(self):
        url = self.url_input.text()
        if "youtube.com" in url or "youtu.be" in url:
            video_id = self.extract_video_id(url)
            if video_id:
                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1&mute=1&loop=1&playlist={video_id}"
                self.web_view.setUrl(QUrl(embed_url))
                self.is_looping = True
                self.repeat_button.setChecked(True)
            else:
                QtWidgets.QMessageBox.warning(self, "エラー", "無効なYouTube URLです。")
        else:
            QtWidgets.QMessageBox.warning(self, "エラー", "YouTube URLを入力してください。")

    def extract_video_id(self, url):
        if "youtube.com/watch?v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1]
        return None

    def toggle_repeat(self):
        self.is_looping = self.repeat_button.isChecked()
        video_id = self.extract_video_id(self.web_view.url().toString())
        if video_id:
            if self.is_looping:
                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1&mute=1&loop=1&playlist={video_id}"
            else:
                embed_url = f"https://www.youtube.com/embed/{video_id}?autoplay=1&mute=1"
            self.web_view.setUrl(QUrl(embed_url))

    def next_video(self):
        # この機能は実装されていません。YouTubeプレイリストを使用する場合に実装可能です。
        pass

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    timer = PomodoroTimer()
    timer.show()
    sys.exit(app.exec_())