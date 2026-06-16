# 服務使用說明

## 用途與適用對象

本頁提供已登入使用者參考 AS API Console 的服務串接方式，適用於已完成 API Key 申請並準備開始呼叫模型服務的使用者。

## 申請前需要準備的資訊

- 已可登入 AS API Console 的帳號
- 申請用途說明
- 預計使用的有效期限
- 可安全保存 API Key 的環境，例如本機 `.env` 或受管密鑰服務

## 串接步驟摘要

1. 先在系統中申請 API Key。
2. 申請成功後立即保存一次性顯示的明文 API Key。
3. 將 `API_KEY` 與 `BASE_URL` 設定到執行環境，其中 `BASE_URL` 為 `https://api.ascs.sinica.edu.tw`。
4. 使用 `Authorization: Bearer <API_KEY>` 呼叫 `POST /v1/chat/completions`。
5. 從回應中的 `choices[0].message.content` 讀取模型回答。

## Python 範例

以下範本為適合文件顯示與使用者參考的版本：

```python
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")


def chat_with_model(prompt, model_name="gemma-4-31B-it"):
    url = f"{BASE_URL}/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": "請使用繁體中文回答。"},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.7,
        "max_tokens": 20480,
    }

    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]


if __name__ == "__main__":
    answer = chat_with_model("請簡短介紹你自己")
    print(answer)
```

## 注意事項

- 明文 API Key 預設只會在建立當下顯示一次，請立即保存。
- 不要把 API Key 寫死在前端程式或直接提交到版本控制。
- 建議使用環境變數、部署平台 secret，或其他受管密鑰儲存方式保存 API Key。
- 若請求失敗，請先確認 `BASE_URL`、Bearer Token 與請求 payload 格式是否正確。
