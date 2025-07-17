#!/usr/bin/env python3
"""
PostgreSQL usersテーブルの状態確認スクリプト
"""

import os
import psycopg
from psycopg.rows import dict_row
from dotenv import load_dotenv

load_dotenv()

def check_users_table():
    """usersテーブルの状態を確認"""
    database_url = os.getenv('DATABASE_URL')
    
    try:
        with psycopg.connect(database_url) as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                # テーブル構造を確認
                print("=== テーブル構造確認 ===")
                cur.execute("""
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_name = 'users'
                    ORDER BY ordinal_position;
                """)
                columns = cur.fetchall()
                for col in columns:
                    print(f"{col['column_name']}: {col['data_type']} (nullable: {col['is_nullable']}, default: {col['column_default']})")
                
                print("\n=== 既存ユーザーデータ ===")
                cur.execute("SELECT id, email, LENGTH(password_hash) as hash_length, is_premium, free_usage_count FROM users")
                users = cur.fetchall()
                for user in users:
                    print(f"ID: {user['id']}, Email: {user['email']}, Hash Length: {user['hash_length']}, Premium: {user['is_premium']}, Usage: {user['free_usage_count']}")
                
                print("\n=== パスワードハッシュ詳細 ===")
                cur.execute("SELECT id, email, password_hash FROM users LIMIT 3")
                users = cur.fetchall()
                for user in users:
                    hash_data = user['password_hash']
                    print(f"\nUser {user['id']} ({user['email']}):")
                    print(f"  Type: {type(hash_data)}")
                    if isinstance(hash_data, memoryview):
                        print(f"  Memoryview bytes: {hash_data.tobytes()[:50]}...")
                    elif isinstance(hash_data, bytes):
                        print(f"  Bytes: {hash_data[:50]}...")
                    elif isinstance(hash_data, str):
                        print(f"  String: {hash_data[:50]}...")
                
    except Exception as e:
        print(f"エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_users_table()