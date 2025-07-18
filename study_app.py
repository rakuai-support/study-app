import pandas as pd
import json
import time
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash
import os
import google.generativeai as genai
from datetime import datetime
from auth import User, get_current_user, login_required
from dotenv import load_dotenv
from database import db_manager, initialize_database
from psycopg.rows import dict_row

# 環境変数を読み込み（開発環境用）
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this-in-production')

# デバッグモードとログレベル設定
app.config['DEBUG'] = True
import logging
import sys
logging.basicConfig(level=logging.INFO)
# print文のバッファリングを無効化
sys.stdout.reconfigure(line_buffering=True)
print("[STARTUP] DEBUG: Debug mode enabled, logging configured, buffering disabled")

# サーバー統一APIキー（環境変数から取得）
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

if not GEMINI_API_KEY:
    print("[STARTUP] WARNING: GEMINI_API_KEY environment variable not set. AI features will be disabled.")
else:
    print(f"[STARTUP] SUCCESS: GEMINI_API_KEY loaded successfully (length: {len(GEMINI_API_KEY)})")

# 管理者キー（環境変数から取得）
ADMIN_KEY = os.environ.get('ADMIN_KEY', 'admin123')
print("[STARTUP] SUCCESS: ADMIN_KEY configured")

# ===== 追加: 重要なリクエストのみログに記録するデバッグコード =====
@app.before_request
def log_request_info():
    try:
        # 重要なAPI エンドポイントのみログ出力
        important_paths = ['/api/ai-generate', '/api/activate-premium', '/api/progress/update', '/login', '/register']
        
        if any(request.path.startswith(path) for path in important_paths):
            print('-----------------------------------------------------')
            print(f"[REQUEST LOG] Path: {request.path}")
            print(f"[REQUEST LOG] Method: {request.method}")
            # POSTなどのボディを持つリクエストの場合、中身をログに出力
            if request.method in ['POST', 'PUT'] and request.get_data():
                try:
                    print(f"[REQUEST LOG] Body: {request.get_data(as_text=True)}")
                except UnicodeDecodeError:
                    print("[REQUEST LOG] Body: (Could not decode as text)")
            print('-----------------------------------------------------')
    except Exception as e:
        print(f"[REQUEST LOG] Error in logging middleware: {e}")
# ===== ここまで =====

# ===== データベース初期化（新しいdatabase.pyモジュールを使用） =====


