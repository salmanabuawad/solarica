def projected_balance(current_qty: float, issued_qty: float, received_qty: float) -> float:
    return current_qty - issued_qty + received_qty
