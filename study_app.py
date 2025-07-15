import pandas as pd
import json
import sqlite3
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os
import google.generativeai as genai
from datetime import datetime
from auth import User, get_current_user, login_required
from dotenv import load_dotenv

# 環境変数を読み込み（開発環境用）
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# サーバー統一APIキー（環境変数から取得）
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("[STARTUP] WARNING: GEMINI_API_KEY environment variable not set. AI features will be disabled.")
else:
    print(f"[STARTUP] SUCCESS: GEMINI_API_KEY loaded successfully (length: {len(GEMINI_API_KEY)})")

# 管理者キー（環境変数から取得）
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'admin123')
print("[STARTUP] SUCCESS: ADMIN_KEY configured")

# ===== 追加: 全リクエストをログに記録するデバッグコード =====
@app.before_request
def log_request_info():
    try:
        print('-----------------------------------------------------')
        print(f"[REQUEST LOG] Path: {request.path}")
        print(f"[REQUEST LOG] Method: {request.method}")
        print(f"[REQUEST LOG] Headers: {dict(request.headers)}")
        # POSTなどのボディを持つリクエストの場合、中身をログに出力
        if request.method in ['POST', 'PUT'] and request.get_data():
            # get_data()はbytesを返すので、デコードを試みる
            try:
                print(f"[REQUEST LOG] Body: {request.get_data(as_text=True)}")
            except UnicodeDecodeError:
                print("[REQUEST LOG] Body: (Could not decode as text)")
        print('-----------------------------------------------------')
    except Exception as e:
        print(f"[REQUEST LOG] Error in logging middleware: {e}")
# ===== ここまで =====

# ===== データベース初期化関数 =====
def initialize_database():
    """アプリ起動時にデータベースを初期化"""
    db_path = 'study_app.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 既存テーブルの確認
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        existing_tables = [table[0] for table in cursor.fetchall()]
        
        # usersテーブルを作成（既存データベースと互換性を保つ）
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            is_premium INTEGER DEFAULT 0,
            premium_expires_at TEXT,
            free_usage_count INTEGER DEFAULT 0,
            last_reset_date TEXT DEFAULT (date('now')),
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)
        
        # activation_codesテーブルを作成
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS activation_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE NOT NULL,
            user_email TEXT NOT NULL,
            is_used INTEGER DEFAULT 0,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)
        
        # progressテーブルを作成
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            identifier TEXT NOT NULL,
            progress_data TEXT NOT NULL,
            updated_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
        """)
        
        # learning_itemsテーブルは既存の構造をそのまま使用
        if 'learning_items' not in existing_tables:
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS learning_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT UNIQUE NOT NULL,
                learningPromptData TEXT NOT NULL,
                contentCreationPrompt TEXT NOT NULL
            )
            """)
        
        # インデックス作成（エラーを無視）
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_progress_user_identifier ON progress(user_id, identifier)")
        except:
            pass
        
        conn.commit()
        print("[STARTUP] SUCCESS: Database tables initialized")
        
        # データ確認
        cursor.execute("SELECT COUNT(*) FROM learning_items")
        count = cursor.fetchone()[0]
        print(f"[STARTUP] INFO: Database contains {count} learning items")
            
    except Exception as e:
        print(f"[STARTUP] ERROR: Database initialization failed: {e}")
    finally:
        if conn:
            conn.close()

def import_tsv_data(cursor):
    """TSVファイルからデータをインポート"""
    try:
        tsv_file = 'learning_data.tsv'
        if os.path.exists(tsv_file):
            df = pd.read_csv(tsv_file, sep='\t')
            for _, row in df.iterrows():
                cursor.execute(
                    'INSERT OR IGNORE INTO learning_items (identifier, learningPromptData, contentCreationPrompt) VALUES (?, ?, ?)',
                    (row['identifier'], row['learningPromptData'], row['contentCreationPrompt'])
                )
        else:
            print(f"[STARTUP] WARNING: TSV file not found: {tsv_file}")
    except Exception as e:
        print(f"[STARTUP] ERROR: TSV import failed: {e}")

