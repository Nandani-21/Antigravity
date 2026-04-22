from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def index():
    """
    Serves the main dashboard. All computer vision and AI processing 
    is now handled completely client-side via JavaScript.
    """
    return render_template('index.html')

if __name__ == '__main__':
    # Use threaded=True to ensure the server doesn't block
    app.run(debug=True, threaded=True)
