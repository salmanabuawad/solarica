def estimate_finish_date(planned_total_qty: float, completed_qty: float, avg_daily_output: float):
    if avg_daily_output <= 0:
        return None
    remaining = max(planned_total_qty - completed_qty, 0)
    return remaining / avg_daily_output
