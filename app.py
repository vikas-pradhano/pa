# Updated app.py

from flask import Flask, jsonify, request

app = Flask(__name__)

@app.route('/')
def index():
    return jsonify({'message': 'Welcome to the API!'})

# Consolidated index route, removing duplicates
@app.route('/index')
def index_redirect():
    return index()

if __name__ == '__main__':
    app.run(debug=True)