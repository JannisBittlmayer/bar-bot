import json
from bottle import route, run, request, response
from fuzzywuzzy import fuzz
import sqlite3
from rule import Rule


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


# Take new rule

# TODO: Change to post endpoint if possible
@route('/add_rule')
def add_rule():
    callback_url = request.headers.get('Cpee-Callback')
    instance_id = request.headers.get('Cpee-Instance-Uuid')
    strings_to_match = request.query.strings_to_match
    rule_id = request.query.rule_id
    rule_status = True
    with sqlite3.connect('database.db') as conn:
        db_cursor = conn.cursor()
        # Delete old rule and save new one
        delete_rule(db_cursor, rule_id)
        save_rule(strings_to_match, callback_url,
                  instance_id, rule_id, rule_status)
        # Don't look for match if instance is busy (very unlikely)
        if is_instance_busy(db_cursor, instance_id, rule_id):
            set_rule_status(db_cursor, rule_id, False)
            response.set_header('Cpee-Callback', 'true')
            return 'Instance is busy, rule saved in rule queue'
        # Check, whether rule is already matched by an order
        matching_order, matched_cocktail = find_matching_order(
            db_cursor, strings_to_match)
        # If order is found, set order to processing and return match
        if matching_order:
            set_order_status(db_cursor, matching_order[3], True)
            response.set_header('Content-Type', 'application/json')
            return json.dumps({'rule_id': rule_id, 'order_id': matching_order[3],
                               'user_id': matching_order[1], 'cocktail': matched_cocktail,
                               'timestamp': matching_order[2]})
        # If no order is found, save the rule and tell CPEE to wait for it to be fulfilled
        set_rule_status(db_cursor, rule_id, False)
        response.set_header('Cpee-Callback', 'true')
        return 'No matching order found, rule saved in rule queue'


# Find matching cocktail in orders in database

def find_matching_order(db_cursor: sqlite3.Cursor, strings_to_match: str, rule_id: str):
    cocktails = strings_to_match.split(', ')
    for cocktail in cocktails:
        # Check if matching orders can be found
        db_cursor.execute('SELECT * FROM orders WHERE message LIKE :cocktail',
                          {'cocktail': '%' + cocktail + '%'})
        matching_order = db_cursor.fetchone()
        if (matching_order and not matching_order[4] and not
                match_already_rejected(db_cursor, matching_order[3], rule_id)):
            return matching_order, cocktail
    # If no matching rule can be found, get all orders and use fuzzy matching to find highest match
    db_cursor.execute('SELECT * FROM orders')
    orders = db_cursor.fetchall()
    # Iterate over all orders
    for order in orders:
        # Iterate over all cocktails and search for them in existing orders
        for cocktail in cocktails:
            if (fuzz.partial_ratio(order[0], cocktail) >= 60 and not order[4] and not
                    match_already_rejected(db_cursor, order[3], rule_id)):
                return order, cocktail
    return None, None


# Save/delete rule in database

def save_rule(db_cursor, strings_to_match, callback_url, instance_id, rule_id, status):
    for cocktail in strings_to_match.split(', '):
        db_cursor.execute('INSERT INTO rules VALUES (:strings_to_match, :callback, :instance_id, :rule_id, :status)',
                          {'strings_to_match': cocktail, 'callback': callback_url, 'instance_id': instance_id,
                           'rule_id': rule_id, 'status': status})
    db_cursor.connection.commit()


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


# Check if rule - order pair was already rejected

def match_already_rejected(db_cursor: sqlite3.Cursor, order_id: str, rule_id: str):
    db_cursor.execute('SELECT * FROM rejected_matches WHERE order_id = :order_id AND rule_id = :rule_id',
                      {'order_id': order_id, 'rule_id': rule_id})
    return db_cursor.fetchone() is not None


run(host='::1', port=49125)
