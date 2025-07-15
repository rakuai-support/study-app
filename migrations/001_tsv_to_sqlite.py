import pandas as pd
import sqlite3
import json

# --- 設定 ---
TSV_FILE_PATH = r'C:\Users\utaka\claude\studyアプリ\learning_data.tsv'
DB_FILE_PATH = 'study_app.db' # DBはアプリのルートディレクトリに作成
ITEMS_TABLE_NAME = 'learning_items'
PROGRESS_TABLE_NAME = 'progress'

print(f"データベース '{DB_FILE_PATH}' を作成しています...")
conn = sqlite3.connect(DB_FILE_PATH)
cursor = conn.cursor()

# --- learning_items テーブル作成 ---
cursor.execute(f"DROP TABLE IF EXISTS {ITEMS_TABLE_NAME}")
cursor.execute(f'''
CREATE TABLE {ITEMS_TABLE_NAME} (
    identifier TEXT PRIMARY KEY,
    subject TEXT,
    grade INTEGER,
    learning_objective TEXT,
    learning_prompt TEXT,
    keywords TEXT,
    difficulty TEXT,
    content_types TEXT
)
''')
print(f"テーブル '{ITEMS_TABLE_NAME}' を作成しました。")

# --- progress テーブル作成 ---
cursor.execute(f"DROP TABLE IF EXISTS {PROGRESS_TABLE_NAME}")
cursor.execute(f'''
CREATE TABLE {PROGRESS_TABLE_NAME} (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    item_identifier TEXT NOT NULL,
    level TEXT NOT NULL,
    goal_index INTEGER NOT NULL,
    completed INTEGER DEFAULT 0,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (item_identifier) REFERENCES {ITEMS_TABLE_NAME}(identifier)
)
''')
print(f"テーブル '{PROGRESS_TABLE_NAME}' を作成しました。")


# --- TSVデータの読み込みと挿入 ---
print(f"TSVファイル '{TSV_FILE_PATH}' を読み込んでいます...")
try:
    df = pd.read_csv(TSV_FILE_PATH, sep='\t', encoding='utf-8')
    print(f"{len(df)}件のデータを読み込みました。")
except Exception as e:
    print(f"エラー: TSVファイルの読み込みに失敗しました。 {e}")
    exit()

print("データをデータベースに挿入しています...")
for _, row in df.iterrows():
    try:
        learning_data = json.loads(row['learningPromptData'])
        content_data_str = row['contentCreationPrompt'] # これはJSON文字列のまま保存

        cursor.execute(
            f"""INSERT INTO {ITEMS_TABLE_NAME} (
                identifier, subject, grade, learning_objective, learning_prompt, keywords, difficulty, content_types
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                row['identifier'],
                learning_data.get('subject'),
                learning_data.get('grade'),
                learning_data.get('learningObjective'),
                learning_data.get('learningPrompt'),
                json.dumps(learning_data.get('keywords', [])), # リストをJSON文字列に
                learning_data.get('difficulty'),
                content_data_str
            )
        )
    except Exception as e:
        print(f"警告: ID {row.get('identifier')} のデータ処理中にエラーが発生しました。スキップします。エラー: {e}")
        continue

conn.commit()
conn.close()

print("データ移行が正常に完了しました。")
print(f"'{DB_FILE_PATH}' が作成されました。")
