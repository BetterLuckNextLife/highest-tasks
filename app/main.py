from flask import Flask
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


@app.route("/")
def index():
    return "Flask test"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7007, debug=True)
