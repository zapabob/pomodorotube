import tkinter as tk
from tkinter import ttk, messagebox
import logging
import re
import time
import threading
from typing import Optional
from pytube import YouTube
from datetime import datetime, timedelta, timezone
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
import pyperclip
import winsound

# ロギングの設定
logging.basicConfig(
    filename='pomodoro.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TimerError(Exception):
    """タイマー関連のカスタムエラー"""
    pass

class Timer:
    def __init__(self, duration: int = 25 * 60):
        self.duration = duration
        self.start_time: Optional[float] = None
        self.is_active: bool = False
        self.pause_time: Optional[float] = None
        self.total_pause_time: float = 0
        self.sync_with_video: bool = False
        self.pomodoro_count: int = 0
        self.is_break: bool = False

    def start(self):
        if self.is_active:
            raise TimerError("タイマーは既に動作中です")
        self.start_time = time.time()
        self.is_active = True
        self.total_pause_time = 0

    def stop(self):
        if not self.is_active:
            raise TimerError("タイマーは動作していません")
        self.is_active = False
        self.start_time = None
        self.pause_time = None

    def pause(self):
        if not self.is_active:
            raise TimerError("タイマーは動作していません")
        if self.pause_time:
            raise TimerError("タイマーは既に一時停止中です")
        self.pause_time = time.time()

    def resume(self):
        if not self.is_active:
            raise TimerError("タイマーは動作していません")
        if not self.pause_time:
            raise TimerError("タイマーは一時停止されていません")
        pause_duration = time.time() - self.pause_time
        self.total_pause_time += pause_duration
        self.pause_time = None

    def get_time_remaining(self) -> float:
        if not self.is_active:
            return self.duration
        elapsed_time = time.time() - self.start_time - self.total_pause_time
        if self.pause_time:
            elapsed_time -= time.time() - self.pause_time
        return max(self.duration - elapsed_time, 0)

class PomodoroApp:
    def __init__(self, master):
        self.master = master
        self.master.title("ポモドーロタイマー")
        self.master.geometry("500x400")

        self.timer = Timer()
        self.video_thread = None
        self.driver = None

        self.create_widgets()

    def create_widgets(self):
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#ccc")

        self.timer_label = ttk.Label(self.master, text="25:00", font=("Helvetica", 48))
        self.timer_label.pack(pady=20)

        self.button_frame = ttk.Frame(self.master)
        self.button_frame.pack(pady=10)

        self.start_button = ttk.Button(self.button_frame, text="開始", command=self.start_timer)
        self.start_button.grid(row=0, column=0, padx=5)

        self.pause_button = ttk.Button(self.button_frame, text="一時停止", command=self.pause_timer, state="disabled")
        self.pause_button.grid(row=0, column=1, padx=5)

        self.reset_button = ttk.Button(self.button_frame, text="リセット", command=self.reset_timer)
        self.reset_button.grid(row=0, column=2, padx=5)

        self.url_frame = ttk.Frame(self.master)
        self.url_frame.pack(pady=10)

        self.url_entry = ttk.Entry(self.url_frame, width=40)
        self.url_entry.grid(row=0, column=0, padx=5)

        self.paste_button = ttk.Button(self.url_frame, text="ペースト", command=self.paste_url)
        self.paste_button.grid(row=0, column=1, padx=5)

        self.play_button = ttk.Button(self.url_frame, text="動画再生", command=self.play_video)
        self.play_button.grid(row=0, column=2, padx=5)

        self.sync_var = tk.BooleanVar()
        self.sync_checkbox = ttk.Checkbutton(self.master, text="動画と同期", variable=self.sync_var, command=self.toggle_sync_with_video)
        self.sync_checkbox.pack(pady=5)

    def start_timer(self):
        try:
            self.timer.start()
            logging.info("タイマーが開始されました")
            self.update_timer()
            self.start_button.config(state="disabled")
            self.pause_button.config(state="normal")
        except TimerError as e:
            logging.error(f"タイマー開始エラー: {str(e)}")
            messagebox.showerror("エラー", str(e))

    def pause_timer(self):
        try:
            self.timer.pause()
            logging.info("タイマーが一時停止されました")
            self.start_button.config(state="normal")
            self.pause_button.config(state="disabled")
        except TimerError as e:
            logging.error(f"タイマー一時停止エラー: {str(e)}")
            messagebox.showerror("エラー", str(e))

    def reset_timer(self):
        try:
            self.timer.stop()
            self.timer = Timer()
            logging.info("タイマーがリセットされました")
            self.update_timer()
            self.start_button.config(state="normal")
            self.pause_button.config(state="disabled")
        except TimerError as e:
            logging.error(f"タイマーリセットエラー: {str(e)}")
            messagebox.showerror("エラー", str(e))

    def update_timer(self):
        remaining_time = self.timer.get_time_remaining()
        minutes, seconds = divmod(int(remaining_time), 60)
        self.timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
        if self.timer.is_active and remaining_time > 0:
            self.master.after(1000, self.update_timer)
        elif self.timer.is_active and remaining_time == 0:
            self.timer.is_active = False
            self.timer.pomodoro_count += 1
            self.play_sound()
            if not self.timer.is_break:
                messagebox.showinfo("ポモドーロ", "作業時間が終了しました。休憩しましょう！")
                self.timer.duration = 5 * 60  # 5分休憩
                self.timer.is_break = True
            else:
                messagebox.showinfo("ポモドーロ", "休憩時間が終了しました。作業を再開しましょう！")
                self.timer.duration = 25 * 60  # 25分作業
                self.timer.is_break = False
            self.start_timer()

    def play_sound(self):
        winsound.PlaySound("SystemHand", winsound.SND_ALIAS)

    def paste_url(self):
        self.url_entry.delete(0, tk.END)
        self.url_entry.insert(0, pyperclip.paste())

    def toggle_sync_with_video(self):
        self.timer.sync_with_video = self.sync_var.get()
        logging.info(f"動画同期オプションが{'有効' if self.timer.sync_with_video else '無効'}になりました")

    def play_video(self):
        try:
            url = self.url_entry.get()
            video_id = self.extract_video_id(url)
            if not video_id:
                raise ValueError("無効なYouTube URLです")
            video_url = f"https://www.youtube.com/watch?v={video_id}"
            self.video_thread = threading.Thread(target=self.play_youtube_video, args=(video_url,))
            self.video_thread.start()
        except ValueError as ve:
            logging.error(f"動画再生エラー: {str(ve)}")
            messagebox.showerror("エラー", str(ve))
        except Exception as e:
            logging.error(f"動画再生エラー: {str(e)}")
            messagebox.showerror("エラー", "動画の再生中にエラーが発生しました")

    def extract_video_id(self, url: str) -> Optional[str]:
        youtube_regex = (
            r'(https?://)?(www\.)?'
            '(youtube|youtu|youtube-nocookie)\.(com|be)/'
            '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
        )
        match = re.match(youtube_regex, url)
        return match.group(6) if match else None

    def play_youtube_video(self, url):
        try:
            chrome_options = Options()
            chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
            self.driver = webdriver.Chrome(options=chrome_options)
            self.driver.get(url)

            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".html5-video-player"))
            )

            try:
                play_button = WebDriverWait(self.driver, 10).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, '.ytp-play-button'))
                )
                play_button.click()
            except (TimeoutException, NoSuchElementException):
                logging.warning("再生ボタンが見つからないか、クリックできません")

            if self.timer.sync_with_video:
                video_duration = self.get_video_duration()
                if video_duration:
                    self.timer.duration = video_duration
                    self.start_timer()

            logging.info(f"動画が再生されました: {url}")

        except WebDriverException as e:
            logging.error(f"WebDriverエラー: {str(e)}")
            messagebox.showerror("エラー", f"ブラウザの操作中にエラーが発生しました: {str(e)}")
        except Exception as e:
            logging.error(f"動画再生エラー: {str(e)}")
            messagebox.showerror("エラー", f"動画の再生中にエラーが発生しました: {str(e)}")
        finally:
            if self.driver:
                self.driver.quit()
                self.driver = None

    def get_video_duration(self):
        try:
            video_length_element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ytp-time-duration"))
            )
            video_length = video_length_element.text
            time_parts = video_length.split(':')
            if len(time_parts) == 2:
                minutes, seconds = map(int, time_parts)
                return minutes * 60 + seconds
            elif len(time_parts) == 3:
                hours, minutes, seconds = map(int, time_parts)
                return hours * 3600 + minutes * 60 + seconds
        except (TimeoutException, NoSuchElementException, ValueError):
            logging.warning("動画の長さを取得できません")
        return None

    def on_closing(self):
        if self.driver:
            self.driver.quit()
        self.master.quit()

if __name__ == "__main__":
    root = tk.Tk()
    app = PomodoroApp(root)
    root.protocol("WM_DELETE_WINDOW", app.on_closing)
    root.mainloop()
