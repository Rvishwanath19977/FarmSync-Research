from dotenv import load_dotenv
from flask import Flask, jsonify, redirect

# Load optional local configuration.
# If .env does not exist, FarmSync continues with safe defaults.
load_dotenv()

from farmsync_routes import register_farmsync_routes


def create_app():
    app = Flask(__name__)

    app.config.setdefault("MAX_CONTENT_LENGTH", 60 * 1024 * 1024)

    register_farmsync_routes(app)

    @app.route("/")
    def index():
        return redirect("/farm-sync")

    @app.route("/healthz")
    def healthz():
        return jsonify({
            "status": "ok",
            "application": "FarmSync-Research",
        })

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=False,
    )
