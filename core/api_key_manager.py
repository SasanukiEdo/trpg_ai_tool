# core/api_key_manager.py

"""APIキーをOSの資格情報ストアに安全に保存、取得、削除するためのモジュール。

このモジュールは `keyring` ライブラリを利用して、プラットフォーム依存の
安全なストレージ（Windowsの資格情報マネージャー、macOSのキーチェーンなど）に
APIキーを管理します。

主な機能:
    - save_api_key: APIキーを保存する。
    - get_api_key: 保存されたAPIキーを取得する。
    - delete_api_key: 保存されたAPIキーを削除する。
"""

import keyring
import keyring.errors

# サービス名とユーザー名は、このアプリケーション内でAPIキーを識別するための一意なキーとして機能します。
SERVICE_NAME = "TRPGAITool"
"""str: キーリングサービスに登録する際のサービス名。アプリケーション固有の値。"""

USERNAME_GEMINI = "gemini_api_key"
"""str: Gemini APIキーを識別するためのキーリング内のユーザー名。"""
# 将来的に他のサービスのAPIキーを扱う場合は、以下のように追加できます。
# USERNAME_CLAUDE = "claude_api_key"
# USERNAME_OPENAI = "openai_api_key"


def save_api_key(api_key_value: str, service_username: str = USERNAME_GEMINI) -> tuple[bool, str]:
    """指定されたAPIキーをOSの資格情報ストアに保存します。

    空のAPIキーが渡された場合は、既存のキーを削除する動作となります。

    Args:
        api_key_value (str): 保存するAPIキーの値。
        service_username (str, optional): キーリングサービス内のユーザー名。
            デフォルトは `USERNAME_GEMINI`。

    Returns:
        tuple[bool, str]: 保存/削除操作の成功を示すブール値と、
                          ユーザー向けのメッセージ文字列のタプル。
                          (True, "成功メッセージ") または (False, "エラーメッセージ")
    """
    if not api_key_value:
        # 空のキーは削除として扱う
        return delete_api_key(service_username)

    try:
        keyring.set_password(SERVICE_NAME, service_username, api_key_value)
        msg = f"APIキー ({service_username}) を安全に保存しました。"
        # print(msg)
        return True, msg
    except keyring.errors.NoKeyringError:
        msg = "キーリングサービスが見つかりません。APIキーを安全に保存できませんでした。"
        print(f"Error: {msg}")
        return False, msg
    except Exception as e:
        msg = f"APIキーの保存中に予期せぬエラーが発生しました ({service_username}): {e}"
        print(f"Error: {msg}")
        return False, msg

def get_api_key(service_username: str = USERNAME_GEMINI) -> str | None:
    """OSの資格情報ストアから指定されたサービスのAPIキーを取得します。

    Args:
        service_username (str, optional): 取得するAPIキーに対応するキーリング内のユーザー名。
            デフォルトは `USERNAME_GEMINI`。

    Returns:
        str | None: 取得されたAPIキーの文字列。キーが見つからない場合や
                    エラー発生時は None を返します。
    """
    try:
        api_key = keyring.get_password(SERVICE_NAME, service_username)
        if api_key:
            # print(f"APIキー ({service_username}) を取得しました。") # 実際のキー値をログに出さない
            # print(f"APIキー ({service_username}) をOS資格情報ストアから取得しました。")
            pass
        else:
            print(f"APIキー ({service_username}) はOS資格情報ストアに保存されていません。")
        return api_key
    except keyring.errors.NoKeyringError:
        print(f"Error: キーリングサービスが見つかりません。APIキー ({service_username}) を取得できませんでした。")
        return None
    except Exception as e:
        print(f"Error: APIキーの取得中に予期せぬエラーが発生しました ({service_username}): {e}")
        return None

