
from alpaca.trading.models import Order

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
            'id': str(response.id),
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
            'asset_id': str(response.asset_id),
            'symbol': response.symbol,
            'asset_class': response.asset_class.value,
            'notional': response.notional,
            'qty': response.qty,
            'filled_qty': response.filled_qty,
            'filled_avg_price': response.filled_avg_price,
            'order_class': response.order_class.value,
            'order_type': response.order_type.value,
            'type': response.type.value,
            'side': response.side.value,
            'time_in_force': response.time_in_force.value,
            'limit_price': response.limit_price,
            'stop_price': response.stop_price,
            'status': response.status.value,
            'extended_hours': response.extended_hours,
            'legs': [],
            'trail_percent': response.trail_percent,
            'trail_price': response.trail_price,
            'hwm': response.hwm
        }
        if response.legs:
            response_dict['legs'] = [
                {
                    'asset_class': leg.asset_class.value,
                    'asset_id': str(leg.asset_id),
                    'canceled_at': leg.canceled_at,
                    'client_order_id': leg.client_order_id,
                    'created_at': leg.created_at.strftime('%Y-%m-%d, %H:%M:%S'),
                    'expired_at': leg.expired_at,
                    'extended_hours': leg.extended_hours,
                    'failed_at': leg.failed_at,
                    'filled_at': leg.filled_at,
                    'filled_avg_price': leg.filled_avg_price,
                    'filled_qty': leg.filled_qty,
                    'hwm': leg.hwm,
                    'id': str(leg.id),
                    'legs': leg.legs,
                    'limit_price': leg.limit_price,
                    'notional': leg.notional,
                    'order_class': leg.order_class.value,
                    'order_type': leg.order_type.value,
                    'qty': leg.qty,
                    'replaced_at': leg.replaced_at,
                    'replaced_by': leg.replaced_by,
                    'replaces': leg.replaces,
                    'side': leg.side.value,
                    'status': leg.status.value,
                    'stop_price': leg.stop_price,
                    'submitted_at': leg.submitted_at.strftime('%Y-%m-%d, %H:%M:%S'),
                    'symbol': leg.symbol,
                    'time_in_force': leg.time_in_force.value,
                    'trail_percent': leg.trail_percent,
                    'trail_price': leg.trail_price,
                    'type': leg.type.value,
                    'updated_at': leg.updated_at.strftime('%Y-%m-%d, %H:%M:%S')
                }
                for leg in response.legs
            ]
        return response_dict
    else:
        raise ValueError("Invalid response object. Expected an instance of Order.")