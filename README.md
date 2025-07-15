# 学習指導要領アプリ (Study App)

AI統合型学習指導要領管理Webアプリケーション

## 🚀 機能

- **学習進捗管理**: 741項目の詳細進捗追跡
- **AIアシスタント**: Gemini API統合による学習支援
- **ユーザー認証**: セキュアな個人アカウント管理
- **フリーミアムモデル**: 30回/月無料、プレミアム無制限

## 🛠 技術スタック

- **Backend**: Python Flask
- **Frontend**: JavaScript, HTML5, CSS3
- **Database**: SQLite
- **AI**: Google Gemini API
- **Authentication**: Flask-Login + bcrypt

## 📋 環境変数

以下の環境変数を設定してください：

```bash
SECRET_KEY=your-secret-key-here
GEMINI_API_KEY=your-gemini-api-key-here
ADMIN_KEY=your-admin-key-here
```

## 🔧 ローカル開発

1. リポジトリをクローン
```bash
git clone <repository-url>
cd studyアプリ
```

2. 依存関係をインストール
```bash
pip install -r requirements.txt
```

3. 環境変数を設定
```bash
cp .env.example .env
# .envファイルを編集して実際の値を設定
```

4. アプリケーションを起動
```bash
python study_app.py
```

## 🚀 デプロイ (Render)

1. GitHubリポジトリを作成
2. Renderでリポジトリを連携
3. 環境変数を設定:
   - `GEMINI_API_KEY`: Google AI Studio から取得
   - `ADMIN_KEY`: 管理者用キー
   - `SECRET_KEY`: 自動生成または手動設定

## 📊 完成度

- **メイン機能**: 100% 完成
- **AI統合**: 100% 完成
- **認証システム**: 100% 完成
- **進捗管理**: 100% 完成
- **フリーミアム**: 100% 完成

**総合完成度**: 95% 🚀

---

© 2024-2025 学習指導要領アプリ開発プロジェクト