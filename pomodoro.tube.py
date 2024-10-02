import tkinter as tk
from tkinter import ttk, messagebox
import asyncio
import logging
import re
import time
import webbrowser
from typing import Optional

from pytube import YouTube

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

timer = Timer()

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

def play_video():
    """YouTube動画を再生する"""
    video_url = video_url_entry.get()
    if video_url:
        try:
            video_id = extract_video_id(video_url)
            if video_id:
                url = get_youtube_url(video_id)
                webbrowser.open(url)
            else:
                messagebox.showerror("エラー", "有効なYouTube URLを入力してください")
        except Exception as e:
            messagebox.showerror("エラー", f"動画の再生中にエラーが発生しました: {str(e)}")

def update_timer():
    """タイマーの表示を更新する"""
    if not timer.is_active:
        time_left = timer.duration
        status = "停止"
    else:
        if timer.pause_time:
            elapsed_time = timer.pause_time - timer.start_time - timer.total_pause_time
            status = "一時停止中"
        else:
            elapsed_time = time.time() - timer.start_time - timer.total_pause_time
            status = "動作中"
        time_left = max(0, timer.duration - int(elapsed_time))

    minutes, seconds = divmod(time_left, 60)
    time_string = f"{minutes:02d}:{seconds:02d}"
    timer_label.config(text=f"{time_string} ({status})")

    if timer.is_active and time_left > 0:
        root.after(1000, update_timer)
    elif timer.is_active and time_left == 0:
        messagebox.showinfo("時間終了", "時間になりました！")
        stop_timer()

# GUIの作成
root = tk.Tk()
root.title("ポモドーロタイマー with YouTube")

frame = ttk.Frame(root, padding="10")
frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

timer_label = ttk.Label(frame, text="25:00 (停止)", font=("Helvetica", 24))
timer_label.grid(row=0, column=0, columnspan=4, pady=10)

start_button = ttk.Button(frame, text="開始", command=start_timer)
start_button.grid(row=1, column=0, padx=5, pady=5)

stop_button = ttk.Button(frame, text="停止", command=stop_timer)
stop_button.grid(row=1, column=1, padx=5, pady=5)

pause_button = ttk.Button(frame, text="一時停止", command=pause_timer)
pause_button.grid(row=1, column=2, padx=5, pady=5)

resume_button = ttk.Button(frame, text="再開", command=resume_timer)
resume_button.grid(row=1, column=3, padx=5, pady=5)

ttk.Label(frame, text="タイマー設定 (分):").grid(row=2, column=0, padx=5, pady=5)
duration_entry = ttk.Entry(frame, width=10)
duration_entry.grid(row=2, column=1, padx=5, pady=5)
duration_entry.insert(0, "25")

set_button = ttk.Button(frame, text="設定", command=set_timer)
set_button.grid(row=2, column=2, padx=5, pady=5)

ttk.Label(frame, text="YouTube URL:").grid(row=3, column=0, padx=5, pady=5)
video_url_entry = ttk.Entry(frame, width=40)
video_url_entry.grid(row=3, column=1, columnspan=2, padx=5, pady=5)

play_button = ttk.Button(frame, text="動画再生", command=play_video)
play_button.grid(row=3, column=3, padx=5, pady=5)

root.mainloop()