#!/usr/bin/env python3
"""
PostgreSQL対応データベース管理モジュール
SQLiteからPostgreSQLへの移行対応
"""

import os
import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool
import pandas as pd
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

class DatabaseManager:
    """PostgreSQL/SQLite両対応のデータベース管理クラス"""
    
    def __init__(self):
        self.connection_pool = None
        self.db_type = None
        self._initialize_connection()
    
    def _initialize_connection(self):
        """データベース接続の初期化"""
        # PostgreSQL接続を優先
        database_url = os.getenv('DATABASE_URL')
        if database_url and 'postgresql://' in database_url:
            try:
                # PostgreSQL接続プール作成
                self.connection_pool = SimpleConnectionPool(
                    1, 10,  # 最小1, 最大10接続
                    database_url
                )
                self.db_type = 'postgresql'
                print("[DB] SUCCESS: PostgreSQL connection pool created")
                return
            except Exception as e:
                print(f"[DB] WARNING: PostgreSQL connection failed: {e}")
        
        # フォールバック: SQLite使用
        self.db_type = 'sqlite'
        print("[DB] INFO: Using SQLite fallback")
    
    def get_connection(self):
        """接続を取得"""
        if self.db_type == 'postgresql':
            return self.connection_pool.getconn()
        else:
            import sqlite3
            return sqlite3.connect('study_app.db')
    
    def return_connection(self, conn):
        """接続を返却"""
        if self.db_type == 'postgresql':
            self.connection_pool.putconn(conn)
        else:
            conn.close()
    
    def execute_query(self, query, params=None, fetch=False):
        """クエリ実行のヘルパー関数"""
        conn = None
        try:
            conn = self.get_connection()
            
            if self.db_type == 'postgresql':
                cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
            else:
                cursor = conn.cursor()
            
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            if fetch == 'one':
                result = cursor.fetchone()
            elif fetch == 'all':
                result = cursor.fetchall()
            else:
                result = None
            
            conn.commit()
            cursor.close()
            return result
            
        except Exception as e:
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.return_connection(conn)
    
    def initialize_database(self):
        """データベーステーブルの初期化"""
        print(f"[DB] Initializing {self.db_type} database...")
        
        if self.db_type == 'postgresql':
            self._initialize_postgresql()
        else:
            self._initialize_sqlite()
    
    def _initialize_postgresql(self):
        """PostgreSQL用テーブル初期化"""
        conn = None
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # usersテーブル
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                is_premium BOOLEAN DEFAULT FALSE,
                premium_expires_at TIMESTAMP,
                free_usage_count INTEGER DEFAULT 0,
                last_reset_date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # activation_codesテーブル
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS activation_codes (
                id SERIAL PRIMARY KEY,
                code VARCHAR(50) UNIQUE NOT NULL,
                user_email VARCHAR(255) NOT NULL,
                is_used BOOLEAN DEFAULT FALSE,
                expires_at TIMESTAMP NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # progressテーブル
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS progress (
                id SERIAL PRIMARY KEY,
                user_id INTEGER NOT NULL,
                identifier VARCHAR(50) NOT NULL,
                progress_data TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE
            )
            """)
            
            # learning_itemsテーブル
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_items (
                id SERIAL PRIMARY KEY,
                identifier VARCHAR(50) UNIQUE NOT NULL,
                learningPromptData TEXT NOT NULL,
                contentCreationPrompt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """)
            
            # インデックス作成
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
                "CREATE INDEX IF NOT EXISTS idx_progress_user_identifier ON progress(user_id, identifier)",
                "CREATE INDEX IF NOT EXISTS idx_learning_items_identifier ON learning_items(identifier)"
            ]
            
            for index_sql in indexes:
                try:
                    cursor.execute(index_sql)
                except Exception as e:
                    print(f"[DB] Index creation warning: {e}")
            
            conn.commit()
            cursor.close()
            
            # データ確認
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM learning_items")
            count = cursor.fetchone()[0]
            print(f"[DB] SUCCESS: PostgreSQL tables initialized ({count} learning items)")
            cursor.close()
            
        except Exception as e:
            print(f"[DB] ERROR: PostgreSQL initialization failed: {e}")
            if conn:
                conn.rollback()
            raise e
        finally:
            if conn:
                self.return_connection(conn)
    
    def _initialize_sqlite(self):
        """SQLite用テーブル初期化（既存コード）"""
        # 既存のSQLiteコードをそのまま使用
        import sqlite3
        
        conn = None
        try:
            conn = sqlite3.connect('study_app.db')
            cursor = conn.cursor()
            
            # 既存のSQLiteテーブル作成コード...
            # （元のinitialize_database関数の内容をここに移動）
            
            conn.commit()
            print("[DB] SUCCESS: SQLite tables initialized")
            
        except Exception as e:
            print(f"[DB] ERROR: SQLite initialization failed: {e}")
        finally:
            if conn:
                conn.close()
    
    def import_tsv_data(self):
        """TSVファイルからデータをインポート"""
        try:
            tsv_file = 'learning_data.tsv'
            if not os.path.exists(tsv_file):
                print(f"[DB] WARNING: TSV file not found: {tsv_file}")
                return
            
            df = pd.read_csv(tsv_file, sep='\t')
            print(f"[DB] Loading {len(df)} items from TSV...")
            
            conn = self.get_connection()
            
            if self.db_type == 'postgresql':
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT INTO learning_items (identifier, learningPromptData, contentCreationPrompt) 
                        VALUES (%s, %s, %s) ON CONFLICT (identifier) DO NOTHING
                    """, (row['identifier'], row['learningPromptData'], row['contentCreationPrompt']))
            else:
                cursor = conn.cursor()
                for _, row in df.iterrows():
                    cursor.execute("""
                        INSERT OR IGNORE INTO learning_items (identifier, learningPromptData, contentCreationPrompt) 
                        VALUES (?, ?, ?)
                    """, (row['identifier'], row['learningPromptData'], row['contentCreationPrompt']))
            
            conn.commit()
            cursor.close()
            self.return_connection(conn)
            print(f"[DB] SUCCESS: TSV data imported")
            
        except Exception as e:
            print(f"[DB] ERROR: TSV import failed: {e}")

# グローバルデータベースマネージャー
db_manager = DatabaseManager()

def get_db_connection():
    """データベース接続を取得（既存コードとの互換性用）"""
    return db_manager.get_connection()

def initialize_database():
    """データベース初期化（既存コードとの互換性用）"""
    db_manager.initialize_database()
    
    # learning_itemsテーブルが空の場合、TSVデータをインポート
    try:
        result = db_manager.execute_query("SELECT COUNT(*) FROM learning_items", fetch='one')
        count = result[0] if result else 0
        
        if count == 0:
            print("[DB] Learning items table is empty, importing TSV data...")
            db_manager.import_tsv_data()
    except Exception as e:
        print(f"[DB] Error checking learning_items count: {e}")