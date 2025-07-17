#!/usr/bin/env python3
"""
bcryptハッシュ生成・検証テスト
"""

import bcrypt

def test_bcrypt():
    """bcryptの動作確認"""
    password = "1342uchi"
    email = "utakashi2013@outlook.jp"
    
    print("=== bcrypt ハッシュ生成テスト ===")
    
    # ハッシュ生成
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
    print(f"Original password: {password}")
    print(f"Generated hash type: {type(password_hash)}")
    print(f"Generated hash: {password_hash}")
    print(f"Hash length: {len(password_hash)}")
    
    # 検証テスト
    print("\n=== bcrypt 検証テスト ===")
    result = bcrypt.checkpw(password.encode('utf-8'), password_hash)
    print(f"Verification result: {result}")
    
    # 間違ったパスワードでの検証
    wrong_password = "wrongpassword"
    result_wrong = bcrypt.checkpw(wrong_password.encode('utf-8'), password_hash)
    print(f"Wrong password verification: {result_wrong}")
    
    # 16進文字列への変換（PostgreSQL保存時の問題確認）
    print("\n=== 16進文字列変換テスト ===")
    hex_string = "\\x" + password_hash.hex()
    print(f"Hex string: {hex_string[:50]}...")
    
    # 16進文字列からバイトに戻す
    try:
        recovered_bytes = bytes.fromhex(hex_string[2:])
        print(f"Recovered bytes type: {type(recovered_bytes)}")
        print(f"Recovered bytes: {recovered_bytes[:50]}...")
        
        # 復元されたハッシュで検証
        result_recovered = bcrypt.checkpw(password.encode('utf-8'), recovered_bytes)
        print(f"Recovered hash verification: {result_recovered}")
    except Exception as e:
        print(f"16進変換エラー: {e}")

if __name__ == "__main__":
    test_bcrypt()