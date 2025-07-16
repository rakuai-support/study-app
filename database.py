#!/usr/bin/env python3
"""
psycopg (v3) 対応データベース管理モジュール
PostgreSQL対応 - 最新のpsycopg v3を使用
"""

import os
import pandas as pd
import json
from dotenv import load_dotenv

try:
    import psycopg
    from psycopg.pool import ConnectionPool
    from psycopg.rows import dict_row
    PSYCOPG_VERSION = 3
    print("[DB] INFO: Using psycopg v3")
except ImportError:
    # フォールバック: psycopg2
    import psycopg2 as psycopg
    import psycopg2.extras
    import psycopg2.pool
    PSYCOPG_VERSION = 2
    print("[DB] INFO: Using psycopg2 (fallback)")

# 環境変数読み込み
load_dotenv()

class DatabaseManager:
    """psycopg v3を使用したデータベース管理クラス"""
    
    def __init__(self):
        self.connection_pool = None
        self.db_type = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """データベース接続の初期化"""
        database_url = os.getenv('DATABASE_URL')
        if database_url and 'postgresql://' in database_url:
            try:
                if PSYCOPG_VERSION == 3:
                    # psycopg v3の場合
                    self.connection_pool = ConnectionPool(
                        database_url,
                        min_size=1,
                        max_size=10,
                        max_idle=300,
                        max_lifetime=3600
                    )
                else:
                    # psycopg2の場合（フォールバック）
                    self.connection_pool = psycopg2.pool.SimpleConnectionPool(
                        1, 10, database_url
                    )
                
                # 接続テスト
                with self.get_connection() as conn:
                    if PSYCOPG_VERSION == 3:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                            cur.fetchone()
                    else:
                        with conn.cursor() as cur:
                            cur.execute("SELECT 1")
                            cur.fetchone()
                
                self.db_type = 'postgresql'
                print(f"[DB] SUCCESS: PostgreSQL connection pool created (psycopg v{PSYCOPG_VERSION})")
                return
                
            except Exception as e:
                print(f"[DB] ERROR: PostgreSQL connection failed: {e}")
                self.connection_pool = None
                self.db_type = None
                return
        
        # SQLiteフォールバック
        try:
            import sqlite3
            self.db_type = 'sqlite'
            print("[DB] SUCCESS: SQLite fallback configured")
        except Exception as e:
            print(f"[DB] ERROR: SQLite fallback failed: {e}")
            self.connection_pool = None
            self.db_type = None
    
    def get_connection(self):
        """データベース接続を取得"""
        if self.connection_pool is None:
            self._initialize_connection()
        
        if self.db_type == 'postgresql':
            if PSYCOPG_VERSION == 3:
                return self.connection_pool.connection()
            else:
                return self.connection_pool.getconn()
        else:
            # SQLiteフォールバック
            import sqlite3
            db_path = os.path.join(os.path.dirname(__file__), 'study_app.db')
            return sqlite3.connect(db_path)
    
    def return_connection(self, conn):
        """接続を返却"""
        if conn:
            if self.db_type == 'postgresql' and PSYCOPG_VERSION == 2:
                self.connection_pool.putconn(conn)
            else:
                conn.close()
    
    def execute_query(self, query, params=None):
        """クエリを実行"""
        with self.get_connection() as conn:
            if PSYCOPG_VERSION == 3:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
            else:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, params)
                    return cur.fetchall()
    
    def execute_single(self, query, params=None):
        """単一行を実行"""
        with self.get_connection() as conn:
            if PSYCOPG_VERSION == 3:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(query, params)
                    return cur.fetchone()
            else:
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute(query, params)
                    return cur.fetchone()

# グローバルインスタンス
db_manager = DatabaseManager()

def initialize_database():
    """データベースの初期化"""
    if db_manager.connection_pool is None:
        print("[DB] ERROR: Database connection not established")
        return False
    
    try:
        with db_manager.get_connection() as conn:
            if PSYCOPG_VERSION == 3:
                with conn.cursor() as cur:
                    _create_tables_psycopg3(cur)
                    conn.commit()
            else:
                with conn.cursor() as cur:
                    _create_tables_psycopg2(cur)
                    conn.commit()
        
        # 学習データの読み込み
        _load_learning_data()
        print("[DB] SUCCESS: PostgreSQL tables initialized")
        return True
        
    except Exception as e:
        print(f"[DB] ERROR: Database initialization failed: {e}")
        return False

