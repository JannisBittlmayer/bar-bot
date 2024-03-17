import json
from bottle import route, run, request
import sqlite3
import requests
from order import Order

# Create tables if not present yet


def create_tables():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute(
            '''CREATE TABLE IF NOT EXISTS orders (message text, user_id text, timestamp integer)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS rules (strings_to_match text, callback text)''')


create_tables()

# Take order


@route('/order')
def index():
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        message = request.query.message
        user_id = request.query.user_id
        timestamp = request.query.timestamp
        new_order = Order(message, user_id, timestamp)
        # Check, whether order is already matched by a rule
        matched_word, matching_rule = find_matching_rule(db_cursor, message)
        # If rule is found, callback CPEE, delete rule and return info to user
        if matching_rule:
            send_request_and_delete_rule(
                db_cursor, matching_rule, user_id, timestamp)
            return 'Rule matched: Found \"' + matched_word + '\" in rule ' + matching_rule[0]
        else:
            save_order(db_cursor, message, user_id, timestamp)
    return 'No matching rule found, order saved in order queue'

# Find matching rule in database


def find_matching_rule(db_cursor, message):
    words = message.split()
    for word in words:
        # Ignore words with less than 4 characters like 'a', 'the', 'and'
        if len(word) < 4:
            continue
        # Check if a matching rule can be found
        db_cursor.execute('SELECT * FROM rules WHERE strings_to_match LIKE :strings',
                          {'strings': '%' + word + '%'})
        matching_rule = db_cursor.fetchone()
        if matching_rule:
            return word, matching_rule
    return None, None

# Tell CPEE about matched rule and delete rule from database


def send_request_and_delete_rule(db_cursor, matching_rule, user_id, timestamp):
    callback_url = matching_rule[1]
    # Tell CPEE about matched rule
    requests.put(callback_url, json.dumps(
        {'user_id': user_id, 'cocktail': matching_rule[0], 'timestamp': timestamp}))
    # Delete matched rule from database
    db_cursor.execute('DELETE FROM rules WHERE strings_to_match = :strings AND callback = :callback', {
        'strings': matching_rule[0], 'callback': matching_rule[1]})

# Save order to database


def save_order(db_cursor, message, user_id, timestamp):
    db_cursor.execute('INSERT INTO orders VALUES (:message, :user_id, :timestamp)', {
        'message': message, 'user_id': user_id, 'timestamp': timestamp})


run(host='::1', port=49124)
