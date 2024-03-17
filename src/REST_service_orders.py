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
        c = conn.cursor()
        message = request.query.message
        user_id = request.query.user_id
        timestamp = request.query.timestamp
        new_order = Order(message, user_id, timestamp)
        # Check, if matching rule can be found
        words = message.split()
        # For every word, check if a matching rule can be found
        for word in words:
            # Ignore short words like "a", "the", "is", etc.
            if len(word) < 4:
                continue
            # Check if a matching rule can be found
            c.execute('SELECT * FROM rules WHERE strings_to_match LIKE :strings',
                      {'strings': '%' + word + '%'})
            matching_rule = c.fetchone()
            # If rule is found, send a request to the matching rule's callback and delete the rule from the database
            if matching_rule:
                # Send a request to the matching rule's callback
                callback_url = matching_rule[1]
                requests.put(callback_url, word)
                # Delete the rule from the database
                c.execute('DELETE FROM rules WHERE strings_to_match = :strings AND callback = :callback', {
                          'strings': matching_rule[0], 'callback': matching_rule[1]})
                return 'Rule matched: ' + word
        # If no rule is found, save the order in the database
        c.execute('INSERT INTO orders VALUES (:message, :user_id, :timestamp)', {
                  'message': message, 'user_id': user_id, 'timestamp': timestamp})
    return 'No matching rule found, order saved in order queue'


run(host='::1', port=49124)
