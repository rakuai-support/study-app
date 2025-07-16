# 高校生版 AI学習アプリ (manabuwa)

小学校・中学校・高校の学習指導要領データを活用した教育支援Webアプリケーション

## 🚀 主な機能

- **学習指導要領データ閲覧**: 741項目の詳細学習内容
- **AI学習サポート**: Gemini APIによる個別指導
- **進捗管理**: ユーザー別学習進捗追跡
- **フリーミアムSaaS**: 無料プラン（30回/月）＋プレミアムプラン
- **管理者機能**: 認証コード生成・使用量統計

## 🛠 技術スタック

- **バックエンド**: Python Flask + PostgreSQL
- **フロントエンド**: HTML/CSS/JavaScript (Vanilla)
- **AI統合**: Google Gemini API
- **認証**: Flask-Login + bcrypt
- **デプロイ**: Render (Free Tier)

## 📋 本番環境デプロイ手順

### 1. 環境変数設定

Renderダッシュボードで以下の環境変数を設定：

```bash
DATABASE_URL=postgresql://username:password@host:port/database
GEMINI_API_KEY=your-gemini-api-key
ADMIN_KEY=your-secure-admin-key
SECRET_KEY=your-secret-key-change-this-in-production
```

### 2. PostgreSQLデータベース

- Supabase PostgreSQL（無料プラン）を使用
- 接続情報を`DATABASE_URL`に設定
- アプリ起動時に自動テーブル作成

### 3. Renderデプロイ

1. GitHubリポジトリをRenderに接続
2. 環境変数を設定
3. 自動デプロイ実行

### 4. 初期設定

- 管理者アカウント作成
- `/admin`で認証コード生成
- AI機能テスト実行

## 🔧 ローカル開発環境

### 必要条件

- Python 3.11+
- PostgreSQL（Supabaseアカウント）
- Gemini API キー

### セットアップ

```bash
# 1. リポジトリクローン
git clone <repository-url>
cd study-app

# 2. 仮想環境作成
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. 依存関係インストール
pip install -r requirements.txt

# 4. 環境変数設定
cp .env.example .env
# .envファイルを編集して実際の値を設定

# 5. アプリ起動
python study_app.py
```

### アクセス

- **メインアプリ**: http://127.0.0.1:5000
- **管理画面**: http://127.0.0.1:5000/admin

## 📊 管理機能

### 管理者画面 (`/admin`)

1. **🎫 認証コード生成**
   - プレミアムユーザー有効化
   - 有効期限設定（30日〜5年）

2. **❌ プレミアム解除**
   - ユーザーのプレミアム状態解除
   - キャンセル処理

3. **📊 使用量統計**
   - 全ユーザーの使用量確認
   - プレミアム/無料ユーザー統計

## 🎯 利用制限

- **無料プラン**: AI機能30回/月
- **プレミアムプラン**: AI機能無制限
- **進捗管理**: 制限なし（全ユーザー）

## 🔐 セキュリティ

- パスワード: bcryptハッシュ化
- セッション管理: Flask-Login
- 機密情報: 環境変数管理
- CSRF保護: Flask標準機能

## 📝 API エンドポイント

### 認証
- `POST /login` - ログイン
- `POST /register` - ユーザー登録
- `GET /logout` - ログアウト

### AI機能
- `POST /api/ai-generate` - AI生成実行
- `POST /api/test-api-key` - APIキーテスト

### 進捗管理
- `GET /api/progress/<user_id>` - 進捗取得
- `POST /api/progress/update` - 進捗更新
- `GET /api/progress-stats` - 統計情報

### 管理者機能
- `POST /api/generate-activation-code` - 認証コード生成
- `POST /api/revoke-premium` - プレミアム解除
- `POST /api/usage-stats` - 使用量統計

## 🧪 テスト

### 動作確認項目

1. **基本機能**
   - ユーザー登録・ログイン
   - 学習データ閲覧
   - 進捗保存・読み込み

2. **AI機能**
   - Gemini API接続
   - プロンプト実行
   - 利用制限（30回/月）

3. **プレミアム機能**
   - 認証コード有効化
   - 無制限AI利用
   - 使用量追跡

4. **管理機能**
   - 認証コード生成
   - プレミアム解除
   - 使用量統計表示

## 📈 パフォーマンス最適化

- **データベース**: 接続プール使用
- **統計情報**: キャッシュ化（起動時計算）
- **ログ**: 重要エンドポイントのみ出力
- **フロントエンド**: API呼び出し最適化

## 🐛 トラブルシューティング

### よくある問題

1. **PostgreSQL接続エラー**
   - `DATABASE_URL`環境変数確認
   - Supabase接続情報確認

2. **AI機能エラー**
   - `GEMINI_API_KEY`確認
   - API制限・課金状況確認

3. **認証エラー**
   - セッション期限切れ → 再ログイン
   - `SECRET_KEY`設定確認

## 📞 サポート

- **開発者**: Your Name
- **Email**: your-email@example.com
- **リポジトリ**: GitHub URL

## 📜 ライセンス

MIT License - 詳細は`LICENSE`ファイルを参照

---

**🌟 高校生の皆さんの学習を全力でサポートします！**