from app.tasks.celery_app import celery_app

@celery_app.task
def run_validation(run_id: int):
    # TODO: load parsed design data, active rules, create issues
    return {"run_id": run_id, "status": "todo"}
