

import sqlite3
import json
import pandas as pd
from collections import Counter

# Pandasの表示オプションを設定
pd.set_option('display.max_rows', 100)

DB_PATH = 'study_app.db'

def analyze_keywords():
    """データベース内のキーワードを分析し、結果を出力する"""
    try:
        conn = sqlite3.connect(DB_PATH)
        # pandasを使ってデータを読み込むのが効率的
        df = pd.read_sql_query("SELECT subject, keywords FROM learning_items", conn)
        conn.close()
    except Exception as e:
        print(f"データベースの読み込みに失敗しました: {e}")
        return

    print("データベースからデータを正常に読み込みました。分析を開始します...")

    # --- キーワードのパース ---
    all_keywords = []
    subject_keywords = {subject: [] for subject in df['subject'].unique()}

    for index, row in df.iterrows():
        try:
            # JSON文字列をPythonのリストに変換
            keywords = json.loads(row['keywords'])
            if isinstance(keywords, list):
                all_keywords.extend(keywords)
                subject_keywords[row['subject']].extend(keywords)
        except (json.JSONDecodeError, TypeError):
            # パースに失敗した場合はスキップ
            continue

    # --- 分析実行 ---
    print("\n" + "="*50)
    print(" キーワード分析レポート")
    print("="*50 + "\n")

    # 1. 全体のサマリー
    total_keywords_count = len(all_keywords)
    unique_keywords_count = len(set(all_keywords))
    print(f"[サマリー]")
    print(f"  - 総キーワード数（重複あり）: {total_keywords_count}")
    print(f"  - ユニークキーワード数: {unique_keywords_count}")

    # 2. 全体でのキーワード出現頻度
    overall_counts = Counter(all_keywords)
    print("\n--- 全体でのキーワード出現頻度 Top 20 ---")
    for keyword, count in overall_counts.most_common(20):
        print(f"  - {keyword}: {count}回")

    # 3. 教科別のキーワード出現頻度
    print("\n--- 教科別のキーワード出現頻度 Top 5 ---")
    for subject, keywords_list in subject_keywords.items():
        print(f"\n  【{subject}】")
        if not keywords_list:
            print("    キーワードがありませんでした。")
            continue
        subject_counts = Counter(keywords_list)
        for keyword, count in subject_counts.most_common(5):
            print(f"    - {keyword}: {count}回")

    # 4. 複数の教科で出現するキーワード
    # 各キーワードがどの教科で出現したかを記録
    keyword_to_subjects = {}
    for subject, keywords_list in subject_keywords.items():
        for keyword in set(keywords_list):
            if keyword not in keyword_to_subjects:
                keyword_to_subjects[keyword] = set()
            keyword_to_subjects[keyword].add(subject)
    
    # 2つ以上の教科で出現するキーワードを抽出
    cross_subject_keywords = {kw: subjects for kw, subjects in keyword_to_subjects.items() if len(subjects) > 1}
    # 出現教科数が多い順にソート
    sorted_cross_keywords = sorted(cross_subject_keywords.items(), key=lambda item: len(item[1]), reverse=True)

    print("\n--- 複数の教科で出現するキーワード Top 10 ---")
    print("（学習項目間の関連性を示唆します）")
    for keyword, subjects in sorted_cross_keywords[:10]:
        print(f"  - 「{keyword}」: {len(subjects)}教科 ({', '.join(sorted(list(subjects)))})")

    print("\n" + "="*50)
    print(" 分析終了")
    print("="*50 + "\n")

if __name__ == '__main__':
    analyze_keywords()

