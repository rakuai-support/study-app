#!/usr/bin/env python3
"""
データベース内容確認スクリプト
"""

import os
import psycopg
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

def check_database():
    """データベースの内容を確認"""
    database_url = os.getenv('DATABASE_URL')
    
    if not database_url:
        print("DATABASE_URLが設定されていません")
        return
    
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor() as cur:
                # テーブル一覧を取得
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public'
                    ORDER BY table_name
                """)
                tables = cur.fetchall()
                
                print("=== データベース内容確認 ===")
                print(f"データベース: {database_url.split('@')[1].split('/')[0]}")
                print(f"テーブル数: {len(tables)}")
                print()
                
                for (table_name,) in tables:
                    print(f"--- {table_name} ---")
                    
                    # 件数を取得
                    cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                    count = cur.fetchone()[0]
                    print(f"件数: {count}")
                    
                    # 最初の5件を表示
                    cur.execute(f"SELECT * FROM {table_name} LIMIT 5")
                    rows = cur.fetchall()
                    
                    if rows:
                        # カラム名を取得
                        cur.execute(f"""
                            SELECT column_name 
                            FROM information_schema.columns 
                            WHERE table_name = '{table_name}'
                            ORDER BY ordinal_position
                        """)
                        columns = [row[0] for row in cur.fetchall()]
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
    check_database()