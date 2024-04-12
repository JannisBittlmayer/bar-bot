import json
from bottle import post, run, request
from fuzzywuzzy import fuzz
import sqlite3
import requests as requestslib
from order import Order


# Create tables if not present yet

def create_tables():
    with sqlite3.connect('database.db') as conn:
        c = conn.cursor()
        c.execute(
            '''CREATE TABLE IF NOT EXISTS orders 
            (message TEXT, user_id TEXT, timestamp INTEGER, order_id TEXT, processing BOOLEAN)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS rules 
            (strings_to_match TEXT, callback TEXT, instance_id TEXT, rule_id TEXT, processing BOOLEAN)''')
        c.execute(
            '''CREATE TABLE IF NOT EXISTS rejected_matches 
            (order_id TEXT, rule_id TEXT)''')


create_tables()


# Take order

@post('/order')
def order():
    data = request.forms
    message = data['message']
    user_id = data['user_id']
    timestamp = int(data['timestamp'])
    order_id = data['order_id']
    # Set order to processing so no one can "snipe" it during processing
    order_status = True
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        save_order(db_cursor, message, user_id,
                   timestamp, order_id, order_status)
        # This only loops if a match was found but the callback was dead
        while True:
            # Check if a matching rule can be found
            matching_rule = find_matching_rule(db_cursor, message)
            # If there's a match, continue if the corresponding instance is available
            if matching_rule:
                set_rule_status(db_cursor, matching_rule[3], True)
                # True if rule was processing before status update or instance is busy because of another rule
                if matching_rule[4] or is_instance_busy(db_cursor, matching_rule[2], matching_rule[3]):
                    if not matching_rule[4]:
                        set_rule_status(db_cursor, matching_rule[3], False)
                    set_order_status(db_cursor, order_id, False)
                    return (f'The cocktail "{matching_rule[0]}" is on the menu but the robot is busy. '
                            'You will receive updates on your order via DM!')
                # Try telling CPEE about match via callback
                successfully_sent = send_matched_rule(
                    matching_rule, user_id, timestamp, order_id)
                # From here on, the matched rule stays in the processing state until it is deleted
                if successfully_sent:
                    return f'The cocktail "{matching_rule[0]}" is on the menu. You will receive updates on your order via DM!'
                else:
                    # Callback returns error -> CPEE task is completed and rule cannot be matched anymoree
                    delete_rule(db_cursor, matching_rule[3])
            # If no matching rule is found, inform user and set order to not processing
            else:
                set_order_status(db_cursor, order_id, False)
                return 'Your order cannot be yet fulfilled, we saved it and will contact you as soon as it is fulfilled.'


# Accept or reject match

@post('/accept_match')
def accept_match():
    data = request.forms
    rule_id = data['rule_id']
    order_id = data['order_id']
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        # Rule will be deleted once the same rule is set again so rule stays
        delete_count = delete_order(db_cursor, order_id)
    return f'Deleted rows (normally 1): {delete_count}'


@post('/reject_match')
def reject_match():
    data = request.forms
    rule_id = data['rule_id']
    order_id = data['order_id']
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        set_order_status(db_cursor, order_id, False)
        db_cursor.execute('INSERT INTO rejected_matches VALUES (:order_id, :rule_id)',
                          {'order_id': order_id, 'rule_id': rule_id})
    return f'Order freed'


# Find matching rule in database

def find_matching_rule(db_cursor: sqlite3.Cursor, message: str):
    words = message.split()
    # If possible, return an available rule, as backup return a processing rule
    backup_rules = []
    for word in words:
        # Ignore words with less than 4 characters like 'a', 'the', 'and'
        if len(word) < 4:
            continue
        # Check if matching rule can be found
        db_cursor.execute('SELECT * FROM rules WHERE strings_to_match LIKE :word',
                          {'word': '%' + word + '%'})
        for rule in db_cursor.fetchall():
            if not rule[4]:
                return rule
            elif rule not in backup_rules:
                backup_rules.append(rule)
    if len(backup_rules) > 0:
        return backup_rules[0]
    # If no matching rule can be found, get all rules and use fuzzy matching to find highest match
    db_cursor.execute('SELECT * FROM rules')
    rules = db_cursor.fetchall()
    # Iterate over all rules
    for rule in rules:
        # Search for cocktail of the rule in the message
        if fuzz.partial_ratio(message, rule[0]) >= 60:
            if not rule[4]:
                return rule
            elif rule not in backup_rules:
                backup_rules.append(rule)
    if len(backup_rules) > 0:
        return backup_rules[0]
    # If no matching rule can be found, return None
    return None


# Tell CPEE about matched rule and delete rule from database

def send_matched_rule(matching_rule, user_id, timestamp, order_id):
    callback_url = matching_rule[1]
    # Tell CPEE about matched rule
    headers = {'Content-Type': 'application/json'}
    response = requestslib.put(callback_url, json.dumps(
        {'rule_id': matching_rule[3], 'order_id': order_id, 'user_id': user_id,
         'cocktail': matching_rule[0], 'timestamp': timestamp}), headers=headers)
    return response.status_code == 200


# Delete order/rule from database

def delete_order(db_cursor, order_id: str):
    db_cursor.execute('DELETE FROM orders WHERE order_id = :order_id', {
                      'order_id': order_id})
    db_cursor.connection.commit()
    deleted_rows_count = db_cursor.rowcount
    # Also delete rejected matches
    db_cursor.execute('DELETE FROM rejected_matches WHERE order_id = :order_id', {
                      'order_id': order_id})
    db_cursor.connection.commit()
    return deleted_rows_count


def delete_rule(db_cursor, rule_id: str):
    db_cursor.execute('DELETE FROM rules WHERE rule_id = :rule_id', {
                      'rule_id': rule_id})
    db_cursor.connection.commit()
    deleted_rows_count = db_cursor.rowcount
    return deleted_rows_count


# Set status of order/rule

def set_order_status(db_cursor: sqlite3.Cursor, order_id: str, processing: bool):
    db_cursor.execute('UPDATE orders SET processing = :processing WHERE order_id = :order_id', {
        'processing': processing, 'order_id': order_id})
    db_cursor.connection.commit()


def set_rule_status(db_cursor: sqlite3.Cursor, rule_id: str, processing: bool):
    db_cursor.execute('UPDATE rules SET processing = :processing WHERE rule_id = :rule_id', {
        'processing': processing, 'rule_id': rule_id})
    db_cursor.connection.commit()


# Save order to database

def save_order(db_cursor, message, user_id, timestamp, order_id, status):
    db_cursor.execute('INSERT INTO orders VALUES (:message, :user_id, :timestamp, :order_id, :status)', {
        'message': message, 'user_id': user_id, 'timestamp': timestamp, 'order_id': order_id, 'status': status})
    db_cursor.connection.commit()


# Check if instance is busy

def is_instance_busy(db_cursor: sqlite3.Cursor, instance_id: str, exclude_rule_id: str = None):
    # Check if instance has a rule which is being processed. Optional: exclude rule from check
    if exclude_rule_id is not None:
        db_cursor.execute(
            'SELECT * FROM rules WHERE instance_id = :instance_id AND processing = :processing AND rule_id != :rule_id',
            {'instance_id': instance_id, 'processing': True, 'rule_id': exclude_rule_id})
    else:
        db_cursor.execute(
            'SELECT * FROM rules WHERE instance_id = :instance_id AND processing = :processing',
            {'instance_id': instance_id, 'processing': True})
    return db_cursor.fetchone() is not None


run(host='::1', port=49124)
