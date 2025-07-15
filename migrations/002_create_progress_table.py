
import sqlite3

def migrate(db_path):
    """
    progressテーブルを作成するマイグレーション
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # progressテーブルが存在しない場合のみ作成
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
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

        conn.commit()
        print("マイグレーション成功: 'progress'テーブルを作成しました。")

    except sqlite3.Error as e:
        print(f"データベースエラー: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    import os
    # このスクリプトの場所を基準に、プロジェクトルートを特定
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, '..'))
    db_file = os.path.join(project_root, 'study_app.db')
    
    print(f"データベースファイルのパス: {db_file}")
    migrate(db_file)
