#!/usr/bin/env python3
"""
PostgreSQL直接接続テスト（psycopg）
"""

import os
import psycopg
from dotenv import load_dotenv

load_dotenv()

def test_direct_connection():
    """直接接続テスト"""
    database_url = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {database_url}")
    
    # IPv6アドレス直接指定テスト
    ipv6_url = "postgresql://postgres:1342uchi@[2406:da14:271:9904:1de9:61ba:2623:da7e]:5432/postgres"
    
    print("\n=== 通常の接続テスト ===")
    try:
        print("psycopgで直接接続を試行...")
        with psycopg.connect(database_url) as conn:
            print("接続成功！")
            _test_queries(conn)
                
    except Exception as e:
        print(f"接続エラー: {e}")
        print(f"エラータイプ: {type(e)}")
        
    print("\n=== IPv6直接指定テスト ===")
    try:
        print("IPv6アドレス直接指定で接続を試行...")
        with psycopg.connect(ipv6_url) as conn:
            print("IPv6接続成功！")
            _test_queries(conn)
            
    except Exception as e:
        print(f"IPv6接続エラー: {e}")
        print(f"エラータイプ: {type(e)}")

def _test_queries(conn):
    """接続後のテストクエリ"""
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        version = cur.fetchone()[0]
        print(f"PostgreSQL version: {version}")
        
        cur.execute("SELECT current_database()")
        database = cur.fetchone()[0]
        print(f"Current database: {database}")
        
        cur.execute("SELECT current_user")
        user = cur.fetchone()[0]
        print(f"Current user: {user}")

if __name__ == "__main__":
    test_direct_connection()