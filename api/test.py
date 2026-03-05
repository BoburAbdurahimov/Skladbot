from flask import Flask, jsonify
import sys
import traceback
import os

app = Flask(__name__)

@app.route('/api/test')
def test():
    try:
        import libsql_experimental
        
        url = os.environ.get("TURSO_DATABASE_URL", "missing")
        token = os.environ.get("TURSO_AUTH_TOKEN", "missing")
        
        conn = libsql_experimental.connect("test.db", sync_url=url, auth_token=token)
        conn.sync()
        
        return jsonify({
            "status": "success",
            "message": "libsql_experimental imported and synced successfully",
            "url_loaded": url != "missing",
            "token_loaded": token != "missing"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e),
            "traceback": traceback.format_exc()
        }), 500

if __name__ == '__main__':
    app.run(debug=True)
