from flask import Flask, request, jsonify
import re
from supabase import create_client, Client
from datetime import datetime

# --- CONFIG ---
SUPABASE_URL = "https://oodqaphoejozowarcnxy.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Im9vZHFhcGhvZWpvem93YXJjbnh5Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTExODUzMDEsImV4cCI6MjA2Njc2MTMwMX0.vorNchBsWI_bjWWIFjgaSeaIYHXlUVQZUQYk48sRHGc"  
TABLE_NAME = "Messages"  # Make sure this table exists in Supabase

# --- INIT ---
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- REGEX PATTERNS ---
NAME_PATTERN = r"Name[:\s]+([A-Za-z ]+)"
AMOUNT_PATTERN = r"Amount[:\s]+([\d,.]+)"
ACCOUNT_PATTERN = r"Account(?: No\.| Number)[:\s]+(\d+)"

def extract_fields(text):
    # TxId
    txid = ''
    txid_match = re.search(r'TxId[:\s]*([\d]+)', text)
    if not txid_match:
        txid_match = re.search(r'\*161\*TxId:([\d]+)\*R\*', text)
    if txid_match:
        txid = txid_match.group(1)

    # Amount
    amount = ''
    amount_match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*RWF', text)
    if amount_match:
        amount = amount_match.group(0)

    # Sender name
    sender_name = ''
    sender_match = re.search(r'from ([A-Za-z ]+) \(', text)
    if sender_match:
        sender_name = sender_match.group(1).strip()

    # Timestamp
    timestamp = ''
    timestamp_match = re.search(r'at (\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', text)
    if timestamp_match:
        timestamp = timestamp_match.group(1)

    return {
        'raw_text': text,
        'txid': txid or '',
        'amount': amount or '',
        'sender_name': sender_name or '',
        'timestamp': timestamp or None
    }

# --- ROUTES ---
@app.route('/receive-sms', methods=['POST'])
def receive_sms():
    data = request.get_json()
    message = data.get('message', '')

    # Only process messages that match the specific format
    pattern = r"^\*161\*TxId:\d+\*R\*You have received \d+ RWF from [A-Za-z ]+ \([*\d]+\) on your mobile money account at \d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\."
    if not re.match(pattern, message):
        return jsonify({"status": "ignored", "reason": "Message format not supported."})

    fields = extract_fields(message)
    supabase.table(TABLE_NAME).insert(fields).execute()
    return jsonify({"status": "saved", "data": fields})

if __name__ == '__main__':
    app.run(debug=True, port=5000) 