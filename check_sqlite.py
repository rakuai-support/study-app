#!/usr/bin/env python3
"""
SQLiteデータベース内容確認スクリプト
"""

import sqlite3
import os

def check_sqlite():
    """SQLiteデータベースの内容を確認"""
    db_path = 'study_app.db'
    
    if not os.path.exists(db_path):
        print(f"SQLiteデータベースファイルが見つかりません: {db_path}")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # テーブル一覧を取得
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' 
                ORDER BY name
            """)
            tables = cursor.fetchall()
            
            print("=== SQLiteデータベース内容確認 ===")
            print(f"データベース: {db_path}")
            print(f"テーブル数: {len(tables)}")
            print()
            
            for (table_name,) in tables:
                print(f"--- {table_name} ---")
                
                # 件数を取得
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"件数: {count}")
                
                # 最初の5件を表示
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                rows = cursor.fetchall()
                
                if rows:
                    # カラム名を取得
                    cursor.execute(f"PRAGMA table_info({table_name})")
                    columns = [row[1] for row in cursor.fetchall()]
                    print(f"カラム: {', '.join(columns)}")
                    
                    print("サンプルデータ:")
                    for row in rows:
                        print(f"  {row}")
                else:
                    print("データなし")
                print()
                
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    check_sqlite()