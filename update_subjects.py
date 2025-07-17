#!/usr/bin/env python3
"""
データベースの教科名標準化スクリプト
「特別の教科 道徳」→「道徳」
「外国語」→「英語」
"""

import os
import sys
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# プロジェクトのパスを追加
sys.path.append(os.path.dirname(__file__))

from database import db_manager

def update_subject_names():
    """教科名を標準化"""
    try:
        print("[UPDATE] 教科名の標準化を開始...")
        
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # 現在の教科名を確認
                cur.execute("SELECT DISTINCT subject FROM learning_items ORDER BY subject")
                current_subjects = cur.fetchall()
                print("[UPDATE] 現在の教科名:")
                for subject in current_subjects:
                    print(f"  - {subject[0]}")
                
                # 教科名を更新
                updates = [
                    ("特別の教科 道徳", "道徳"),
                    ("外国語", "英語")
                ]
                
                for old_name, new_name in updates:
                    cur.execute(
                        "UPDATE learning_items SET subject = %s WHERE subject = %s",
                        (new_name, old_name)
                    )
                    updated_count = cur.rowcount
                    print(f"[UPDATE] '{old_name}' → '{new_name}': {updated_count}件更新")
                
                conn.commit()
                
                # 更新後の教科名を確認
                cur.execute("SELECT DISTINCT subject FROM learning_items ORDER BY subject")
                updated_subjects = cur.fetchall()
                print("\n[UPDATE] 更新後の教科名:")
                for subject in updated_subjects:
                    print(f"  - {subject[0]}")
                
                # 教科別件数確認
                cur.execute("SELECT subject, COUNT(*) FROM learning_items GROUP BY subject ORDER BY subject")
                subject_counts = cur.fetchall()
                print("\n[UPDATE] 教科別件数:")
                for subject, count in subject_counts:
                    print(f"  {subject}: {count}件")
        
        print("\n[UPDATE] 教科名の標準化が完了しました")
        return True
        
    except Exception as e:
        print(f"[UPDATE] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    update_subject_names()