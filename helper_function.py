import requests
from dotenv import load_dotenv
import os
import json

load_dotenv()
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")


def setup_get_started_button():
    url = "https://graph.facebook.com/v21.0/me/messenger_profile"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    payload = {
        "get_started": {
            "payload": "GET_STARTED"
        }
    }
    response = requests.post(url, params=params, json=payload)
    print(f"Setup Get Started Button response: {response.json()}")


def set_persistent_menu():
    url = f"https://graph.facebook.com/v21.0/me/messenger_profile?access_token={PAGE_ACCESS_TOKEN}"
    
    payload = {
        "persistent_menu": [
            {
                "locale": "default",
                "composer_input_disabled": False,
                "call_to_actions": [
                    {
                        "type": "postback",
                        "title": "Restart this conversation",
                        "payload": "RESTART_CONVERSATION"
                    }
                ]
            }
        ]
    }
    
    response = requests.post(url, json=payload)
    
    if response.status_code == 200:
        print("Persistent Menu set successfully!")
    else:
        print(f"Failed to set Persistent Menu: {response.text}")


def test_get_introduce_api():
    # URL của API
    url = "https://chatbot-server-2cc5c060e8ef.herokuapp.com/api/v1/get_introduce"

    # Body của yêu cầu
    payload = {
        "thread_id": "",
        "message": "",
        "additional_data": {
            "additionalProp1": {}
        }
    }

    # Header của yêu cầu
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json"
    }

    # Gửi yêu cầu POST và nhận dữ liệu SSE
    try:
        with requests.post(url, json=payload, headers=headers, stream=True) as response:
            response.raise_for_status()  # Kiểm tra lỗi HTTP
            for line in response.iter_lines():
                if line:
                    # Giải mã dòng dữ liệu
                    decoded_line = line.decode('utf-8')
                    # Dữ liệu SSE thường bắt đầu bằng "data: "
                    if decoded_line.startswith('data:'):
                        data = decoded_line[len('data: '):]
                        try:
                            # Nếu dữ liệu là JSON, parse nó
                            json_data = json.loads(data)
                            content = json_data["content"]
                            print(content)
                        except json.JSONDecodeError:
                            # Nếu không phải JSON, in nguyên văn
                            print(decoded_line)
    except requests.exceptions.RequestException as e:
        print(f"Lỗi khi gửi yêu cầu: {e}")
        
test_get_introduce_api()