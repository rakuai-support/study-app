import sqlite3
import os

def migrate(db_path):
    """
    ユーザー認証システム用のテーブルを作成する
    - users: ユーザー情報（メール、パスワード、プレミアム状態等）
    - activation_codes: プレミアム認証コード管理
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # usersテーブルを作成
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_premium INTEGER DEFAULT 0,
            premium_expires_at TEXT,
            free_usage_count INTEGER DEFAULT 0,
            last_reset_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)
        print("'users'テーブルを作成しました。")

        # activation_codesテーブルを作成
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            user_email TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)
        print("'activation_codes'テーブルを作成しました。")

        # インデックスを作成（パフォーマンス向上）
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_premium ON users(is_premium)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activation_codes_code ON activation_codes(code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_activation_codes_user_email ON activation_codes(user_email)")
        print("インデックスを作成しました。")

        conn.commit()
        print("マイグレーション成功: ユーザー認証システム用テーブルを作成しました。")

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    db_file = os.path.join(project_root, 'study_app.db')
    
    print(f"データベースファイルのパス: {db_file}")
    migrate(db_file)