#!/usr/bin/env python3
"""
学習データの再読み込みスクリプト
既存のlearning_itemsテーブルをクリアして、正しくsubject情報を含めて再作成
"""

import os
import sys
from dotenv import load_dotenv

# 環境変数読み込み
load_dotenv()

# プロジェクトのパスを追加
sys.path.append(os.path.dirname(__file__))

from database import db_manager

def reload_learning_data():
    """学習データを再読み込み"""
    try:
        print("[RELOAD] 学習データの再読み込みを開始...")
        
        # 既存のlearning_itemsテーブルを削除
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM learning_items")
                conn.commit()
                print("[RELOAD] 既存のlearning_itemsデータを削除しました")
        
        # 学習データを再読み込み
        from database import _load_learning_data
        _load_learning_data()
        
        # 結果を確認
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM learning_items")
                count = cur.fetchone()[0]
                print(f"[RELOAD] 再読み込み完了: {count}件の学習データ")
                
                # サンプルデータの確認
                cur.execute("SELECT identifier, subject FROM learning_items WHERE identifier = %s", ('8310213211100000',))
                result = cur.fetchone()
                if result:
                    print(f"[RELOAD] テスト用identifier確認: {result[0]} | {result[1]}")
                else:
                    print("[RELOAD] WARNING: テスト用identifierが見つかりません")
                
                # 教科別件数確認
                cur.execute("SELECT subject, COUNT(*) FROM learning_items GROUP BY subject ORDER BY subject")
                subjects = cur.fetchall()
                print("[RELOAD] 教科別件数:")
                for subject, count in subjects:
                    print(f"  {subject}: {count}件")
        
        print("[RELOAD] 学習データの再読み込みが完了しました")
        return True
        
    except Exception as e:
        print(f"[RELOAD] ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    reload_learning_data()