# ===== ここまで =====


class StudyDataViewer:
    def __init__(self, db_file_path):
        self.db_file_path = db_file_path
        self.data = None
        self.load_data()

    def load_data(self):
        """SQLiteデータベースからデータを読み込み、identifierで昇順にソートして格納"""
        try:
            conn = sqlite3.connect(self.db_file_path)
            # データベースからデータをpandas DataFrameに読み込み、identifierで昇順ソート
            self.data = pd.read_sql_query("SELECT * FROM learning_items ORDER BY identifier ASC", conn)
            conn.close()
            print(f"データベースからデータを正常に読み込みました。行数: {len(self.data)}")
        except Exception as e:
            print(f"データベース読み込みエラー: {e}")
            self.data = None
    
    def get_identifiers(self):
        """利用可能な識別子のリストを取得"""
        if self.data is not None:
            return self.data['identifier'].tolist()
        return []
    
    def get_all_content_with_subjects(self):
        """全てのコンテンツを教科ごとに分類して取得"""
        if self.data is None:
            return {}
        
        content_by_subject = {}
        # self.dataは既にidentifierでソート済み
        # groupbyのsort=Falseで、元のデータフレームの順序を維持したままグループ化
        for subject, group in self.data.groupby('subject', sort=False):
            items = group.to_dict('records')
            # キーワードと合計ゴール数を計算して追加
            for item in items:
                item['keywords'] = json.loads(item['keywords'])
                try:
                    content_data = json.loads(item['content_types'])
                    progress_tracking = content_data.get('progressTracking', {})
                    beginner_goals = len(progress_tracking.get('beginnerGoals', []))
                    intermediate_goals = len(progress_tracking.get('intermediateGoals', []))
                    advanced_goals = len(progress_tracking.get('advancedGoals', []))
                    item['total_goals'] = beginner_goals + intermediate_goals + advanced_goals
                except (json.JSONDecodeError, KeyError):
                    item['total_goals'] = 0 # パース失敗時は0
            content_by_subject[subject] = items
                
        return content_by_subject
    
    def get_subjects(self):
        """利用可能な教科のリストを取得"""
        content_by_subject = self.get_all_content_with_subjects()
        return list(content_by_subject.keys())
    
    def get_content_by_id(self, identifier):
        """指定された識別子の内容を取得"""
        if self.data is None:
            return None
        
        # 識別子で行を検索
        row = self.data[self.data['identifier'] == identifier]
        
        if row.empty:
            return None
        
        try:
            # 変更後: DataFrameから直接データを取得し、必要なJSONをパース
            learning_prompt_data = {
                'learningPrompt': row.iloc[0]['learning_prompt'],
                'keywords': json.loads(row.iloc[0]['keywords']),
                'grade': row.iloc[0]['grade'],
                'subject': row.iloc[0]['subject'],
                'learningObjective': row.iloc[0]['learning_objective'],
                'difficulty': row.iloc[0]['difficulty']
            }
            content_creation_prompt = json.loads(row.iloc[0]['content_types'])
            
            return {
                'identifier': identifier,
                'learningPromptData': learning_prompt_data,
                'contentCreationPrompt': content_creation_prompt
            }
        except (json.JSONDecodeError, KeyError) as e:
            print(f"データ解析エラー (ID: {identifier}): {e}")
            return None

# アプリ起動時にデータベースを初期化（既存DBファイルがある場合はスキップ）
if not os.path.exists('study_app.db') or os.path.getsize('study_app.db') < 1000:
    print("[STARTUP] INFO: Initializing new database...")
    initialize_database()
else:
    print("[STARTUP] INFO: Using existing database file")

# グローバルインスタンス
viewer = StudyDataViewer('study_app.db')