class StudyDataViewer:
    def __init__(self):
        self.data = None
        self._cached_stats = None  # 統計情報のキャッシュ
        self._content_cache = {}  # コンテンツ詳細のキャッシュ
        self._subject_cache = {}  # 教科別データのキャッシュ
        self._cache_timestamp = None  # キャッシュタイムスタンプ
        self.CACHE_DURATION = 300  # 5分キャッシュ
        self.load_data()

    def load_data(self):
        """PostgreSQLデータベースからデータを読み込み、identifierで昇順にソートして格納"""
        try:
            # psycopg v3対応のデータベース操作
            with db_manager.get_connection() as conn:
                # 必要な列のみを選択してクエリを最適化
                optimized_query = """
                    SELECT identifier, learning_prompt, keywords, grade, subject, 
                           learning_objective, difficulty, content_types 
                    FROM learning_items 
                    ORDER BY identifier ASC
                """
                self.data = pd.read_sql_query(optimized_query, conn)
            
            print(f"データベースからデータを正常に読み込みました。行数: {len(self.data)}")
            
            # デバッグ: 教科リストを出力
            if self.data is not None and not self.data.empty:
                subjects = self.data['subject'].unique()
                print(f"[DEBUG] 読み込まれた教科: {list(subjects)}")
            
            # データ読み込み時に統計情報もキャッシュ
            self._calculate_stats_cache()
        except Exception as e:
            print(f"データベース読み込みエラー: {e}")
            self.data = None
            self._cached_stats = None
    
    def _calculate_stats_cache(self):
        """統計情報を計算してキャッシュに保存（起動時の1回のみ実行）"""
        if self.data is None:
            self._cached_stats = None
            return
        
        try:
            total_identifiers = len(self.data)
            total_goals = 0
            error_count = 0
            
            print(f"[STARTUP] 統計情報キャッシュを計算中... ({total_identifiers}項目)")
            
            # 各項目のゴール数を計算
            for _, row in self.data.iterrows():
                try:
                    content_data = json.loads(row['content_types'])  # 正しいカラム名
                    progress_tracking = content_data.get('progressTracking', {})
                    
                    beginner_goals = len(progress_tracking.get('beginnerGoals', []))
                    intermediate_goals = len(progress_tracking.get('intermediateGoals', []))
                    advanced_goals = len(progress_tracking.get('advancedGoals', []))
                    
                    total_goals += beginner_goals + intermediate_goals + advanced_goals
                    
                except (json.JSONDecodeError, KeyError) as e:
                    error_count += 1
                    if error_count <= 3:  # 最初の3件のみログ出力
                        print(f"[STARTUP] データ解析エラー (ID: {row.get('identifier', 'unknown')}): {e}")
                    continue
            
            self._cached_stats = {
                'totalIdentifiers': total_identifiers,
                'totalGoals': total_goals,
                'errorCount': error_count
            }
            print(f"[STARTUP] 統計キャッシュ完了: {total_identifiers}項目, {total_goals}ゴール (エラー: {error_count}件)")
            
        except Exception as e:
            print(f"[STARTUP] 統計計算エラー: {e}")
            self._cached_stats = None
    
    def get_identifiers(self):
        """利用可能な識別子のリストを取得"""
        if self.data is not None:
            return self.data['identifier'].tolist()
        return []
    
    def get_all_content_with_subjects(self):
        """全てのコンテンツを教科ごとに分類して取得（identifier順でキャッシュ付き）"""
        if self.data is None:
            return {}
        
        # キャッシュチェック
        now = time.time()
        if (self._subject_cache and self._cache_timestamp and 
            (now - self._cache_timestamp) < self.CACHE_DURATION):
            return self._subject_cache
        
        content_by_subject = {}
        # self.dataは既にidentifierでソート済み
        # groupbyのsort=Falseで、元のデータフレームの順序を維持したままグループ化
        for subject, group in self.data.groupby('subject', sort=False):
            items = group.to_dict('records')
            # キーワードと合計ゴール数を計算して追加
            for item in items:
                # NaN値を適切にハンドリング
                for key, value in item.items():
                    if pd.isna(value):
                        if key == 'grade':
                            item[key] = 0  # gradeのNaNは0に変換
                        else:
                            item[key] = None  # その他のNaNはNoneに変換
                
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
        
        # identifier順で並び替えるため、教科順序を取得
        subject_order = self.get_subjects()
        
        # 順序通りに並び替えた辞書を作成
        ordered_content = {}
        for subject in subject_order:
            if subject in content_by_subject:
                ordered_content[subject] = content_by_subject[subject]
        
        # キャッシュに保存
        self._subject_cache = ordered_content
        self._cache_timestamp = now
                
        return ordered_content
    
    def get_subjects(self):
        """利用可能な教科のリストを取得（identifier順で取得）"""
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # identifier順（学習指導要領の順序）で教科を取得
                    cur.execute("""
                        SELECT subject, MIN(identifier) as first_identifier
                        FROM learning_items 
                        GROUP BY subject 
                        ORDER BY MIN(identifier) ASC
                    """)
                    subjects = [row[0] for row in cur.fetchall()]
                    return subjects
        except Exception as e:
            print(f"[ERROR] 教科リスト取得エラー: {e}")
            # フォールバック: identifier順の固定リスト
            return ['国語', '社会', '数学', '理科', '音楽', '英語', '技術・家庭', '保健体育', '美術', '道徳']
    
    def get_content_by_id(self, identifier):
        """指定された識別子の内容を取得（キャッシュ付き）"""
        if self.data is None:
            return None
        
        # キャッシュチェック
        if identifier in self._content_cache:
            return self._content_cache[identifier]
        
        # 識別子で行を検索
        row = self.data[self.data['identifier'] == identifier]
        
        if row.empty:
            return None
        
        try:
            # 変更後: DataFrameから直接データを取得し、必要なJSONをパース
            row_data = row.iloc[0]
            
            # NaN値を適切にハンドリング
            grade = row_data['grade']
            if pd.isna(grade):
                grade = 0
            
            learning_prompt_data = {
                'learningPrompt': row_data['learning_prompt'],
                'keywords': json.loads(row_data['keywords']),
                'grade': grade,
                'subject': row_data['subject'],
                'learningObjective': row_data['learning_objective'],
                'difficulty': row_data['difficulty']
            }
            content_creation_prompt = json.loads(row_data['content_types'])
            
            result = {
                'identifier': identifier,
                'learningPromptData': learning_prompt_data,
                'contentCreationPrompt': content_creation_prompt
            }
            
            # キャッシュに保存
            self._content_cache[identifier] = result
            return result
            
        except (json.JSONDecodeError, KeyError) as e:
            print(f"データ解析エラー (ID: {identifier}): {e}")
            return None

