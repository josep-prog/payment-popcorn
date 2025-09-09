from flask import Flask, request, jsonify, render_template
import re
from supabase import create_client, Client
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import sys

#  CONFIG for supabase keys
load_dotenv()
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
TABLE_NAME = "messages"

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Error: SUPABASE_URL and SUPABASE_KEY must be set in the environment.")
    sys.exit(1)

# --- INIT ---
app = Flask(__name__)
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def _to_int_amount(text: str) -> int | None:
    match = re.search(r'(\d{1,3}(?:,\d{3})*|\d+)\s*RWF', text, flags=re.IGNORECASE)
    if not match:
        match = re.search(r'RWF\s*(\d{1,3}(?:,\d{3})*|\d+)', text, flags=re.IGNORECASE)
        if match:
            value = match.group(1)
        else:
            return None
    else:
        value = match.group(1)
    try:
        return int(value.replace(',', ''))
    except Exception:
        return None


def extract_fields(text: str) -> dict:
    # TxId (accept alphanumerics, dots, dashes)
    txid = ''
    txid_match = re.search(r'TxId[:\s]*([A-Za-z0-9.\-]+)', text, flags=re.IGNORECASE)
    if not txid_match:
        txid_match = re.search(r'\*\d+\*TxId:([A-Za-z0-9.\-]+)\*', text, flags=re.IGNORECASE)
    if txid_match:
        txid = txid_match.group(1).strip()

    # Amount in RWF as integer
    amount_rwf = _to_int_amount(text) or 0

    # Payer name
    payer_name = ''
    sender_match = re.search(r'from\s+([A-Za-z][A-Za-z ]+?)\s*\(', text, flags=re.IGNORECASE)
    if sender_match:
        payer_name = sender_match.group(1).strip()

    # Phone last digits (masked inside parentheses like (07****123))
    phone_last_digits = ''
    phone_match = re.search(r'\((?:[*\d]*?)(\d{2,3})\)', text)
    if phone_match:
        phone_last_digits = phone_match.group(1)

    received_at = datetime.now(timezone.utc).isoformat()

    return {
        'raw_text': text,
        'txid': txid,
        'amount_rwf': amount_rwf,
        'payer_name': payer_name,
        'phone_last_digits': phone_last_digits,
        'received_at': received_at,
    }

# --- ROUTES ---
@app.route('/receive-sms', methods=['POST'])
def receive_sms():
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()
    if not message:
        return jsonify({"status": "error", "error": "Missing 'message'"}), 400

    fields = extract_fields(message)
    if not fields.get('txid'):
        return jsonify({"status": "ignored", "reason": "TxId not found in message."}), 200

    supabase.table(TABLE_NAME).insert(fields).execute()
    return jsonify({"status": "saved", "data": fields}), 200

@app.route('/verify-payment', methods=['POST'])
def verify_payment_api():
    data = request.get_json(silent=True) or {}
    name = (data.get('name') or '').strip()
    phone = (data.get('phone_number') or '').strip()
    txid = (data.get('txid') or '').strip()

    if not (name and phone and txid):
        return jsonify({"status": "not_approved", "message": "name, phone_number, and txid are required."}), 400

    # Fetch by txid (case-insensitive)
    db = supabase.table(TABLE_NAME).select('*').ilike('txid', txid).limit(1).execute()
    if not db.data:
        return jsonify({"status": "not_approved", "message": "TxId not found."}), 200

    record = db.data[0]

    # Name check (case-insensitive substring)
    rec_name = (record.get('payer_name') or '').strip()
    if not rec_name or (name.lower() not in rec_name.lower()):
        return jsonify({"status": "not_approved", "message": "Name does not match."}), 200

    # Phone last digits check (match last 2 or 3 digits)
    submitted_last3 = phone[-3:] if len(phone) >= 3 else phone
    submitted_last2 = phone[-2:] if len(phone) >= 2 else phone
    rec_last = (record.get('phone_last_digits') or '').strip()
    if rec_last and rec_last not in {submitted_last3, submitted_last2}:
        return jsonify({"status": "not_approved", "message": "Phone digits do not match."}), 200

    amount_rwf = record.get('amount_rwf') or 0
    return jsonify({
        "status": "approved",
        "message": "Payment verified.",
        "amount_rwf": amount_rwf,
        "txid": record.get('txid'),
    }), 200


@app.route('/', methods=['GET', 'HEAD'])
def health():
    return 'OK', 200


@app.route('/verify-payment-web', methods=['GET', 'POST'])
def verify_payment_web():
    result_message = None
    result_status = None
    amount = None
    if request.method == 'POST':
        name = request.form.get('name')
        phone = request.form.get('phone')
        txid = request.form.get('txid')
        if name and phone and txid:
            resp = verify_payment_api()
            # When called internally, verify_payment_api returns a Flask Response
            # For web flow simplicity, re-run the core logic here without HTTP wrapper
            db = supabase.table(TABLE_NAME).select('*').ilike('txid', txid.strip()).limit(1).execute()
            if not db.data:
                result_message = "TxId not found."
                result_status = "not_approved"
            else:
                record = db.data[0]
                rec_name = (record.get('payer_name') or '')
                rec_last = (record.get('phone_last_digits') or '')
                ok_name = (name.strip().lower() in rec_name.lower()) if rec_name else False
                last3 = phone.strip()[-3:] if len(phone.strip()) >= 3 else phone.strip()
                last2 = phone.strip()[-2:] if len(phone.strip()) >= 2 else phone.strip()
                ok_phone = (not rec_last) or (rec_last in {last3, last2})
                if ok_name and ok_phone:
                    result_status = "approved"
                    amount = record.get('amount_rwf') or 0
                    result_message = f"Payment verified. Amount received: {amount:,} RWF."
                else:
                    result_status = "not_approved"
                    result_message = "Details do not match."
        else:
            result_message = "All fields are required."
            result_status = "not_approved"
    return render_template('verify_payment.html', result_message=result_message, result_status=result_status, amount=amount)

if __name__ == '__main__':
    app.run(debug=True, port=5000) 