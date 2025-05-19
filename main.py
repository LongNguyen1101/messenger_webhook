from fastapi import FastAPI, Request, Query
from fastapi.responses import PlainTextResponse
import requests
from dotenv import load_dotenv
import os
import uvicorn
import aiohttp
import asyncio
import json

load_dotenv(override=True)

app = FastAPI()

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN")
PAGE_ACCESS_TOKEN = os.getenv("PAGE_ACCESS_TOKEN")
CHATBOT_URL_PREFIX = os.getenv("CHATBOT_URL_PREFIX")

user_threads = {}  # {sender_psid: thread_id}

def get_customer_name(sender_psid: str):
    url = f"https://graph.facebook.com/v18.0/{sender_psid}"
    params = {
        "fields": "first_name,last_name",
        "access_token": PAGE_ACCESS_TOKEN
    }

    response = requests.get(url, params=params)

    if response.status_code == 200:
        data = response.json()
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        full_name = f"{first_name} {last_name}".strip()
        return full_name
    else:
        print(f"Failed to fetch name for PSID {sender_psid}. Status code: {response.status_code}")
        return None


@app.get("/")
async def hello_page():
    return PlainTextResponse(content="Hello World", status_code=200)
    
@app.get("/webhook")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_verify_token: str = Query(None, alias="hub.verify_token"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
):
    
    # Facebook gửi GET request để verify webhook
    if hub_mode == "subscribe" and hub_verify_token == VERIFY_TOKEN:
        print("Webhook verified successfully.")
        return PlainTextResponse(content=hub_challenge, status_code=200)
    else:
        return PlainTextResponse(content="Verification failed", status_code=403)


@app.post("/webhook")
async def receive_webhook(request: Request):
    # Facebook gửi POST request với event
    data = await request.json()
    print("Received webhook event:", data)

    if data.get('object') == 'page':
        for entry in data.get('entry', []):
            for messaging_event in entry.get('messaging', []):
                sender_id = messaging_event['sender']['id']
                print(f"messaging_event: {messaging_event}")

                # Xử lý tin nhắn
                if 'message' in messaging_event:
                    message_text = messaging_event['message']
                    is_echo = message_text.get("is_echo", None)
                    if is_echo is None:
                        await handleMessage(sender_id, message_text)

                # Xử lý postback
                elif 'postback' in messaging_event:
                    postback_payload = messaging_event['postback']
                    await handlePostback(sender_id, postback_payload)

    return {"status": "EVENT_RECEIVED"}
    
# Handles messages events
async def handleMessage(sender_psid, received_message):
    if 'text' in received_message:
        content = received_message.get('text', '')
        thread_id = user_threads.get(sender_psid, None)
        
        print(f">>>>>>>>>>>>> khách nhắn: {content}")
        print(f"thread id: {thread_id}")
        
        if thread_id is not None:
            print(f"thread id: {thread_id}")
            await stream_messages(sender_psid, thread_id=thread_id, message=content, init=False)
        else:
            customer_name = get_customer_name(sender_psid)
            print(f">>>>>>>>>>>>> khách nhắn: {content}")
            
            await stream_messages(
                sender_psid=sender_psid,
                customer_name=customer_name,
                intent=None,
                message=content,
                init=True
            )

# Handles messaging_postbacks events
async def handlePostback(sender_psid, received_postback):
    response = ""
    
    payload = received_postback.get("payload", None)
    if payload is not None:
        if payload == "GET_STARTED" or payload == "RESTART_CONVERSATION":
            if sender_psid in user_threads:
                del user_threads[sender_psid]
                
            response = {
                "attachment": {
                    "type": "template",
                    "payload": {
                        "template_type": "button",
                        "text": "Nhà hàng xin kính chào quý khách. Quý khách có nhu cầu đặt bàn, điều chỉnh thông tin đặt bàn, hay hủy bàn không ạ? Nhà hàng sẵn sàng hỗ trợ quý khách.",
                        "buttons": [
                            {
                                "type": "postback",
                                "title": "Đặt bàn",
                                "payload": "booking"
                            },
                            {
                                "type": "postback",
                                "title": "Thay đổi đơn đặt bàn",
                                "payload": "modify"
                            },
                            {
                                "type": "postback",
                                "title": "Huỷ bàn",
                                "payload": "cancel"
                            }
                        ]
                    }
                }
            }
            
            await callSendAPI(sender_psid, response)
        elif payload == "booking" or payload == "modify" or payload == "cancel":
            customer_name = get_customer_name(sender_psid)
            
            await stream_messages(
                sender_psid=sender_psid,
                customer_name=customer_name,
                intent=payload,
                init=True
            )
        elif payload == "no":
            response = {
                "text": "Oops, try sending another image."
            }
            await callSendAPI(sender_psid, response)

    
async def stream_messages(sender_psid: str, customer_name: str = None, intent: str = None,  
                          thread_id: str = None, message: str = None, init: bool = True):
    headers = {
        "Accept": "text/event-stream",
        "Content-Type": "application/json"
    }
    
    if init == True:
        body = {
            "thread_id": "",
            "message": "",
            "customer_psid": sender_psid,
            "customer_name": customer_name,
            "intent": intent,
            "user_input": message
        }
    else:
        body = {
            "thread_id": thread_id,
            "message": message
        }
    
    get_thread_flag = False
    
    url = f"{CHATBOT_URL_PREFIX}/api/v1/get_introduce" if init else f"{CHATBOT_URL_PREFIX}/api/v1/interact"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=body, headers=headers) as response:
                if response.status != 200:
                    error_msg = f"Failed to call API {url}: {response.content} | {response.status}"
                    await callSendAPI(sender_psid, {"text": error_msg})
                    return

                async for line in response.content:
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data = decoded_line[len('data: '):]
                            try:
                                message_dict = json.loads(data)
                                if "content" in message_dict and message_dict["type"] == "ai":
                                    # Gửi tin nhắn về Messenger
                                    print(f"message_dict: {message_dict}")
                                    await callSendAPI(sender_psid, {"text": message_dict["content"]})
                                    
                                    if get_thread_flag == False:
                                        user_threads[sender_psid] = message_dict["thread_id"]    
                                        get_thread_flag = True
                                        print(f"Saved thread_id for {sender_psid}: {user_threads[sender_psid]}")
                                        
                                elif "error" in message_dict:
                                    await callSendAPI(sender_psid, {"text": f"Error: {message_dict['error']}"})
                            except json.JSONDecodeError:
                                print(f"Invalid JSON: {data}")
                                continue
    except Exception as e:
        error_msg = f"Error streaming introduce messages: {str(e)}"
        await callSendAPI(sender_psid, {"text": error_msg})

# Sends response messages via the Send API
async def callSendAPI(sender_psid, response):
    url = "https://graph.facebook.com/v21.0/me/messages"
    params = {"access_token": PAGE_ACCESS_TOKEN}
    headers = {"Content-Type": "application/json"}
    payload = {
        "recipient": {"id": sender_psid},
        "message": response,
        "messaging_type": "RESPONSE"
    }
    
    response = requests.post(url, headers=headers, params=params, json=payload)
    print(f"Send message to messenger: code {response.status_code} | text: {response.text}")
    
 
if __name__ == '__main__':
    uvicorn.run("main:app",
                host="0.0.0.0",
                port=8000,
                reload=True)