@app.route('/')
def index():
    """メインページ"""
    user = get_current_user()
    
    # 未ログイン時は認証画面にリダイレクト
    if not user:
        return redirect(url_for('login'))
    
    content_by_subject = viewer.get_all_content_with_subjects()
    subjects = viewer.get_subjects()
    return render_template('index.html', content_by_subject=content_by_subject, subjects=subjects)

@app.route('/api/content/<identifier>')
def get_content(identifier):
    """API: 指定されたIDのコンテンツを取得"""
    content = viewer.get_content_by_id(identifier)
    if content:
        return jsonify(content)
    else:
        return jsonify({'error': 'Content not found'}), 404

@app.route('/content/<identifier>')
@login_required
def view_content(identifier):
    """コンテンツ表示ページ"""
    content = viewer.get_content_by_id(identifier)
    if content:
        return render_template('content.html', content=content)
    else:
        return "コンテンツが見つかりません", 404

@app.route('/api/test-api-key', methods=['POST'])
def test_api_key():
    """APIキーの有効性をテスト"""
    try:
        data = request.get_json()
        api_key = data.get('api_key')
        
        if not api_key:
            return jsonify({'success': False, 'error': 'APIキーが設定されていません'}), 400
        
        # Gemini APIキーをテスト
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 簡単なテストプロンプト
        response = model.generate_content("Hello")
        
        if response and response.text:
            return jsonify({'success': True, 'message': 'APIキーは有効です'})
        else:
            return jsonify({'success': False, 'error': 'APIからの応答が無効です'}), 400
            
    except Exception as e:
        error_message = str(e)
        print(f"API Test Error: {error_message}")  # デバッグ用
        
        if "API_KEY_INVALID" in error_message or "invalid" in error_message.lower():
            return jsonify({'success': False, 'error': 'APIキーが無効です'}), 400
        elif "QUOTA_EXCEEDED" in error_message or "quota" in error_message.lower():
            return jsonify({'success': False, 'error': 'APIの使用量制限に達しています'}), 400
        elif "permission" in error_message.lower() or "forbidden" in error_message.lower():
            return jsonify({'success': False, 'error': 'APIキーに必要な権限がありません'}), 400
        else:
            return jsonify({'success': False, 'error': f'APIテストエラー: {error_message}'}), 500

