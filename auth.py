import bcrypt
from flask import session, g
from flask_login import UserMixin
from datetime import datetime, timedelta
from database import db_manager

class User(UserMixin):
    def __init__(self, id, email, is_premium=False, premium_expires_at=None, free_usage_count=0, last_reset_date=None):
        self.id = id
        self.email = email
        self.is_premium = is_premium
        self.premium_expires_at = premium_expires_at
        self.free_usage_count = free_usage_count
        self.last_reset_date = last_reset_date
        
        # プレミアム期限チェック
        self.check_premium_expiry()

    @staticmethod
    def get(user_id):
        """ユーザーIDからユーザー情報を取得"""
        try:
            user_data = db_manager.execute_single('SELECT * FROM users WHERE id = %s', (user_id,))
            
            if user_data:
                return User(
                    id=user_data['id'],
                    email=user_data['email'],
                    is_premium=bool(user_data['is_premium']),
                    premium_expires_at=user_data['premium_expires_at'],
                    free_usage_count=user_data['free_usage_count'],
                    last_reset_date=user_data['last_reset_date']
                )
            return None
        except Exception as e:
            print(f"[AUTH] Error getting user: {e}")
            return None

    @staticmethod
    def get_by_email(email):
        """メールアドレスからユーザー情報を取得"""
        try:
            user_data = db_manager.execute_single('SELECT * FROM users WHERE email = %s', (email,))
            
            if user_data:
                return User(
                    id=user_data['id'],
                    email=user_data['email'],
                    is_premium=bool(user_data['is_premium']),
                    premium_expires_at=user_data['premium_expires_at'],
                    free_usage_count=user_data['free_usage_count'],
                    last_reset_date=user_data['last_reset_date']
                )
            return None
        except Exception as e:
            print(f"[AUTH] Error getting user by email: {e}")
            return None

    @staticmethod
    def create(email, password):
        """新しいユーザーを作成"""
        try:
            password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
            
            # ユーザーを作成
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'INSERT INTO users (email, password_hash) VALUES (%s, %s) RETURNING id',
                        (email, password_hash)
                    )
                    user_id = cur.fetchone()[0]
                    conn.commit()
            
            return User(id=user_id, email=email)
        except Exception as e:
            print(f"[AUTH] Error creating user: {e}")
            return None  # メールアドレスが既に存在

    @staticmethod
    def verify_password(email, password):
        """パスワードを検証"""
        try:
            result = db_manager.execute_single('SELECT password_hash FROM users WHERE email = %s', (email,))
            
            if result:
                stored_hash = result['password_hash']
                
                # バイナリデータの処理
                if isinstance(stored_hash, memoryview):
                    stored_hash = stored_hash.tobytes()
                elif isinstance(stored_hash, str) and stored_hash.startswith('\\x'):
                    try:
                        hex_string = stored_hash[2:]
                        stored_hash = bytes.fromhex(hex_string)
                    except ValueError:
                        print(f"[AUTH] Invalid hex format: {stored_hash[:50]}...")
                        return False
                elif isinstance(stored_hash, str):
                    stored_hash = stored_hash.encode('utf-8')
                
                return bcrypt.checkpw(password.encode('utf-8'), stored_hash)
            return False
        except Exception as e:
            print(f"[AUTH] Error verifying password: {e}")
            return False

    def check_usage_limit(self):
        """無料プランの利用制限をチェック"""
        print(f"[DEBUG] check_usage_limit: is_premium={self.is_premium}, usage_count={self.free_usage_count}")
        
        # プレミアムユーザーは常に利用可能
        if self.is_premium:
            print("[DEBUG] Premium user - unlimited access")
            return True
        
        # 月が変わったらカウントリセット
        today = datetime.now().date()
        if self.last_reset_date:
            if isinstance(self.last_reset_date, str):
                last_reset = datetime.strptime(self.last_reset_date, '%Y-%m-%d').date()
            else:
                last_reset = self.last_reset_date
            
            if today.month != last_reset.month or today.year != last_reset.year:
                print("[DEBUG] Monthly usage reset required")
                self.reset_usage_count()
                return True
        
        # 無料ユーザーは30回まで利用可能
        result = self.free_usage_count < 30
        print(f"[DEBUG] Free user limit check: {self.free_usage_count}/30 - allowed: {result}")
        return result

    def increment_usage_count(self):
        """利用回数をカウントアップ（プレミアムユーザーでも使用量把握のためカウント）"""
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'UPDATE users SET free_usage_count = free_usage_count + 1 WHERE id = %s',
                        (self.id,)
                    )
                    conn.commit()
            
            self.free_usage_count += 1
            
            if self.is_premium:
                print(f"[DEBUG] Premium user usage tracked: {self.free_usage_count} (unlimited)")
            else:
                print(f"[DEBUG] Free user usage incremented: {self.free_usage_count}/30")
        except Exception as e:
            print(f"[AUTH] Error incrementing usage count: {e}")

    def reset_usage_count(self):
        """利用回数をリセット（月初処理）"""
        try:
            today = datetime.now().date()
            
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'UPDATE users SET free_usage_count = 0, last_reset_date = %s WHERE id = %s',
                        (today, self.id)
                    )
                    conn.commit()
            
            self.free_usage_count = 0
            self.last_reset_date = today
        except Exception as e:
            print(f"[AUTH] Error resetting usage count: {e}")

    def activate_premium(self, activation_code):
        """プレミアムアカウントを有効化"""
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    # 認証コードの検証
                    cur.execute(
                        'SELECT * FROM activation_codes WHERE code = %s AND user_email = %s AND is_used = FALSE AND expires_at > %s',
                        (activation_code, self.email, datetime.now())
                    )
                    code_data = cur.fetchone()
                    
                    if code_data:
                        # 認証コードを使用済みにする
                        cur.execute(
                            'UPDATE activation_codes SET is_used = TRUE WHERE id = %s',
                            (code_data['id'],)
                        )
                        
                        # プレミアムアカウントに変更（1年間有効）
                        premium_expires = datetime.now() + timedelta(days=365)
                        cur.execute(
                            'UPDATE users SET is_premium = TRUE, premium_expires_at = %s WHERE id = %s',
                            (premium_expires, self.id)
                        )
                        
                        conn.commit()
                        
                        self.is_premium = True
                        self.premium_expires_at = premium_expires
                        return True
                    else:
                        return False
        except Exception as e:
            print(f"[AUTH] Error activating premium: {e}")
            return False

    def revoke_premium(self):
        """プレミアムアカウントを解除"""
        try:
            with db_manager.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        'UPDATE users SET is_premium = FALSE, premium_expires_at = NULL WHERE id = %s',
                        (self.id,)
                    )
                    conn.commit()
            
            self.is_premium = False
            self.premium_expires_at = None
            return True
        except Exception as e:
            print(f"[AUTH] Error revoking premium: {e}")
            return False

    def check_premium_expiry(self):
        """プレミアム期限をチェックして、期限切れの場合は自動解除"""
        if self.is_premium and self.premium_expires_at:
            if isinstance(self.premium_expires_at, str):
                expires_at = datetime.fromisoformat(self.premium_expires_at.replace('Z', '+00:00'))
            else:
                expires_at = self.premium_expires_at
            
            if datetime.now() > expires_at:
                print(f"[AUTH] プレミアム期限切れ検出: {self.email}")
                self.revoke_premium()

def get_current_user():
    """現在のログインユーザーを取得"""
    if 'user_id' in session:
        return User.get(session['user_id'])
    return None

def login_required(f):
    """ログインが必要なページのデコレーター"""
    from functools import wraps
    from flask import redirect, url_for, flash
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('ログインが必要です。', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function