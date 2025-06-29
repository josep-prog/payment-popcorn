from flask import Flask, request, jsonify
import sqlite3
import re
from messages_view import get_messages  # <-- importing the function

app = Flask(__name__)
DATABASE = 'sms_messages.db'





@app.route('/messages')
def show_messages():
    return get_messages()

# Initialize DB (create table if not exists)
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            raw_text TEXT,
            amount TEXT,
            sender_name TEXT,
            recipient_name TEXT,
            recipient_account TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Extract fields from SMS text
def extract_fields(text):
    amount = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*RWF', text)
    recipient_name = re.search(r'to\s+([A-Za-z\s]+)\s*(\(\d+\)|\d+)?', text)
    recipient_account = re.search(r'\((\d{9,})\)|\b(\d{6,})\b', text)
    sender = re.search(r'from your mobile money account\s+(\d+)', text)

    return {
        'raw_text': text,
        'amount': amount.group(0) if amount else '',
        'recipient_name': recipient_name.group(1).strip() if recipient_name else '',
        'recipient_account': recipient_account.group(1) or recipient_account.group(2) if recipient_account else '',
        'sender_name': sender.group(1) if sender else ''
    }

@app.route('/receive-sms', methods=['POST'])
def receive_sms():
    data = request.get_json()
    message = data.get('message', '')

    fields = extract_fields(message)

    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO messages (raw_text, amount, sender_name, recipient_name, recipient_account)
        VALUES (?, ?, ?, ?, ?)
    ''', (
        fields['raw_text'],
        fields['amount'],
        fields['sender_name'],
        fields['recipient_name'],
        fields['recipient_account']
    ))
    conn.commit()
    conn.close()

    return jsonify({"status": "saved", "data": fields})

if __name__ == '__main__':
    init_db()
    app.run()
