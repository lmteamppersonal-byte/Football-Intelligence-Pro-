from flask import Flask, Response
import threading
from prometheus_client import Counter, generate_latest

app = Flask(__name__)

# Basic Scraper Metrics
SCRAPE_REQUESTS_TOTAL = Counter('scrape_requests_total', 'Total number of scraping requests made')
SCRAPE_403_TOTAL = Counter('scrape_403_total', 'Total number of 403 Forbidden errors')
SCRAPE_RETRIES_TOTAL = Counter('scrape_retries_total', 'Total number of scraping retries')
SCRAPE_SELENIUM_FALLBACKS_TOTAL = Counter('scrape_selenium_fallbacks_total', 'Total number of Selenium fallbacks used')

@app.route('/metrics')
def metrics():
    return Response(generate_latest(), mimetype="text/plain")

@app.route('/health')
def health_check():
    return {"status": "ok"}, 200

def start_exporter(port=9090):
    """Call this function to run the exporter in a background thread."""
    t = threading.Thread(target=app.run, kwargs={"host": "0.0.0.0", "port": port}, daemon=True)
    t.start()

if __name__ == '__main__':
    # Simulating some metrics explicitly in a test environment
    SCRAPE_REQUESTS_TOTAL.inc(10)
    SCRAPE_403_TOTAL.inc(2)
    start_exporter(9090)
    app.run(host="0.0.0.0", port=9090)
