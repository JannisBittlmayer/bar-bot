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
        # Repeat until a matching rule is found or the order is saved
        while True:
            # Check if a matching rule can be found
            matched_word, matching_rule = find_matching_rule(
                db_cursor, message)
            # If a matching rule is found, delete the rule
            if matching_rule:
                delete_rule(db_cursor, matching_rule)
                # Tell CPEE about matched rule. If successful, return info to user. If not, try again
                if send_matched_rule(matching_rule, user_id, timestamp):
                    return f'Rule matched: Found "{matched_word}" in rule {matching_rule[0]}'
            # If no matching rule is found, save the order in the order queue
            else:
                save_order(db_cursor, message, user_id, timestamp)
                return '''Your order cannot be yet fulfilled, we saved it and will 
                contact you as soon as it is fulfilled.'''

# Find matching rule in database


def find_matching_rule(db_cursor, message):
    words = message.split()
    for word in words:
        # Ignore words with less than 4 characters like 'a', 'the', 'and'
        if len(word) < 4:
            continue
        # Check if a matching rule can be found
        db_cursor.execute('SELECT * FROM rules WHERE strings_to_match LIKE :word',
                          {'word': '%' + word + '%'})
        matching_rule = db_cursor.fetchone()
        if matching_rule:
            return word, matching_rule
    return None, None

# Tell CPEE about matched rule and delete rule from database


def send_matched_rule(matching_rule, user_id, timestamp):
    callback_url = matching_rule[1]
    # Tell CPEE about matched rule
    response = requests.put(callback_url, json.dumps(
        {'user_id': user_id, 'cocktail': matching_rule[0], 'timestamp': timestamp}))
    return response.status_code == 200


def delete_rule(db_cursor, matching_rule):
    # Delete matched rule from database
    db_cursor.execute('DELETE FROM rules WHERE strings_to_match = :strings AND callback = :callback', {
        'strings': matching_rule[0], 'callback': matching_rule[1]})

# Save order to database


def save_order(db_cursor, message, user_id, timestamp):
    db_cursor.execute('INSERT INTO orders VALUES (:message, :user_id, :timestamp)', {
        'message': message, 'user_id': user_id, 'timestamp': timestamp})


run(host='::1', port=49124)