@app.route('/api/progress-stats', methods=['GET'])
def get_progress_stats():
    """全ての学習項目の進捗統計情報を取得"""
    try:
        if viewer.data is None:
            return jsonify({'success': False, 'error': 'データが読み込まれていません'}), 500
        
        total_identifiers = len(viewer.data)
        total_goals = 0
        
        # 各項目のゴール数を計算
        for _, row in viewer.data.iterrows():
            try:
                content_data = json.loads(row['contentCreationPrompt'])
                progress_tracking = content_data.get('progressTracking', {})
                
                beginner_goals = len(progress_tracking.get('beginnerGoals', []))
                intermediate_goals = len(progress_tracking.get('intermediateGoals', []))
                advanced_goals = len(progress_tracking.get('advancedGoals', []))
                
                total_goals += beginner_goals + intermediate_goals + advanced_goals
                
            except (json.JSONDecodeError, KeyError) as e:
                print(f"進捗データ解析エラー (ID: {row.get('identifier', 'unknown')}): {e}")
                continue
        
        return jsonify({
            'success': True,
            'totalIdentifiers': total_identifiers,
            'totalGoals': total_goals
        })
        
    except Exception as e:
        print(f"進捗統計取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/<user_id>', methods=['GET'])
def get_progress(user_id):
    """指定されたユーザーの進捗データを取得"""
    try:
        conn = sqlite3.connect(viewer.db_file_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM progress WHERE user_id = ?", (user_id,))
        rows = cursor.fetchall()
        
        progress_data = [dict(row) for row in rows]
        
        conn.close()
        
        return jsonify({'success': True, 'progress': progress_data})
        
    except Exception as e:
        print(f"進捗データ取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/update', methods=['POST'])
def update_progress():
    """進捗データを更新（保存）"""
    try:
        data = request.get_json()
        print(f"[DEBUG] /api/progress/update received: {data}") # デバッグログ

        user_id = data.get('userId')
        item_identifier = data.get('itemIdentifier')
        level = data.get('level')
        goal_index = data.get('goalIndex')
        completed = data.get('completed')

        if not all([user_id, item_identifier, level, goal_index is not None, completed is not None]):
            print(f"[DEBUG] Parameter validation failed for: {data}") # デバッグログ
            return jsonify({'success': False, 'error': '必要なパラメータが不足しています'}), 400

        conn = sqlite3.connect(viewer.db_file_path)
        cursor = conn.cursor()

        sql = """
            INSERT INTO progress (user_id, item_identifier, level, goal_index, completed, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(user_id, item_identifier, level, goal_index) 
            DO UPDATE SET completed = excluded.completed, updated_at = excluded.updated_at
        """
        params = (user_id, item_identifier, level, goal_index, 1 if completed else 0, datetime.now().isoformat())
        
        print(f"[DEBUG] Executing SQL: {sql} with params {params}") # デバッグログ
        cursor.execute(sql, params)

        conn.commit()
        conn.close()

        print("[DEBUG] Progress update successful.") # デバッグログ
        return jsonify({'success': True, 'message': '進捗を更新しました'})

    except Exception as e:
        import traceback
        print(f"[ERROR] Progress update failed: {e}")
        traceback.print_exc() # スタックトレースをコンソールに出力
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/ai-generate', methods=['POST'])
@login_required
def ai_generate():
    """AIプロンプトを実行して結果を取得（利用制限付き）"""
    print(f"[DEBUG] AI API called - Request data: {request.get_json()}")
    try:
        # 現在のユーザーを取得
        user = get_current_user()
        if not user:
            return jsonify({'success': False, 'error': 'ログインが必要です'}), 401
        
        # 利用制限チェック
        if not user.check_usage_limit():
            return jsonify({
                'success': False,
                'error': 'USAGE_LIMIT_EXCEEDED',
                'message': f'無料利用回数（30回/月）を超過しました。現在の利用回数: {user.free_usage_count}/30',
                'upgrade_url': 'https://your-website.com/premium'
            }), 429
        
        data = request.get_json()
        prompt = data.get('prompt')
        content_type = data.get('content_type', '')
        context = data.get('context', {})  # コンテキスト情報を追加
        
        if not prompt:
            return jsonify({'success': False, 'error': 'プロンプトが提供されていません'}), 400
        
        # サーバー統一APIキーを使用
        print(f"[DEBUG] GEMINI_API_KEY exists: {bool(GEMINI_API_KEY)}")
        if not GEMINI_API_KEY:
            print("[ERROR] GEMINI_API_KEY is not set")
            return jsonify({'success': False, 'error': 'サーバーのAPIキーが設定されていません'}), 500
        
        # Gemini APIを設定
        print(f"[DEBUG] Using API key: {GEMINI_API_KEY[:10]}...{GEMINI_API_KEY[-5:]}")
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 基本的な優しいトーンの設定
        base_tone = """
あなたは不登校の子どもたちをサポートする優しい教育アシスタントです。
常に温かく、理解のある態度で接し、プレッシャーを与えずに学習をサポートしてください。
子どもたちのペースを尊重し、小さな進歩も褒めて励ましてください。
        """
        
        # コンテキストに基づいてプロンプトを構築
        if context.get('page_type') == 'content':
            # content画面用のコンテキスト情報
            learning_objective = context.get('learning_objective', '')
            subject = context.get('subject', '')
            grade = context.get('grade', '')
            keywords = context.get('keywords', [])
            beginner_goals = context.get('beginner_goals', [])
            intermediate_goals = context.get('intermediate_goals', [])
            advanced_goals = context.get('advanced_goals', [])
            
            context_info = f"""
【現在の学習内容】
• 教科: {subject}
• 学年: {grade}年生
• 学習目標: {learning_objective}
• キーワード: {', '.join(keywords)}

【学習ゴール】
初心者レベル: {', '.join(beginner_goals)}
中級者レベル: {', '.join(intermediate_goals)}
上級者レベル: {', '.join(advanced_goals)}
            """
            
            enhanced_prompt = f"""
{base_tone}

{context_info}

コンテンツタイプ: {content_type}

{prompt}

上記の学習内容とゴールを理解した上で、以下の観点から優しくアドバイスを提供してください：
1. この学習内容に特化した具体的なアプローチ
2. 必要な材料やツール（家庭にあるものを中心に）
3. 無理をしないで進めるコツ
4. 小さな達成感を味わえる工夫
5. 学年に適した楽しい要素

あなたならきっとできます！一歩ずつ、自分のペースで進めていきましょう。
            """
        else:
            # ホーム画面用（汎用的な優しいメッセージ）
            enhanced_prompt = f"""
{base_tone}

{prompt}

あなたは学習について相談された優しい先生です。以下の点を心がけて回答してください：
1. 無理をしないことの大切さを伝える
2. 小さな一歩でも価値があることを伝える
3. 具体的で実践しやすいアドバイス
4. 励ましの言葉を忘れずに

学習は競争ではありません。あなた自身のペースで、興味のあることから始めてみましょう。
            """
        
        # AI生成実行
        response = model.generate_content(enhanced_prompt)
        
        if response and response.text:
            # 成功時に利用回数をカウントアップ
            user.increment_usage_count()
            
            return jsonify({
                'success': True,
                'result': response.text,
                'content_type': content_type,
                'timestamp': datetime.now().isoformat(),
                'usage_count': user.free_usage_count,
                'usage_limit': 30
            })
        else:
            return jsonify({'success': False, 'error': 'AIからの応答が空です'}), 500
            
    except Exception as e:
        error_message = str(e)
        print(f"[ERROR] AI Generation Error: {error_message}")  # デバッグ用
        import traceback
        traceback.print_exc()  # スタックトレースを表示
        
        if "API_KEY_INVALID" in error_message or "invalid" in error_message.lower():
            return jsonify({'success': False, 'error': 'APIキーが無効です'}), 400
        elif "QUOTA_EXCEEDED" in error_message or "quota" in error_message.lower():
            return jsonify({'success': False, 'error': 'APIの使用量制限に達しています'}), 429
        elif "SAFETY" in error_message or "safety" in error_message.lower():
            return jsonify({'success': False, 'error': 'コンテンツがAIの安全性フィルターに引っかかりました'}), 400
        elif "permission" in error_message.lower() or "forbidden" in error_message.lower():
            return jsonify({'success': False, 'error': 'APIキーに必要な権限がありません'}), 400
        else:
            return jsonify({'success': False, 'error': f'AI生成エラー: {error_message}'}), 500

# ===== 認証エンドポイント =====

@app.route('/login', methods=['GET', 'POST'])
def login():
    """ログイン処理"""
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'メールアドレスとパスワードは必須です'}), 400
        
        if User.verify_password(email, password):
            user = User.get_by_email(email)
            if user:
                session['user_id'] = user.id
                return jsonify({'success': True, 'user': {'id': user.id, 'email': user.email}})
        
        return jsonify({'success': False, 'error': 'メールアドレスまたはパスワードが間違っています'}), 401
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    """ユーザー登録処理"""
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'success': False, 'error': 'メールアドレスとパスワードは必須です'}), 400
        
        if len(password) < 6:
            return jsonify({'success': False, 'error': 'パスワードは6文字以上で設定してください'}), 400
        
        user = User.create(email, password)
        if user:
            session['user_id'] = user.id
            return jsonify({'success': True, 'user': {'id': user.id, 'email': user.email}})
        else:
            return jsonify({'success': False, 'error': 'このメールアドレスは既に使用されています'}), 400
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    """ログアウト処理"""
    session.pop('user_id', None)
    return redirect(url_for('index'))

