import datetime
import json
from typing import Iterable
from bottle import post, run, request
from fuzzywuzzy import fuzz
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
            '''CREATE TABLE IF NOT EXISTS rules (strings_to_match text, callback text, available_hours text)''')


create_tables()


# Take order

@post('/order')
def index():
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        data = request.forms
        message = data['message']
        user_id = data['user_id']
        timestamp = int(data['timestamp'])
        new_order = Order(message, user_id, timestamp)
        # Repeat until a matching rule is found or the order is saved
        while True:
            # Check if a matching rule can be found
            matched_word, matching_rule = find_matching_rule(
                db_cursor, message, timestamp)
            # If a matching rule is found, delete the rule
            if matching_rule:
                delete_rule(db_cursor, matching_rule)
                # Tell CPEE about matched rule. If successful, return info to user. If not, try again
                if send_matched_rule(matching_rule, user_id, timestamp):
                    return f'Rule matched: Found {matched_word} in rule {matching_rule[0]}'
            # If no matching rule is found, save the order in the order queue
            else:
                save_order(db_cursor, message, user_id, timestamp)
                return 'Your order cannot be yet fulfilled, we saved it and will contact you as soon as it is fulfilled.'


# Find matching rule in database

def find_matching_rule(db_cursor: sqlite3.Cursor, message: str, timestamp: int):
    # Search for longer message words in rules
    words = message.split()
    for word in words:
        # Ignore words with less than 4 characters like 'a', 'the', 'and'
        if len(word) < 4:
            continue
        # Check if matching rules can be found and if one of them matches time-wise
        db_cursor.execute('SELECT * FROM rules WHERE strings_to_match LIKE :word',
                          {'word': '%' + word + '%'})
        matching_rules = db_cursor.fetchall()
        if matching_rules:
            matching_rule = time_based_matching_rule(matching_rules, timestamp)
            if matching_rule:
                return word, matching_rule
    # If no matching rule can be found, get all rules and use fuzzy matching to find highest match
    db_cursor.execute('SELECT * FROM rules')
    rules = db_cursor.fetchall()
    # Iterate over all rules
    for rule in rules:
        # Search for cocktail of the rule in the message
        if fuzz.partial_ratio(message, rule[0]) >= 60 and time_based_matching_rule([rule], timestamp):
            return 'a partially matching cocktail', rule
    # If no matching rule can be found, return None
    return None, None


# Check, if order was made within the time of any matched rule

def time_based_matching_rule(matched_rules: Iterable, timestamp: int):
    for rule in matched_rules:
        available_from = int(rule[2].split('-')[0])
        available_to = int(rule[2].split('-')[1])
        timestamp_date_object = datetime.datetime.fromtimestamp(timestamp)
        print(timestamp_date_object.hour)
        if available_from <= timestamp_date_object.hour <= available_to:
            return rule
    return None


# Tell CPEE about matched rule and delete rule from database

def send_matched_rule(matching_rule, user_id, timestamp):
    callback_url = matching_rule[1]
    # Tell CPEE about matched rule
    headers = {'Content-Type': 'application/json'}
    response = requests.put(callback_url, json.dumps(
        {'user_id': user_id, 'cocktail': matching_rule[0], 'timestamp': timestamp}), headers=headers)
    return response.status_code == 200


def delete_rule(db_cursor, matching_rule):
    # Delete matched rule from database
    db_cursor.execute('DELETE FROM rules WHERE callback = :callback', {
                      'callback': matching_rule[1]})


# Save order to database

def save_order(db_cursor, message, user_id, timestamp):
    db_cursor.execute('INSERT INTO orders VALUES (:message, :user_id, :timestamp)', {
        'message': message, 'user_id': user_id, 'timestamp': timestamp})


run(host='::1', port=49124)
