# Pomodoro Tube

Pomodoro TubeはPythonで開発されたポモドーロテクニック用のタイマーアプリケーションです。YouTubeの動画を組み込んで、作業中や休憩中に好きな動画を視聴することができます。

## 機能

- ポモドーロタイマー（25分作業 / 5分休憩）
- 長時間休憩オプション（4セット後に15分休憩）
- YouTubeビデオプレーヤー統合
- タスクリスト管理（5つ）
- Notion連携機能

## 必要条件

- Python 3.7以上
- PyQt5
- PyQtWebEngine
- その他の依存ライブラリ（requirements.txtを参照）

## インストール

1. リポジトリをクローンまたはダウンロードします。



git clone https://github.com/zapabob/pomodoro_tube.git
cd pomodoro_tube



2. 仮想環境を作成し、アクティベートします（推奨）。

python -m venv venv
source venv/bin/activate  # Linuxの場合
venv\Scripts\activate  # Windowsの場合


3. 必要なライブラリをインストールします。

pip install -r requirements.txt

## 使用方法

1. アプリケーションを起動します。
python pomodoro_tube.py


2. 「開始」ボタンをクリックしてポモドーロタイマーを開始します。
3. YouTubeのURLを入力し、「読み込み」ボタンをクリックして動画を再生します。
4. タスクを入力し、「タスクを追加」ボタンをクリックしてタスクリストに追加します。

## 注意事項

- YouTubeの利用規約に従って使用してください。
- Notion連携機能を使用する場合は、別途NotionのAPIキーが必要です。
- アプリケーションの使用中は、適度な休憩を取ることを忘れずに。

## ライセンス

このプロジェクトはMITライセンスの下で公開されています。詳細は[LICENSE](LICENSE)ファイルを参照してください。

## 貢献

バグ報告や機能リクエストは、GitHubのIssueを通じてお願いします。プルリクエストも歓迎します。

## 作者

峯岸亮

---

このプロジェクトは学習目的で作成されました。商用利用する場合は、各サービスの利用規約を確認してください。