def delete_api_key(service_username: str = USERNAME_GEMINI) -> tuple[bool, str]:
    """OSの資格情報ストアから指定されたサービスのAPIキーを削除します。

    Args:
        service_username (str, optional): 削除するAPIキーに対応するキーリング内のユーザー名。
            デフォルトは `USERNAME_GEMINI`。

    Returns:
        tuple[bool, str]: 削除操作の成功を示すブール値と、ユーザー向けのメッセージ文字列のタプル。
    """
    try:
        # 削除前にキーが存在するか確認 (任意だが、ユーザーメッセージのために行う)
        existing_key = keyring.get_password(SERVICE_NAME, service_username)
        if existing_key is None:
            msg = f"削除対象のAPIキー ({service_username}) は見つかりませんでした（既に削除済みか未保存）。"
            print(msg)
            return True, msg # 削除対象がないので実質成功

        keyring.delete_password(SERVICE_NAME, service_username)
        msg = f"保存されていたAPIキー ({service_username}) 情報を削除しました。"
        # print(msg)
        return True, msg
    except keyring.errors.PasswordDeleteError:
        # keyring.delete_password がキーが存在しない場合にこのエラーを出す場合がある
        msg = f"APIキー ({service_username}) の削除に失敗しました（または既に存在しませんでした）。"
        print(f"Info: {msg}") # エラーというより情報として
        return True, msg # 存在しない場合もTrueを返すことでUI側の処理を簡略化
    except keyring.errors.NoKeyringError:
        msg = f"キーリングサービスが見つかりません。APIキー ({service_username}) を削除できませんでした。"
        print(f"Error: {msg}")
        return False, msg
    except Exception as e:
        msg = f"APIキーの削除中に予期せぬエラーが発生しました ({service_username}): {e}"
        print(f"Error: {msg}")
        return False, msg

if __name__ == '__main__':
    """モジュールのテスト実行用コード。"""
    # print("--- APIキー管理モジュール テスト ---")

    # テスト用のAPIキー
    test_api_key_value = "test_gemini_key_12345abcde"
    test_service_user = USERNAME_GEMINI # デフォルトを使用

    # 1. 保存テスト
    # print(f"\n1. APIキー '{test_service_user}' の保存テスト...")
    success, message = save_api_key(test_api_key_value, test_service_user)
    # print(f"   結果: {success}, メッセージ: {message}")

    # 2. 取得テスト
    if success:
        # print(f"\n2. APIキー '{test_service_user}' の取得テスト...")
        retrieved_key = get_api_key(test_service_user)
        if retrieved_key == test_api_key_value:
            # print(f"   取得成功: キーは一致しました。")
            pass
        elif retrieved_key is None:
            # print(f"   取得失敗: キーが見つかりませんでした。")
            pass
        else:
            # print(f"   取得失敗: キーが期待した値と異なります。取得値: {retrieved_key}")
            pass

    # 3. 削除テスト
    # print(f"\n3. APIキー '{test_service_user}' の削除テスト...")
    del_success, del_message = delete_api_key(test_service_user)
    # print(f"   結果: {del_success}, メッセージ: {del_message}")

    # 4. 削除後の取得テスト
    # print(f"\n4. 削除後のAPIキー '{test_service_user}' の取得テスト...")
    retrieved_after_delete = get_api_key(test_service_user)
    if retrieved_after_delete is None:
        # print(f"   取得成功: キーは正しく削除されました (Noneが返されました)。")
        pass
    else:
        # print(f"   取得失敗: キーがまだ存在しています。取得値: {retrieved_after_delete}")
        pass

    # 5. 存在しないキーの削除テスト
    # print(f"\n5. 存在しないキー ('dummy_service_user') の削除テスト...")
    non_exist_del_success, non_exist_del_message = delete_api_key("dummy_service_user")
    # print(f"   結果: {non_exist_del_success}, メッセージ: {non_exist_del_message}")

    # 6. 空のAPIキーを保存しようとするテスト (削除として扱われる)
    # print(f"\n6. 空のAPIキーを '{test_service_user}' に保存するテスト (削除動作)...")
    # まず何かキーを保存しておく
    save_api_key("temp_key_for_empty_test", test_service_user)
    retrieved_before_empty_save = get_api_key(test_service_user)
    # print(f"   空キー保存前のキー取得確認: {'あり' if retrieved_before_empty_save else 'なし'}")

    empty_save_success, empty_save_message = save_api_key("", test_service_user)
    # print(f"   空キー保存結果: {empty_save_success}, メッセージ: {empty_save_message}")
    retrieved_after_empty_save = get_api_key(test_service_user)
    if retrieved_after_empty_save is None:
        # print(f"   取得成功: 空キー保存によりキーは正しく削除されました。")
        pass
    else:
        # print(f"   取得失敗: 空キー保存後もキーが存在しています。取得値: {retrieved_after_empty_save}")
        pass

    # print("\n--- テスト完了 ---")

