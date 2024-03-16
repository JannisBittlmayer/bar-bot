from bottle import route, run, request
import sqlite3
import requests
from rule import Rule

conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create tables if not present yet
with conn:
  c.execute('''CREATE TABLE IF NOT EXISTS orders (message text, user_id text, timestamp integer)''')
  c.execute('''CREATE TABLE IF NOT EXISTS rules (strings_to_match text, callback text)''')

# Take new rule
@route('/add_rule')
def index():
  callback_url = request.headers.get('Cpee-Callback')
  strings_to_match = request.query.message
  # Create new Rule object
  new_rule = Rule(strings_to_match, callback_url)
  # Check, whether rule is already matched by a order
  cocktails = strings_to_match.split(',')
  for cocktail in cocktails:
    # Check if a matching order can be found
    with conn:
      c.execute('SELECT * FROM orders WHERE message LIKE :message', {'message': '%' + cocktail + '%'})
      matching_order = c.fetchone()
    # If order is found, send a request to the callback and delete the order from the database
    if matching_order:
      # Send a request to the callback ibcluding the user_id, when the order was placed and the cocktail
      requests.put(callback_url, json={'user_id': matching_order[1], 'cocktail': cocktail, 'timestamp': matching_order[2]})
      # Delete the order from the database
      with conn:
        c.execute('''DELETE FROM orders
           WHERE message = :message
           AND user_id = :user_id
           AND timestamp = :timestamp
           LIMIT 1''', {'message': matching_order[0], 'user_id': matching_order[1], 'timestamp': matching_order[2]})
      return 'Order matched: ' + cocktail
  # If no order is found, save the rule in the database
  with conn:
    c.execute('INSERT INTO rules VALUES (:strings_to_match, :callback)', {'strings_to_match': strings_to_match, 'callback': callback_url})
  return 'No matching order found, rule saved in rule queue'

run(host='::1', port=49125)