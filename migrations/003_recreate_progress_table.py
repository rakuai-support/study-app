
import sqlite3
import os

def migrate(db_path):
    """
    progressテーブルを削除し、正しいUNIQUE制約付きで再作成する
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 既存のprogressテーブルを削除
        cursor.execute("DROP TABLE IF EXISTS progress")
        print("古い'progress'テーブルを削除しました。")

        # 正しいスキーマでprogressテーブルを再作成
        cursor.execute("""
        CREATE TABLE progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            item_identifier TEXT NOT NULL,
            level TEXT NOT NULL,
            goal_index INTEGER NOT NULL,
            completed INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL,
            UNIQUE(user_id, item_identifier, level, goal_index)
        )
        """)
        print("新しい'progress'テーブルをUNIQUE制約付きで作成しました。")

        conn.commit()
        print("マイグレーション成功: 'progress'テーブルを再作成しました。")

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
