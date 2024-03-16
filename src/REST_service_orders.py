from bottle import route, run, request
import sqlite3
import requests
from order import Order
  
conn = sqlite3.connect('database.db')
c = conn.cursor()

# Create tables if not present yet
with conn:
  c.execute('''CREATE TABLE IF NOT EXISTS orders (message text, user_id text, timestamp integer)''')
  c.execute('''CREATE TABLE IF NOT EXISTS rules (strings_to_match text, callback text)''')

# Take order  
@route('/order')
def index():
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
    with conn:
      c.execute('SELECT * FROM rules WHERE strings_to_match LIKE :strings', {'strings': '%' + word + '%'})
      matching_rule = c.fetchone()
    # If rule is found, send a request to the matching rule's callback
    if matching_rule:
      # Send a request to the matching rule's callback
      callback_url = matching_rule[1]
      requests.put(callback_url, word)
      return 'Rule matched: ' + word
  # If no rule is found, save the order in the database
  with conn:
    c.execute('INSERT INTO orders VALUES (:message, :user_id, :timestamp)', {'message': message, 'user_id': user_id, 'timestamp': timestamp})
  return 'No matching rule found, order saved in order queue'

conn.close()
run(host='::1', port=49124)