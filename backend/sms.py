import requests

API_KEY = "YOUR_FAST2SMS_API_KEY"

def send_sms(phone, message):
    url = "https://www.fast2sms.com/dev/bulkV2"
    payload = {
        "route":"q",
        "message":message,
        "language":"english",
        "numbers":phone
    }
    headers = {
        "authorization": API_KEY,
        "Content-Type":"application/json"
    }
    r = requests.post(url, json=payload, headers=headers)
    print(r.text)

send_sms("9876543210", "Your museum ticket booked successfully!")
