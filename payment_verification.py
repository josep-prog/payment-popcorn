from supabase import create_client, Client
import os
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in the environment.")

TABLE_NAME = "messages"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def verify_payment(txid: str) -> dict:
    db = supabase.table(TABLE_NAME).select('*').ilike('txid', txid.strip()).limit(1).execute()
    if not db.data:
        return {"status": "not_approved", "message": "TxId not found."}

    record = db.data[0]
    amount_rwf = record.get('amount_rwf') or 0
    return {
        "status": "approved",
        "message": "Payment verified.",
        "amount_rwf": amount_rwf,
        "txid": record.get('txid'),
    }