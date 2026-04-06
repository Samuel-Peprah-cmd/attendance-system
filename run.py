from app import create_app
from app.extensions import socketio

app = create_app()


@app.cli.command("check-renewals")
def check_renewals_command():
    from app.tasks.renewal_tasks import process_expired_subscriptions
    process_expired_subscriptions(app)


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)








# from app import create_app

# app = create_app()

# @app.cli.command("check-renewals")
# def check_renewals_command():
#     from app.tasks.renewal_tasks import process_expired_subscriptions
#     process_expired_subscriptions(app)

# if __name__ == "__main__":
#     app.run(host='0.0.0.0', port=5000, debug=True)