@app.route('/admin')
def admin():
    """管理者画面"""
    return render_template('admin.html')

@app.route('/api/current-user')
def current_user():
    """現在のユーザー情報を取得"""
    user = get_current_user()
    if user:
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'is_premium': user.is_premium,
                'free_usage_count': user.free_usage_count,
                'usage_limit': 30
            }
        })
    
    return jsonify({'success': False, 'error': 'ログインしていません'}), 401

@app.route('/api/generate-activation-code', methods=['POST'])
def generate_activation_code():
    """管理者用：認証コード生成"""
    data = request.get_json()
    admin_key = data.get('admin_key')
    user_email = data.get('user_email')
    expires_days = data.get('expires_days', 365)  # デフォルト1年
    
    # 管理者認証
    if admin_key != ADMIN_KEY:
        return jsonify({'success': False, 'error': '管理者権限が必要です'}), 403
    
    if not user_email:
        return jsonify({'success': False, 'error': 'ユーザーメールアドレスが必要です'}), 400
    
    try:
        import secrets
        import string
        from datetime import timedelta
        
        # 12文字のランダムコード生成
        code = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(12))
        
        # 有効期限設定
        expires_at = (datetime.now() + timedelta(days=expires_days)).isoformat()
        
        # データベースに保存
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO activation_codes (code, user_email, expires_at)
            VALUES (?, ?, ?)
        """, (code, user_email, expires_at))
        
        conn.commit()
        conn.close()
        
        return jsonify({
            'success': True,
            'activation_code': code,
            'user_email': user_email,
            'expires_at': expires_at,
            'message': f'認証コード「{code}」を生成しました'
        })
        
    except Exception as e:
        print(f"認証コード生成エラー: {e}")
        return jsonify({'success': False, 'error': '認証コード生成に失敗しました'}), 500

@app.route('/api/revoke-premium', methods=['POST'])
def revoke_premium():
    """管理者用：プレミアム状態を解除（キャンセル処理）"""
    data = request.get_json()
    admin_key = data.get('admin_key')
    user_email = data.get('user_email')
    
    # 管理者認証
    if admin_key != ADMIN_KEY:
        return jsonify({'success': False, 'error': '管理者権限が必要です'}), 403
    
    if not user_email:
        return jsonify({'success': False, 'error': 'ユーザーメールアドレスが必要です'}), 400
    
    try:
        # ユーザーを取得
        from auth import User
        user = User.get_by_email(user_email)
        
        if not user:
            return jsonify({'success': False, 'error': 'ユーザーが見つかりません'}), 404
        
        if not user.is_premium:
            return jsonify({'success': False, 'error': 'このユーザーはプレミアムではありません'}), 400
        
        # プレミアム状態を解除
        user.revoke_premium()
        
        return jsonify({
            'success': True,
            'user_email': user_email,
            'message': f'ユーザー「{user_email}」のプレミアム状態を解除しました'
        })
        
    except Exception as e:
        print(f"プレミアム解除エラー: {e}")
        return jsonify({'success': False, 'error': 'プレミアム解除に失敗しました'}), 500

@app.route('/api/activate-premium', methods=['POST'])
@login_required
def activate_premium():
    """プレミアムアカウントを有効化"""
    data = request.get_json()
    activation_code = data.get('activation_code')
    
    if not activation_code:
        return jsonify({'success': False, 'error': '認証コードが必要です'}), 400
    
    user = get_current_user()
    if user.activate_premium(activation_code):
        return jsonify({'success': True, 'message': 'プレミアムアカウントが有効化されました'})
    else:
        return jsonify({'success': False, 'error': '認証コードが無効または期限切れです'}), 400

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)