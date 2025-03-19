from flask import Flask, render_template, request, abort, Response
from flask_cors import CORS
import datetime
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def load_cars():
    with open('cars.json', 'r') as f:
        return json.load(f)['cars']

def load_news():
    with open('news.json', 'r') as f:
        return json.load(f)['articles']

@app.route('/')
def home():
    featured_cars = load_cars()[:3]  # Get first 3 cars for featured section
    latest_news = load_news()[:3]    # Get latest 3 news articles
    return render_template('home.html', featured_cars=featured_cars, latest_news=latest_news)

@app.route('/cars')
def car_search():
    query = request.args.get('q', '')
    cars = load_cars()
    if query:
        filtered_cars = [car for car in cars if query.lower() in car['name'].lower()]
    else:
        filtered_cars = cars
    return render_template('car_search.html', cars=filtered_cars, query=query)

@app.route('/cars/<int:car_id>')
def car_details(car_id):
    cars = load_cars()
    car = next((car for car in cars if car['id'] == car_id), None)
    if not car:
        abort(404)
    return render_template('car_details.html', car=car)

@app.route('/news')
def news():
    news_articles = load_news()
    return render_template('news.html', news_articles=news_articles)

@app.route('/news/<int:news_id>')
def news_details(news_id):
    news_articles = load_news()
    article = next((article for article in news_articles if article['id'] == news_id), None)
    if not article:
        abort(404)
    return render_template('news_details.html', article=article)

@app.route('/sitemap.xml')
def sitemap():
    """Generate sitemap.xml"""
    pages = []
    base_url = request.url_root.rstrip('/')
    
    # Add static pages
    pages.append({
        'loc': base_url + '/',
        'lastmod': datetime.date.today().isoformat(),
        'priority': '1.0'
    })
    pages.append({
        'loc': base_url + '/cars',
        'lastmod': datetime.date.today().isoformat(),
        'priority': '0.8'
    })
    pages.append({
        'loc': base_url + '/news',
        'lastmod': datetime.date.today().isoformat(),
        'priority': '0.8'
    })
    
    # Add car detail pages
    for car in load_cars():
        pages.append({
            'loc': f"{base_url}/cars/{car['id']}",
            'lastmod': datetime.date.today().isoformat(),
            'priority': '0.7'
        })
    
    # Add news detail pages
    for article in load_news():
        pages.append({
            'loc': f"{base_url}/news/{article['id']}",
            'lastmod': article['date'],
            'priority': '0.6'
        })

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    return Response(sitemap_xml, mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True, port=5530)
