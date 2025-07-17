#!/usr/bin/env python3
"""教科名確認スクリプト"""

import os
from dotenv import load_dotenv
from database import db_manager

# 環境変数を読み込み
load_dotenv()

def check_subjects():
    """データベースから実際の教科名を確認"""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT DISTINCT subject, COUNT(*) FROM learning_items GROUP BY subject ORDER BY subject')
                results = cur.fetchall()
                
                print('データベースの実際の教科名:')
                for subject, count in results:
                    print(f'  "{subject}" - {count}件')
                    
    except Exception as e:
        print(f'エラー: {e}')

if __name__ == '__main__':
    check_subjects()