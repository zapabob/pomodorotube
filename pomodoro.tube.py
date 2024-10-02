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

# ロギングの設定
logging.basicConfig(
    filename='pomodoro.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class Timer:
    def __init__(self, duration: int = 25 * 60):
        self.duration = duration
        self.start_time: Optional[float] = None
        self.is_active: bool = False
        self.pause_time: Optional[float] = None
        self.total_pause_time: float = 0
        self.sync_with_video: bool = False

timer = Timer()
video_thread = None
driver = None

def start_timer():
    """タイマーを開始する"""
    try:
        if timer.is_active:
            messagebox.showinfo("情報", "タイマーは既に動作中です")
            return
        timer.start_time = time.time()
        timer.is_active = True
        timer.total_pause_time = 0
        logging.info("タイマーが開始されました")
        update_timer()
    except Exception as e:
        logging.error(f"タイマー開始エラー: {str(e)}")
        messagebox.showerror("エラー", "タイマーの開始中にエラーが発生しました")

def stop_timer():
    """タイマーを停止する"""
    try:
        if not timer.is_active:
            messagebox.showinfo("情報", "タイマーは動作していません")
            return
        timer.is_active = False
        timer.start_time = None
        timer.pause_time = None
        logging.info("タイマーが停止されました")
        update_timer()
    except Exception as e:
        logging.error(f"タイマー停止エラー: {str(e)}")
        messagebox.showerror("エラー", "タイマーの停止中にエラーが発生しました")

def pause_timer():
    """タイマーを一時停止する"""
    try:
        if not timer.is_active:
            messagebox.showinfo("情報", "タイマーは動作していません")
            return
        if timer.pause_time:
            messagebox.showinfo("情報", "タイマーは既に一時停止中です")
            return
        timer.pause_time = time.time()
        logging.info("タイマーが一時停止されました")
        update_timer()
    except Exception as e:
        logging.error(f"タイマー一時停止エラー: {str(e)}")
        messagebox.showerror("エラー", "タイマーの一時停止中にエラーが発生しました")

def resume_timer():
    """一時停止したタイマーを再開する"""
    try:
        if not timer.is_active:
            messagebox.showinfo("情報", "タイマーは動作していません")
            return
        if not timer.pause_time:
            messagebox.showinfo("情報", "タイマーは一時停止されていません")
            return
        pause_duration = time.time() - timer.pause_time
        timer.total_pause_time += pause_duration
        timer.pause_time = None
        logging.info("タイマーが再開されました")
        update_timer()
    except Exception as e:
        logging.error(f"タイマー再開エラー: {str(e)}")
        messagebox.showerror("エラー", "タイマーの再開中にエラーが発生しました")

def set_timer():
    """タイマーの時間を設定する"""
    try:
        if timer.is_active:
            messagebox.showinfo("情報", "タイマー動作中は設定を変更できません")
            return
        duration = int(duration_entry.get()) * 60
        if duration <= 0:
            raise ValueError("タイマーの時間は0より大きい値を設定してください")
        timer.duration = duration
        logging.info(f"タイマーが{duration}秒に設定されました")
        update_timer()
    except ValueError as ve:
        logging.error(f"タイマー設定エラー: {str(ve)}")
        messagebox.showerror("エラー", str(ve))
    except Exception as e:
        logging.error(f"タイマー設定エラー: {str(e)}")
        messagebox.showerror("エラー", "タイマーの設定中にエラーが発生しました")

def extract_video_id(url: str) -> Optional[str]:
    """YouTubeのURLからビデオIDを抽出する"""
    youtube_regex = (
        r'(https?://)?(www\.)?'
        '(youtube|youtu|youtube-nocookie)\.(com|be)/'
        '(watch\?v=|embed/|v/|.+\?v=)?([^&=%\?]{11})'
    )
    match = re.match(youtube_regex, url)
    return match.group(6) if match else None

def get_youtube_url(video_id: str) -> str:
    """YouTubeビデオIDから再生可能なURLを取得する"""
    try:
        yt = YouTube(f"https://www.youtube.com/watch?v={video_id}")
        return yt.streams.filter(progressive=True, file_extension='mp4').order_by('resolution').desc().first().url
    except Exception as e:
        logging.error(f"YouTube URL取得エラー: {str(e)}")
        raise Exception("YouTube URLの取得中にエラーが発生しました")

def play_youtube_video(url):
    """Chromiumを使用してYouTube動画を再生する"""
    global driver
    try:
        # Chromiumのオプションを設定
        chrome_options = Options()
        chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")
        
        # Chromiumドライバーを初期化
        driver = webdriver.Chrome(options=chrome_options)
        
        # YouTubeのURLを開く
        driver.get(url)
        
        # 動画プレーヤーが読み込まれるまで待機
        try:
            WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".html5-video-player"))
            )
        except TimeoutException:
            raise Exception("動画プレーヤーの読み込みに失敗しました")
        
        # 再生ボタンをクリック（必要な場合）
        try:
            play_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, '.ytp-play-button'))
            )
            play_button.click()
        except (TimeoutException, NoSuchElementException):
            logging.warning("再生ボタンが見つからないか、クリックできません")
        
        # 動画の長さを取得
        try:
            video_length_element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ytp-time-duration"))
            )
            video_length = video_length_element.text
            time_parts = video_length.split(':')
            if len(time_parts) == 2:
                minutes, seconds = map(int, time_parts)
                video_duration = minutes * 60 + seconds
            elif len(time_parts) == 3:
                hours, minutes, seconds = map(int, time_parts)
                video_duration = hours * 3600 + minutes * 60 + seconds
            else:
                raise ValueError("Unexpected time format")
        except (TimeoutException, NoSuchElementException, ValueError):
            logging.warning("動画の長さを取得できません")
            video_duration = None
        
        # タイマーを動画の長さに合わせて設定（オプション）
        if timer.sync_with_video and video_duration:
            timer.duration = video_duration
            start_timer()
        
        logging.info(f"動画が再生されました: {url}")
        
        # 動画が終了するまで待機
        if video_duration:
            try:
                WebDriverWait(driver, video_duration + 30).until(
                    EC.text_to_be_present_in_element((By.CLASS_NAME, "ytp-time-current"), video_length)
                )
            except TimeoutException:
                logging.warning("動画の終了を検出できませんでした")
        else:
            # 動画の長さが不明の場合は、一定時間待機
            time.sleep(300)  # 5分間待機
        
        # 動画が終了したらタイマーも停止（オプション）
        if timer.sync_with_video:
            stop_timer()
        
    except WebDriverException as e:
        logging.error(f"WebDriverエラー: {str(e)}")
        messagebox.showerror("エラー", f"ブラウザの操作中にエラーが発生しました: {str(e)}")
    except Exception as e:
        logging.error(f"動画再生エラー: {str(e)}")
        messagebox.showerror("エラー", f"動画の再生中にエラーが発生しました: {str(e)}")
    finally:
        if driver:
            driver.quit()
            driver = None

