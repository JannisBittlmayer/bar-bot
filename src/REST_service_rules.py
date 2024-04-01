import datetime
import json
from typing import Iterable
from bottle import route, run, request, response
from fuzzywuzzy import fuzz
import sqlite3
from rule import Rule


# Create tables if not present yet

def create_tables():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute(
            '''CREATE TABLE IF NOT EXISTS orders (message text, user_id text, timestamp integer)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS rules (strings_to_match text, callback text, available_hours text)''')


create_tables()


# Take new rule

@route('/add_rule')
def index():
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        callback_url = request.headers.get('Cpee-Callback')
        strings_to_match = request.query.strings_to_match
        available_hours = request.query.available_hours
        new_rule = Rule(strings_to_match, callback_url)
        # Check, whether rule is already matched by an order
        matching_order, matched_cocktail = find_matching_order(
            db_cursor, strings_to_match, available_hours)
        # If order is found, delete order and return info to user
        if matching_order:
            delete_order(db_cursor, matching_order)
            response.set_header('Content-Type', 'application/json')
            return json.dumps({'user_id': matching_order[1], 'cocktail': matched_cocktail, 'timestamp': matching_order[2]})
        # If no order is found, save the rule and tell CPEE to wait for it to be fulfilled
        save_rule(db_cursor, strings_to_match, callback_url, available_hours)
        response.set_header('Cpee-Callback', 'true')
    return 'No matching order found, rule saved in rule queue'


# Find matching cocktail in orders in database

def find_matching_order(db_cursor: sqlite3.Cursor, strings_to_match: str, available_hours: str):
    cocktails = strings_to_match.split(', ')
    for cocktail in cocktails:
        # Check if matching orders can be found and if one of them matches time-wise
        db_cursor.execute('SELECT * FROM orders WHERE message LIKE :cocktail',
                          {'cocktail': '%' + cocktail + '%'})
        matching_orders = db_cursor.fetchall()
        if matching_orders:
            matching_order = time_based_matching_order(
                matching_orders, available_hours)
            if matching_order:
                return matching_order, cocktail
    # If no matching rule can be found, get all orders and use fuzzy matching to find highest match
    db_cursor.execute('SELECT * FROM orders')
    orders = db_cursor.fetchall()
    # Iterate over all orders
    for order in orders:
        # Iterate over all cocktails and search for them in existing orders
        for cocktail in cocktails:
            if fuzz.partial_ratio(order[0], cocktail) >= 60 and time_based_matching_order([order], available_hours):
                return order, cocktail
    return None, None


# Check, if any order was made within the time of the rule

def time_based_matching_order(matched_orders: Iterable, available_hours: str):
    for order in matched_orders:
        available_from = int(available_hours.split('-')[0])
        available_to = int(available_hours.split('-')[1])
        timestamp_date_object = datetime.datetime.fromtimestamp(order[2])
        if available_from <= timestamp_date_object.hour <= available_to:
            return order
    return None


# Delete order from database

def delete_order(db_cursor, order):
    db_cursor.execute('''DELETE FROM orders
                    WHERE message = :message
                    AND user_id = :user_id
                    AND timestamp = :timestamp
                    LIMIT 1''', {'message': order[0], 'user_id': order[1], 'timestamp': order[2]})


# Save rule in database

def save_rule(db_cursor, strings_to_match, callback_url, available_hours):
    for cocktail in strings_to_match.split(', '):
        db_cursor.execute('INSERT INTO rules VALUES (:strings_to_match, :callback, :available_hours)', {
            'strings_to_match': cocktail, 'callback': callback_url, 'available_hours': available_hours})


run(host='::1', port=49125)
