# Service Usage Guide

## Purpose and Audience

This page explains how logged-in users can integrate with the AS API Console service after obtaining an API key. It is intended for users who have completed the application flow and are ready to call the model service.

## Usage Limits

- Request rate: Each API key can send up to `60` API requests per minute (`60 RPM`).
- Concurrent connections: Each API key is limited to `3` concurrent connections.
- Context window: `256K`.

## What to Prepare Before Use

- An account that can sign in to AS API Console.
- A clear application purpose.
- The desired key duration.
- A secure place to store the API key, such as a local `.env` file or a managed secret store.

## Integration Steps

1. Apply for an API key in the system.
2. Save the plaintext API key immediately when it is shown.
3. Set `API_KEY` and `BASE_URL` in your runtime environment, where `BASE_URL` is `https://api.ascs.sinica.edu.tw`.
4. Call `POST /v1/chat/completions` with `Authorization: Bearer <API_KEY>`.
5. Read the model output from `choices[0].message.content`.

## Python Example

The example below is a version prepared for documentation display and user reference:

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
            {"role": "system", "content": "Please answer in Traditional Chinese."},
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
    answer = chat_with_model("Please briefly introduce yourself.")
    print(answer)
```

## Notes

- The plaintext API key is shown only once at creation time, so save it immediately.
- Do not hardcode the API key in frontend code or commit it into version control.
- Use environment variables, deployment secrets, or another managed secret mechanism to store the key.
- Plan request rate, concurrency, and prompt size according to the usage limits above.
- If a request fails, first verify the `BASE_URL`, Bearer token, and payload shape.