def play_video():
    """YouTubeの動画を再生する"""
    global video_thread
    try:
        url = url_entry.get()
        video_id = extract_video_id(url)
        if not video_id:
            raise ValueError("無効なYouTube URLです")
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        video_thread = threading.Thread(target=play_youtube_video, args=(video_url,))
        video_thread.start()
    except ValueError as ve:
        logging.error(f"動画再生エラー: {str(ve)}")
        messagebox.showerror("エラー", str(ve))
    except Exception as e:
        logging.error(f"動画再生エラー: {str(e)}")
        messagebox.showerror("エラー", "動画の再生中にエラーが発生しました")

def update_timer():
    """タイマーの表示を更新する"""
    if timer.is_active and timer.start_time is not None:
        elapsed_time = time.time() - timer.start_time - timer.total_pause_time
        if timer.pause_time:
            elapsed_time -= time.time() - timer.pause_time
        remaining_time = max(timer.duration - elapsed_time, 0)
        minutes, seconds = divmod(int(remaining_time), 60)
        timer_label.config(text=f"{minutes:02d}:{seconds:02d}")
        if remaining_time > 0:
            root.after(1000, update_timer)
        else:
            timer.is_active = False
            messagebox.showinfo("情報", "タイマーが終了しました")
    else:
        minutes, seconds = divmod(timer.duration, 60)
        timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

def update_current_time():
    """現在時刻を更新する"""
    JST = timezone(timedelta(hours=+9), 'JST')
    current_time = datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S")
    current_time_label.config(text=f"現在時刻: {current_time}")
    root.after(1000, update_current_time)

def toggle_sync_with_video():
    """動画同期オプションを切り替える"""
    timer.sync_with_video = sync_var.get()
    logging.info(f"動画同期オプションが{'有効' if timer.sync_with_video else '無効'}になりました")

def on_closing():
    """アプリケーション終了時の処理"""
    global driver
    if driver:
        driver.quit()
    root.quit()

# GUIの設定
root = tk.Tk()
root.title("ポモドーロタイマー")
root.protocol("WM_DELETE_WINDOW", on_closing)

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

timer_label = ttk.Label(frame, text="25:00", font=("Helvetica", 48))
timer_label.grid(row=0, column=0, columnspan=4, pady=10)

current_time_label = ttk.Label(frame, text="", font=("Helvetica", 12))
current_time_label.grid(row=1, column=0, columnspan=4, pady=5)

start_button = ttk.Button(frame, text="スタート", command=start_timer)
start_button.grid(row=2, column=0, pady=5)

stop_button = ttk.Button(frame, text="ストップ", command=stop_timer)
stop_button.grid(row=2, column=1, pady=5)

pause_button = ttk.Button(frame, text="一時停止", command=pause_timer)
pause_button.grid(row=2, column=2, pady=5)

resume_button = ttk.Button(frame, text="再開", command=resume_timer)
resume_button.grid(row=2, column=3, pady=5)

duration_label = ttk.Label(frame, text="タイマー時間（分）:")
duration_label.grid(row=3, column=0, pady=5)

duration_entry = ttk.Entry(frame, width=10)
duration_entry.insert(0, "25")
duration_entry.grid(row=3, column=1, pady=5)

set_button = ttk.Button(frame, text="設定", command=set_timer)
set_button.grid(row=3, column=2, columnspan=2, pady=5)

url_label = ttk.Label(frame, text="YouTube URL:")
url_label.grid(row=4, column=0, pady=5)

url_entry = ttk.Entry(frame, width=40)
url_entry.grid(row=4, column=1, columnspan=2, pady=5)

play_button = ttk.Button(frame, text="動画再生", command=play_video)
play_button.grid(row=4, column=3, pady=5)

sync_var = tk.BooleanVar()
sync_checkbox = ttk.Checkbutton(frame, text="動画と同期", variable=sync_var, command=toggle_sync_with_video)
sync_checkbox.grid(row=5, column=0, columnspan=4, pady=5)

# コピーアンドペースト機能を有効にする
url_entry.bind('<Control-v>', lambda e: 'break')  # デフォルトの動作を無効化
url_entry.bind('<Control-V>', lambda e: 'break') # 大文字のVも対応
copy_button = ttk.Button(frame, text="コピー", command=lambda: root.clipboard_clear())
def paste(event):
    url_entry.delete(0, tk.END)
    url_entry.insert(tk.INSERT, root.clipboard_get())

url_entry.bind('<Control-v>', paste)
url_entry.bind('<Control-V>', paste)

update_current_time()

root.mainloop()