# PostgreSQLデータベースを初期化
print("[STARTUP] INFO: Initializing PostgreSQL database...")
initialize_database()

# グローバルインスタンス
viewer = StudyDataViewer()

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

@app.route('/api/learning-item/<identifier>')
def get_learning_item(identifier):
    """API: 指定されたIDの学習項目情報（教科名等）を取得"""
    try:
        with db_manager.get_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    "SELECT identifier, subject FROM learning_items WHERE identifier = %s",
                    (identifier,)
                )
                item = cur.fetchone()
                
                if item:
                    return jsonify({
                        'identifier': item['identifier'],
                        'subject': item['subject']
                    })
                else:
                    return jsonify({'error': 'Learning item not found'}), 404
                    
    except Exception as e:
        print(f"[ERROR] 学習項目取得エラー: {e}")
        return jsonify({'error': 'Database error'}), 500

@app.route('/api/subjects')
def get_subjects_api():
    """API: 利用可能な教科のリストを取得"""
    try:
        subjects = viewer.get_subjects()
        return jsonify(subjects)
    except Exception as e:
        print(f"[ERROR] 教科リスト取得エラー: {e}")
        return jsonify(['国語', '算数', '数学', '理科', '社会', '英語', '道徳', '音楽', '美術', '保健体育', '技術・家庭']), 500

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
    """全ての学習項目の進捗統計情報を取得（キャッシュ使用）"""
    try:
        # 教科別データを取得
        items_by_subject = viewer.get_all_content_with_subjects()
        
        # キャッシュが存在する場合はそれを返す
        if viewer._cached_stats:
            return jsonify({
                'success': True,
                'totalIdentifiers': viewer._cached_stats['totalIdentifiers'],
                'totalGoals': viewer._cached_stats['totalGoals'],
                'items_by_subject': items_by_subject,
                'cached': True  # キャッシュ使用であることを示す
            })
        
        # キャッシュが無い場合（エラー時のフォールバック）
        if viewer.data is None:
            return jsonify({'success': False, 'error': 'データが読み込まれていません'}), 500
        
        print("[WARNING] 統計キャッシュが無いため、フォールバック処理を実行")
        return jsonify({
            'success': True,
            'totalIdentifiers': len(viewer.data),
            'totalGoals': 0,  # フォールバック時は簡易計算
            'items_by_subject': items_by_subject,
            'cached': False
        })
        
    except Exception as e:
        print(f"進捗統計取得エラー: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/progress/<user_id>', methods=['GET'])
def get_progress(user_id):
    """指定されたユーザーの進捗データを取得"""
    try:
        progress_data = db_manager.execute_query("SELECT * FROM progress WHERE user_id = %s", (user_id,))
        
        # psycopg v3では辞書型として返される
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

        # PostgreSQL用UPSERT構文
        sql = """
            INSERT INTO progress (user_id, item_identifier, level, goal_index, completed, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, item_identifier, level, goal_index) 
            DO UPDATE SET completed = EXCLUDED.completed, updated_at = EXCLUDED.updated_at
        """
        params = (user_id, item_identifier, level, goal_index, completed, datetime.now())
        
        print(f"[DEBUG] Executing SQL: {sql} with params {params}") # デバッグログ
        
        # psycopg v3対応のデータベース操作（トランザクション保護付き）
        with db_manager.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute(sql, params)
                    conn.commit()
                    print("[DEBUG] Individual progress update committed")
            except Exception as e:
                conn.rollback()
                print(f"[ERROR] Individual update transaction rolled back: {e}")
                raise

        print("[DEBUG] Progress update successful.") # デバッグログ
        return jsonify({'success': True, 'message': '進捗を更新しました'})

    except Exception as e:
        import traceback
        print(f"[ERROR] Progress update failed: {e}")
        traceback.print_exc() # スタックトレースをコンソールに出力
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/progress/batch-update', methods=['POST'])
def batch_update_progress():
    """進捗データをバッチで更新（パフォーマンス最適化）"""
    try:
        data = request.get_json()
        print(f"[DEBUG] /api/progress/batch-update received: {len(data.get('updates', []))} updates") # デバッグログ

        user_id = data.get('userId')
        updates = data.get('updates', [])

        if not user_id or not updates:
            return jsonify({'success': False, 'error': '必要なパラメータが不足しています'}), 400

        # バッチ処理用のSQL（PostgreSQL UPSERT）
        sql = """
            INSERT INTO progress (user_id, item_identifier, level, goal_index, completed, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id, item_identifier, level, goal_index) 
            DO UPDATE SET completed = EXCLUDED.completed, updated_at = EXCLUDED.updated_at
        """
        
        # バッチパラメータ準備
        current_time = datetime.now()
        batch_params = []
        
        for update in updates:
            item_identifier = update.get('identifier')
            level = update.get('level')
            goal_index = update.get('goalIndex')
            completed = update.get('completed')
            
            if not all([item_identifier, level, goal_index is not None, completed is not None]):
                print(f"[WARNING] Skipping invalid update: {update}")
                continue
                
            batch_params.append((user_id, item_identifier, level, goal_index, completed, current_time))
        
        if not batch_params:
            return jsonify({'success': False, 'error': '有効な更新データがありません'}), 400
        
        print(f"[DEBUG] Executing batch update: {len(batch_params)} records")
        
        # バッチでDBに書き込み（トランザクション保護付き）
        with db_manager.get_connection() as conn:
            try:
                with conn.cursor() as cursor:
                    cursor.executemany(sql, batch_params)
                    conn.commit()
                    print(f"[DEBUG] Transaction committed: {len(batch_params)} records")
            except Exception as e:
                conn.rollback()
                print(f"[ERROR] Transaction rolled back due to: {e}")
                raise

        print(f"[DEBUG] Batch progress update successful: {len(batch_params)} records updated")
        return jsonify({
            'success': True, 
            'message': f'{len(batch_params)}件の進捗を更新しました',
            'updated_count': len(batch_params)
        })

    except Exception as e:
        import traceback
        print(f"[ERROR] Batch progress update failed: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/debug/session', methods=['GET'])
def debug_session():
    """セッション情報のデバッグ"""
    try:
        print("[DEBUG] debug_session endpoint called")  # コンソールログ
        user = get_current_user()
        print(f"[DEBUG] Current user in debug: {user}")  # コンソールログ
        return jsonify({
            'session_user_id': session.get('user_id'),
            'user_found': user is not None,
            'user_email': user.email if user else None,
            'user_id': user.id if user else None,
            'is_premium': user.is_premium if user else None,
            'usage_count': user.free_usage_count if user else None
        })
    except Exception as e:
        print(f"[DEBUG] Error in debug_session: {e}")  # コンソールログ
        return jsonify({'error': str(e)})

@app.route('/api/test-log', methods=['GET'])
def test_log():
    """ログテスト用"""
    import sys
    print("TEST LOG: This message should appear in console", flush=True)
    sys.stdout.flush()
    app.logger.info("APP LOGGER: This is from Flask logger")
    return jsonify({'message': 'Check console for log message', 'timestamp': datetime.now().isoformat()})

@app.route('/api/ai-generate-test', methods=['POST'])
def ai_generate_test():
    """AI APIテスト版（認証なし・デバッグ用）"""
    print(f"[DEBUG] AI TEST API called - Request data: {request.get_json()}")
    try:
        data = request.get_json()
        prompt = data.get('prompt', 'テストプロンプト')
        
        # APIキー確認
        if not GEMINI_API_KEY:
            print("[ERROR] GEMINI_API_KEY is not set")
            return jsonify({'success': False, 'error': 'APIキーが設定されていません'}), 500
        
        # Gemini API実行
        genai.configure(api_key=GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')
        response = model.generate_content(prompt)
        
        if response and response.text:
            return jsonify({
                'success': True,
                'result': response.text,
                'debug': 'Test API successful'
            })
        else:
            return jsonify({'success': False, 'error': 'Empty response'}), 500
            
    except Exception as e:
        print(f"[ERROR] AI Test Error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/ai-generate', methods=['POST'])
@login_required
def ai_generate():
    """AIプロンプトを実行して結果を取得（利用制限付き）"""
    print(f"[DEBUG] AI API called - Request data: {request.get_json()}")
    print(f"[DEBUG] Session user_id: {session.get('user_id')}")
    try:
        # 現在のユーザーを取得
        user = get_current_user()
        print(f"[DEBUG] Current user: {user}")
        if not user:
            print("[DEBUG] No user found in session")
            return jsonify({'success': False, 'error': 'ログインが必要です'}), 401
        
        print(f"[DEBUG] User found: {user.email}, Premium: {user.is_premium}, Usage: {user.free_usage_count}/30")
        
        # 利用制限チェック
        usage_check = user.check_usage_limit()
        print(f"[DEBUG] Usage limit check result: {usage_check}")
        if not usage_check:
            return jsonify({
                'success': False,
                'error': 'USAGE_LIMIT_EXCEEDED',
                'message': f'無料利用回数（30回/月）を超過しました。現在の利用回数: {user.free_usage_count}/30',
                'upgrade_url': 'https://www.smilefactory-rakuai.com/product-page/%E5%AD%A6%E7%BF%92%E6%8C%87%E5%B0%8E%E8%A6%81%E9%A0%98%E6%BA%96%E6%8B%A0-ai%E5%AD%A6%E7%BF%92%E3%82%A2%E3%83%97%E3%83%AA'
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
        
        # psycopg v3対応のデータベース操作
        with db_manager.get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO activation_codes (code, user_email, expires_at)
                    VALUES (%s, %s, %s)
                """, (code, user_email, expires_at))
                conn.commit()
        
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

@app.route('/api/usage-stats', methods=['POST'])
def get_usage_stats():
    """管理者用：ユーザー使用量統計取得"""
    data = request.get_json()
    admin_key = data.get('admin_key')
    
    # 管理者認証
    if admin_key != ADMIN_KEY:
        return jsonify({'success': False, 'error': '管理者権限が必要です'}), 403
    
    try:
        # psycopg v3対応のデータベース操作
        users = db_manager.execute_query("""
            SELECT 
                email,
                is_premium,
                free_usage_count,
                premium_expires_at,
                last_reset_date,
                created_at
            FROM users 
            ORDER BY free_usage_count DESC, created_at DESC
        """)
        
        # 統計情報を計算
        total_users = len(users)
        premium_users = sum(1 for user in users if user['is_premium'])
        free_users = total_users - premium_users
        total_usage = sum(user['free_usage_count'] for user in users)
        avg_usage = total_usage / total_users if total_users > 0 else 0
        
        return jsonify({
            'success': True,
            'statistics': {
                'total_users': total_users,
                'premium_users': premium_users,
                'free_users': free_users,
                'total_usage': total_usage,
                'average_usage': round(avg_usage, 1)
            },
            'users': users
        })
        
    except Exception as e:
        print(f"使用量統計取得エラー: {e}")
        return jsonify({'success': False, 'error': '統計取得に失敗しました'}), 500

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

@app.route('/api/reload-learning-data', methods=['POST'])
def reload_learning_data():
    """学習データを再読み込み（管理者用）"""
    try:
        # 簡易管理者認証
        admin_key = request.json.get('adminKey', '') if request.json else ''
        if admin_key != 'admin123':
            return jsonify({'success': False, 'error': '管理者権限が必要です'}), 403
        
        print("[API] 学習データの再読み込みを開始...")
        
        # 既存のlearning_itemsテーブルを削除
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM learning_items")
                conn.commit()
                print("[API] 既存のlearning_itemsデータを削除しました")
        
        # 学習データを再読み込み
        from database import _load_learning_data
        _load_learning_data()
        
        # 結果を確認
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM learning_items")
                count = cur.fetchone()[0]
                
                # テスト用identifierの確認
                cur.execute("SELECT identifier, subject FROM learning_items WHERE identifier = %s", ('8310213211100000',))
                test_result = cur.fetchone()
                
                # 教科別件数確認
                cur.execute("SELECT subject, COUNT(*) FROM learning_items GROUP BY subject ORDER BY subject")
                subjects = cur.fetchall()
        
        return jsonify({
            'success': True,
            'message': f'学習データの再読み込みが完了しました',
            'totalItems': count,
            'testIdentifierFound': bool(test_result),
            'testIdentifierSubject': test_result[1] if test_result else None,
            'subjectCounts': {subject: count for subject, count in subjects}
        })
        
    except Exception as e:
        print(f"[API] 学習データ再読み込みエラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/update-subject-names', methods=['POST'])
def update_subject_names():
    """教科名を標準化（管理者用）"""
    try:
        # 簡易管理者認証
        admin_key = request.json.get('adminKey', '') if request.json else ''
        if admin_key != 'admin123':
            return jsonify({'success': False, 'error': '管理者権限が必要です'}), 403
        
        print("[API] 教科名の標準化を開始...")
        
        with db_manager.get_connection() as conn:
            with conn.cursor() as cur:
                # 現在の教科名を確認
                cur.execute("SELECT DISTINCT subject FROM learning_items ORDER BY subject")
                current_subjects = [row[0] for row in cur.fetchall()]
                
                # 教科名を更新
                updates = [
                    ("特別の教科 道徳", "道徳"),
                    ("外国語", "英語")
                ]
                
                update_results = []
                for old_name, new_name in updates:
                    cur.execute(
                        "UPDATE learning_items SET subject = %s WHERE subject = %s",
                        (new_name, old_name)
                    )
                    updated_count = cur.rowcount
                    update_results.append(f"'{old_name}' → '{new_name}': {updated_count}件更新")
                    print(f"[API] '{old_name}' → '{new_name}': {updated_count}件更新")
                
                conn.commit()
                
                # 更新後の教科名を確認
                cur.execute("SELECT DISTINCT subject FROM learning_items ORDER BY subject")
                updated_subjects = [row[0] for row in cur.fetchall()]
                
                # 教科別件数確認
                cur.execute("SELECT subject, COUNT(*) FROM learning_items GROUP BY subject ORDER BY subject")
                subject_counts = {subject: count for subject, count in cur.fetchall()}
        
        return jsonify({
            'success': True,
            'message': '教科名の標準化が完了しました',
            'currentSubjects': current_subjects,
            'updatedSubjects': updated_subjects,
            'updateResults': update_results,
            'subjectCounts': subject_counts
        })
        
    except Exception as e:
        print(f"[API] 教科名標準化エラー: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)