def _create_tables_psycopg3(cur):
    """psycopg v3でテーブル作成"""
    # usersテーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            email VARCHAR(255) UNIQUE NOT NULL,
            password_hash BYTEA NOT NULL,
            is_premium BOOLEAN DEFAULT FALSE,
            premium_expires_at TIMESTAMP,
            free_usage_count INTEGER DEFAULT 0,
            last_reset_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # activation_codesテーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            id SERIAL PRIMARY KEY,
            code VARCHAR(12) UNIQUE NOT NULL,
            user_email VARCHAR(255) NOT NULL,
            is_used BOOLEAN DEFAULT FALSE,
            expires_at TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # progressテーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id SERIAL PRIMARY KEY,
            user_id INTEGER NOT NULL,
            item_identifier VARCHAR(50) NOT NULL,
            level VARCHAR(20) NOT NULL,
            goal_index INTEGER NOT NULL,
            completed BOOLEAN DEFAULT FALSE,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, item_identifier, level, goal_index)
        )
    """)
    
    # learning_itemsテーブル
    cur.execute("""
        CREATE TABLE IF NOT EXISTS learning_items (
            id SERIAL PRIMARY KEY,
            identifier VARCHAR(50) UNIQUE NOT NULL,
            learning_prompt TEXT,
            keywords TEXT,
            grade INTEGER,
            subject VARCHAR(50),
            learning_objective TEXT,
            difficulty VARCHAR(20),
            content_types TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

def _create_tables_psycopg2(cur):
    """psycopg2でテーブル作成（フォールバック）"""
    _create_tables_psycopg3(cur)  # 同じSQL文を使用

def _load_learning_data():
    """TSVファイルからデータを読み込み"""
    try:
        tsv_path = os.path.join(os.path.dirname(__file__), 'learning_data.tsv')
        if not os.path.exists(tsv_path):
            print("[DB] WARNING: learning_data.tsv not found")
            return
        
        # 既存データを確認
        with db_manager.get_connection() as conn:
            if PSYCOPG_VERSION == 3:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM learning_items")
                    count = cur.fetchone()[0]
            else:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM learning_items")
                    count = cur.fetchone()[0]
        
        if count > 0:
            print(f"[DB] INFO: Learning items already loaded ({count} items)")
            return
        
        # TSVファイルを読み込み
        df = pd.read_csv(tsv_path, sep='\t', encoding='utf-8')
        
        # データベースに挿入
        with db_manager.get_connection() as conn:
            if PSYCOPG_VERSION == 3:
                with conn.cursor() as cur:
                    for _, row in df.iterrows():
                        cur.execute("""
                            INSERT INTO learning_items 
                            (identifier, learning_prompt, keywords, grade, subject, learning_objective, difficulty, content_types)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            row['identifier'],
                            row['learningPromptData'],
                            row['keywords'] if pd.notna(row['keywords']) else None,
                            row['grade'] if pd.notna(row['grade']) else None,
                            row['subject'] if pd.notna(row['subject']) else None,
                            row['learningObjective'] if pd.notna(row['learningObjective']) else None,
                            row['difficulty'] if pd.notna(row['difficulty']) else None,
                            row['contentCreationPrompt']
                        ))
                    conn.commit()
            else:
                # psycopg2の場合も同様の処理
                with conn.cursor() as cur:
                    for _, row in df.iterrows():
                        cur.execute("""
                            INSERT INTO learning_items 
                            (identifier, learning_prompt, keywords, grade, subject, learning_objective, difficulty, content_types)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """, (
                            row['identifier'],
                            row['learningPromptData'],
                            row['keywords'] if pd.notna(row['keywords']) else None,
                            row['grade'] if pd.notna(row['grade']) else None,
                            row['subject'] if pd.notna(row['subject']) else None,
                            row['learningObjective'] if pd.notna(row['learningObjective']) else None,
                            row['difficulty'] if pd.notna(row['difficulty']) else None,
                            row['contentCreationPrompt']
                        ))
                    conn.commit()
        
        print(f"[DB] SUCCESS: Loaded {len(df)} learning items")
        
    except Exception as e:
        print(f"[DB] ERROR: Failed to load learning data: {e}")
        import traceback
        traceback.print_exc()