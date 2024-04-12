import REST_service_messages
import REST_service_orders
import REST_service_rules
from bottle import Bottle


if __name__ == "__main__":
    app = Bottle()
    REST_service_orders.create_tables()
    app.post('/order')(REST_service_orders.order)
    app.post('/accept_match')(REST_service_orders.accept_match)
    app.post('/reject_match')(REST_service_orders.reject_match)
    # TODO: Change to post endpoint if possible
    app.route('/add_rule')(REST_service_rules.add_rule)
    app.post('/message')(REST_service_messages.message)
    app.run(host='::1', port=49124)
