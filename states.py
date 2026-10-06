from aiogram.fsm.state import State, StatesGroup


class CalculatorStates(StatesGroup):
    waiting_for_price = State()
    waiting_for_weight = State()
    waiting_for_city = State()
    waiting_for_delivery = State()


class OrderStates(StatesGroup):
    waiting_for_item = State()
    waiting_for_price = State()
    waiting_for_weight = State()
    waiting_for_city = State()
    waiting_for_delivery = State()
    waiting_for_details = State()
    waiting_for_recipient = State()
    waiting_for_address = State()
    waiting_for_phone = State()


class AdminStates(StatesGroup):
    waiting_for_broker_cny = State()
    waiting_for_cny_low = State()
    waiting_for_cny_high = State()
    waiting_for_usd = State()
    waiting_for_reject_reason = State()
    waiting_for_cancel_id = State()
    waiting_for_cancel_reason = State()
    waiting_for_restore_id = State()
    waiting_for_order_track = State()
    waiting_for_rm_track_id = State()
    waiting_for_rm_track_val = State()
    waiting_for_edit_weight_id = State()
    waiting_for_edit_weight_val = State()
    waiting_for_shipment_name = State()
    waiting_for_shipment_track = State()
    waiting_for_msk_ship_order_id = State()
    waiting_for_delete_order_id = State()
    waiting_for_ban_id = State()
    waiting_for_unban_id = State()
    waiting_for_ticket_photo = State()
    waiting_for_ticket_photo_caption = State()
    waiting_for_shipment_update = State()
    waiting_for_ticket_search = State()
