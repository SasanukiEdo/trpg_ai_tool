# core/api_key_manager.py

import keyring
import keyring.errors

# サービス名とユーザー名は固定値でOK (このアプリ専用として)
SERVICE_NAME = "TRPGAITool"
USERNAME = "gemini_api_key" # 扱うAPIキーの種類が増えたら変更を検討

def save_api_key(api_key_value):
    """指定されたAPIキーをOSの資格情報ストアに保存する"""
    if not api_key_value: # 空のキーは保存しない（削除として扱う）
        delete_api_key()
        return True, "APIキーが空のため、保存情報を削除しました。"
    try:
        keyring.set_password(SERVICE_NAME, USERNAME, api_key_value)
        return True, "APIキーを安全に保存しました。"
    except keyring.errors.NoKeyringError:
        return False, "キーリングサービスが見つかりません。APIキーを安全に保存できませんでした。"
    except Exception as e:
        return False, f"APIキーの保存中にエラーが発生しました: {e}"

def get_api_key():
    """OSの資格情報ストアからAPIキーを取得する"""
    try:
        api_key = keyring.get_password(SERVICE_NAME, USERNAME)
        return api_key # キーが存在しない場合は None が返る
    except keyring.errors.NoKeyringError:
        print("キーリングサービスが見つかりません。APIキーを取得できませんでした。")
        return None
    except Exception as e:
        print(f"APIキーの取得中にエラーが発生しました: {e}")
        return None

def delete_api_key():
    """OSの資格情報ストアからAPIキーを削除する"""
    try:
        keyring.delete_password(SERVICE_NAME, USERNAME)
        return True, "保存されていたAPIキー情報を削除しました。"
    except keyring.errors.PasswordDeleteError:
        # 削除対象のパスワードが存在しない場合もここに来ることがある
        return True, "削除対象のAPIキーが見つからないか、既に削除されています。"
    except keyring.errors.NoKeyringError:
        return False, "キーリングサービスが見つかりません。APIキーを削除できませんでした。"
    except Exception as e:
        return False, f"APIキーの削除中にエラーが発生しました: {e}"

if __name__ == '__main__':
    # テスト用コード
    print("--- APIキー保存テスト ---")
    test_key = "test_api_key_12345"
    success, msg = save_api_key(test_key)
    print(f"保存結果: {success}, メッセージ: {msg}")

    if success:
        print("\n--- APIキー取得テスト ---")
        retrieved_key = get_api_key()
        if retrieved_key == test_key:
            print(f"取得成功: {retrieved_key}")
        elif retrieved_key is None:
            print("取得失敗: キーが見つかりません。")
        else:
            print(f"取得失敗: 期待したキーと異なります。取得値: {retrieved_key}")

        print("\n--- APIキー削除テスト ---")
        success_del, msg_del = delete_api_key()
        print(f"削除結果: {success_del}, メッセージ: {msg_del}")

        print("\n--- 削除後のAPIキー取得テスト ---")
        retrieved_key_after_delete = get_api_key()
        if retrieved_key_after_delete is None:
            print("取得成功: キーは正しく削除されました。")
        else:
            print(f"取得失敗: キーが残っています。取得値: {retrieved_key_after_delete}")

    print("\n--- 空のキー保存（削除）テスト ---")
    success_save_empty, msg_save_empty = save_api_key("")
    print(f"空キー保存結果: {success_save_empty}, メッセージ: {msg_save_empty}")
    retrieved_key_after_empty_save = get_api_key()
    if retrieved_key_after_empty_save is None:
        print("取得成功: 空キー保存によりキーは削除されました。")

