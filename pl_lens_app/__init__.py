"""Flask app for starting server."""

from flask import Flask

app = Flask(__name__)


import pl_lens_app.views
