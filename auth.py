import sqlite3
import bcrypt
from flask import session, g
from flask_login import UserMixin
from datetime import datetime, timedelta

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
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            return User(
                id=user_data[0],
                email=user_data[1],
                is_premium=bool(user_data[3]),
                premium_expires_at=user_data[4],
                free_usage_count=user_data[5],
                last_reset_date=user_data[6]
            )
        return None

    @staticmethod
    def get_by_email(email):
        """メールアドレスからユーザー情報を取得"""
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user_data = cursor.fetchone()
        conn.close()
        
        if user_data:
            return User(
                id=user_data[0],
                email=user_data[1],
                is_premium=bool(user_data[3]),
                premium_expires_at=user_data[4],
                free_usage_count=user_data[5],
                last_reset_date=user_data[6]
            )
        return None

    @staticmethod
    def create(email, password):
        """新しいユーザーを作成"""
        password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'INSERT INTO users (email, password_hash) VALUES (?, ?)',
                (email, password_hash)
            )
            user_id = cursor.lastrowid
            conn.commit()
            
            return User(id=user_id, email=email)
        except sqlite3.IntegrityError:
            return None  # メールアドレスが既に存在
        finally:
            conn.close()

    @staticmethod
    def verify_password(email, password):
        """パスワードを検証"""
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        cursor.execute('SELECT password_hash FROM users WHERE email = ?', (email,))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            return bcrypt.checkpw(password.encode('utf-8'), result[0])
        return False

    def check_usage_limit(self):
        """無料プランの利用制限をチェック"""
        if self.is_premium:
            return True
        
        # 月が変わったらカウントリセット
        today = datetime.now().date()
        if self.last_reset_date:
            last_reset = datetime.strptime(self.last_reset_date, '%Y-%m-%d').date()
            if today.month != last_reset.month or today.year != last_reset.year:
                self.reset_usage_count()
                return True
        
        return self.free_usage_count < 30

    def increment_usage_count(self):
        """利用回数をカウントアップ"""
        if self.is_premium:
            return
        
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET free_usage_count = free_usage_count + 1 WHERE id = ?',
            (self.id,)
        )
        conn.commit()
        conn.close()
        
        self.free_usage_count += 1

    def reset_usage_count(self):
        """利用回数をリセット（月初処理）"""
        today = datetime.now().date()
        
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        cursor.execute(
            'UPDATE users SET free_usage_count = 0, last_reset_date = ? WHERE id = ?',
            (today.strftime('%Y-%m-%d'), self.id)
        )
        conn.commit()
        conn.close()
        
        self.free_usage_count = 0
        self.last_reset_date = today.strftime('%Y-%m-%d')

    def activate_premium(self, activation_code):
        """プレミアムアカウントを有効化"""
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        try:
            # 認証コードの検証
            cursor.execute(
                'SELECT * FROM activation_codes WHERE code = ? AND user_email = ? AND is_used = 0 AND expires_at > ?',
                (activation_code, self.email, datetime.now().isoformat())
            )
            code_data = cursor.fetchone()
            
            if code_data:
                # 認証コードを使用済みにする
                cursor.execute(
                    'UPDATE activation_codes SET is_used = 1 WHERE id = ?',
                    (code_data[0],)
                )
                
                # ユーザーをプレミアムに変更（1年間有効）
                expires_at = datetime.now() + timedelta(days=365)
                cursor.execute(
                    'UPDATE users SET is_premium = 1, premium_expires_at = ? WHERE id = ?',
                    (expires_at.isoformat(), self.id)
                )
                
                conn.commit()
                
                self.is_premium = True
                self.premium_expires_at = expires_at.isoformat()
                return True
            
            return False
        finally:
            conn.close()

    def check_premium_expiry(self):
        """プレミアム期限をチェックし、期限切れの場合は自動的に解除"""
        if self.is_premium and self.premium_expires_at:
            try:
                expires_at = datetime.fromisoformat(self.premium_expires_at)
                if datetime.now() > expires_at:
                    # 期限切れ：プレミアム状態を解除
                    self.revoke_premium()
            except (ValueError, TypeError):
                # 日付形式が不正の場合もプレミアム解除
                self.revoke_premium()

    def revoke_premium(self):
        """プレミアム状態を解除"""
        conn = sqlite3.connect('study_app.db')
        cursor = conn.cursor()
        
        try:
            cursor.execute(
                'UPDATE users SET is_premium = 0, premium_expires_at = NULL WHERE id = ?',
                (self.id,)
            )
            conn.commit()
            
            self.is_premium = False
            self.premium_expires_at = None
            print(f"[INFO] ユーザー {self.email} のプレミアム状態を解除しました")
            
        finally:
            conn.close()

# 認証ヘルパー関数
def get_current_user():
    """現在のユーザーを取得"""
    if 'user_id' in session:
        return User.get(session['user_id'])
    return None

def login_required(f):
    """ログインが必要なエンドポイント用のデコレーター"""
    from functools import wraps
    from flask import redirect, url_for, flash
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('ログインが必要です。', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function