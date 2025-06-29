import sqlite3
from flask import  jsonify
def get_messages():
    conn = sqlite3.connect('sms_messages.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM messages')
    rows = cursor.fetchall()
    conn.close()
    return jsonify(rows)
