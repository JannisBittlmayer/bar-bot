import requests
import json
from bottle import route, run, request

# Load config from config.json
with open('src/config.json') as config_file:
    config = json.load(config_file)
    token = config['token']


@route('/message')
def message():
    user_id = request.query.user_id
    message = request.query.message
    send_discord_message(user_id, message)
    return 'Message sent'


def send_discord_message(user_id, message):
    headers = {
        'Authorization': 'Bot ' + token,
        'Content-Type': 'application/json',
    }

    # Create DM
    response = requests.post(
        'https://discord.com/api/v8/users/@me/channels',
        headers=headers,
        data=json.dumps({'recipient_id': user_id})
    )
    dm_id = response.json().get('id')

    # Send message
    requests.post(
        f'https://discord.com/api/v8/channels/{dm_id}/messages',
        headers=headers,
        data=json.dumps({'content': message})
    )


run(host='::1', port=49126)
