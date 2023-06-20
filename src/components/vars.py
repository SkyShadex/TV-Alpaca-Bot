


def webhook(webhook_message):
        symbol_WH = webhook_message['ticker']
        side_WH = webhook_message['strategy']['order_action']
        price_WH= webhook_message['strategy']['order_price']
        quantity_WH = webhook_message['strategy']['order_contracts']
        comment_WH = webhook_message['strategy']['comment']
        orderID_WH = webhook_message['strategy']['order_id']

        return symbol_WH,side_WH,price_WH,quantity_WH,comment_WH,orderID_WH

def extract_order_response(response):
    if isinstance(response, Order):
        response_dict = {
            'id': response.id,
            'client_order_id': response.client_order_id,
            'created_at': response.created_at.strftime('%m-%d-%Y, %H:%M:%S'),
            'updated_at': response.updated_at.strftime('%m-%d-%Y, %H:%M:%S'),
            'submitted_at': response.submitted_at.strftime('%m-%d-%Y, %H:%M:%S'),
            'filled_at': response.filled_at,
            'expired_at': response.expired_at,
            'canceled_at': response.canceled_at,
            'failed_at': response.failed_at,
            'replaced_at': response.replaced_at,
            'replaced_by': response.replaced_by,
            'replaces': response.replaces,
            'asset_id': response.asset_id,
            'symbol': response.symbol,
            'asset_class': response.asset_class,
            'notional': response.notional,
            'qty': response.qty,
            'filled_qty': response.filled_qty,
            'filled_avg_price': response.filled_avg_price,
            'order_class': response.order_class,
            'order_type': response.order_type,
            'type': response.type,
            'side': response.side,
            'time_in_force': response.time_in_force,
            'limit_price': response.limit_price,
            'stop_price': response.stop_price,
            'status': response.status,
            'extended_hours': response.extended_hours,
            'legs': response.legs,
            'trail_percent': response.trail_percent,
            'trail_price': response.trail_price,
            'hwm': response.hwm
        }
        return response_dict
    else:
        raise ValueError("Invalid response object. Expected an instance of Order.")