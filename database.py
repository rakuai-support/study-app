#!/usr/bin/env python3
"""
psycopg (v3) 対応データベース管理モジュール
PostgreSQL対応 - 最新のpsycopg v3を使用
"""

import os
import pandas as pd
import json
from dotenv import load_dotenv

# psycopg v3のみを使用
import psycopg
from psycopg.rows import dict_row
PSYCOPG_VERSION = 3

# ConnectionPoolのインポート（フォールバック付き）
try:
    from psycopg.pool import ConnectionPool
    print("[DB] INFO: Using psycopg v3 with ConnectionPool")
except ImportError:
    print("[DB] WARNING: psycopg.pool not available, using direct connections")
    ConnectionPool = None

# 環境変数読み込み
load_dotenv()

# グローバル接続プール（アプリケーション起動時に1回だけ作成）
_global_connection_pool = None
_global_db_type = None

def initialize_global_connection_pool():
    """グローバル接続プールの初期化（1回のみ実行）"""
    global _global_connection_pool, _global_db_type
    
    if _global_connection_pool is not None:
        print("[DB] INFO: Global connection pool already exists")
        return
    
    database_url = os.getenv('DATABASE_URL')
    print(f"[DB] INFO: Initializing global connection pool")
    
    if database_url and 'postgresql://' in database_url:
        try:
            if ConnectionPool:
                print("[DB] INFO: Creating global PostgreSQL connection pool")
                _global_connection_pool = ConnectionPool(
                    database_url,
                    min_size=2,
                    max_size=20,
                    max_idle=600,
                    max_lifetime=7200
                )
                _global_db_type = 'postgresql'
                print("[DB] SUCCESS: Global PostgreSQL connection pool created")
            else:
                print("[DB] WARNING: ConnectionPool not available")
                _global_connection_pool = database_url
                _global_db_type = 'postgresql_direct'
        except Exception as e:
            print(f"[DB] ERROR: Failed to create global connection pool: {e}")
            _global_connection_pool = None
            _global_db_type = None

class DatabaseManager:
    """グローバル接続プールを使用したデータベース管理クラス"""
    
    def __init__(self):
        # グローバル接続プールがまだ初期化されていない場合は初期化
        if _global_connection_pool is None:
            initialize_global_connection_pool()
    
    @property
    def connection_pool(self):
        """グローバル接続プールへのアクセス"""
        return _global_connection_pool
    
    @property
    def db_type(self):
        """データベースタイプへのアクセス"""
        return _global_db_type
    
    def get_connection(self):
        """データベース接続を取得"""
        if _global_db_type == 'postgresql':
            if _global_connection_pool:
                # ConnectionPoolから接続を取得
                return _global_connection_pool.connection()
            else:
                raise Exception("Database connection pool not available")
        elif _global_db_type == 'postgresql_direct':
            # 直接接続
            return psycopg.connect(_global_connection_pool)  # connection_poolにURLが格納されている
        else:
            raise Exception("Database connection not available - PostgreSQL required")
    
    def return_connection(self, conn):
        """接続を返却"""
        if conn:
            conn.close()
    
    def execute_query(self, query, params=None):
        """クエリを実行"""
        with self.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                return cur.fetchall()
    
    def execute_single(self, query, params=None):
        """単一行を実行"""
        with self.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(query, params)
                return cur.fetchone()

# グローバル接続プールの初期化
initialize_global_connection_pool()

# グローバルインスタンス
db_manager = DatabaseManager()

def initialize_database():
    """データベースの初期化"""
    if db_manager.db_type != 'postgresql':
        print("[DB] WARNING: Database connection not available, skipping initialization")
        return False
    
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                _create_tables_psycopg3(cur)
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

# psycopg v3のみを使用するため、psycopg2関数は削除

def _load_learning_data():
    """TSVファイルからデータを読み込み"""
    try:
        tsv_path = os.path.join(os.path.dirname(__file__), 'learning_data.tsv')
        if not os.path.exists(tsv_path):
            print("[DB] WARNING: learning_data.tsv not found")
            return
        
        # 既存データを確認
        with db_manager.get_connection() as conn:
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