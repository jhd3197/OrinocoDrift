from flask import Flask, render_template, request, abort, Response
from flask_cors import CORS
import datetime
import json

# Bot Detection Configuration
BOT_DETECTION = {
    'enabled': True,
    'user_agent_patterns': [
        'bot', 'crawler', 'spider', 'scrape',
        'phantomjs', 'selenium', 'headless'
    ],
    'request_patterns': {
        'max_requests_per_minute': 60,
        'suspicious_patterns': {
            'sequential_access': True,  # Detect sequential ID access
            'time_pattern_access': True # Detect systematic time parameter access
        }
    }
}

# Rate Limiting Configuration
RATE_LIMITS = {
    'global': {
        'requests_per_minute': 60,
        'requests_per_hour': 1000
    },
    'endpoints': {
        '/cars': {'requests_per_minute': 30},
        '/brokers': {'requests_per_minute': 30},
        '/news': {'requests_per_minute': 30}
    },
    'cooldown_period': 300  # 5 minutes in seconds
}

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

def get_current_date():
    """Return the current date in YYYY-MM-DD format"""
    return datetime.date.today().isoformat()

def parse_date_param(date_param):
    """Parse date parameter from URL, which can be a year, year.month, or full date"""
    if not date_param:
        return get_current_date()
    
    try:
        # Check if it's a float (year.month format)
        if '.' in date_param:
            year_month = float(date_param)
            year = int(year_month)
            month = int((year_month % 1) * 12) + 1
            return f"{year}-{month:02d}-01"
        # Check if it's just a year
        elif len(date_param) == 4 and date_param.isdigit():
            return f"{date_param}-01-01"
        # Otherwise assume it's a full date
        else:
            # Validate date format
            datetime.datetime.strptime(date_param, '%Y-%m-%d')
            return date_param
    except (ValueError, TypeError):
        # If any parsing error, return current date
        return get_current_date()

def filter_by_time(date_param):
    """Convert date parameter to start and end dates for filtering"""
    date_str = parse_date_param(date_param)
    
    # Parse the date components
    parts = date_str.split('-')
    year = int(parts[0])
    month = int(parts[1])
    
    # If it's just a year (month is 1)
    if month == 1 and parts[2] == '01':
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
    # If it's a specific month
    elif parts[2] == '01':
        start_date = f"{year}-{month:02d}-01"
        # Get last day of month
        if month == 12:
            end_date = f"{year}-12-31"
        else:
            next_month = datetime.date(year, month, 1) + datetime.timedelta(days=32)
            next_month = next_month.replace(day=1) - datetime.timedelta(days=1)
            end_date = next_month.isoformat()
    # If it's a specific day
    else:
        start_date = date_str
        end_date = date_str
    
    return start_date, end_date

def generate_date_for_item(item_id, selected_date_str=None):
    """
    Generate a date for an item based on its ID and the selected date
    """
    # If no selected date, use current date
    if not selected_date_str:
        current_date = datetime.date.today()
    else:
        current_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    
    # Use the item_id to determine the day of the month (1-28)
    day = (item_id % 28) + 1
    
    # Create a date with the current year/month and the calculated day
    item_date = datetime.date(
        year=current_date.year,
        month=current_date.month,
        day=min(day, 28)  # Ensure valid day for all months
    )
    
    return item_date.isoformat()

def generate_timestamp_for_item(item_id, selected_date_str=None):
    """
    Generate a timestamp for an item based on its ID and the selected date
    """
    # Generate the date part
    date_part = generate_date_for_item(item_id, selected_date_str)
    
    # Use the item_id to determine the hour and minute
    hour = (item_id % 12) + 8  # 8 AM to 8 PM
    minute = (item_id * 7) % 60  # 0-59 minutes
    
    # Create the timestamp
    return f"{date_part}T{hour:02d}:{minute:02d}:00"

def determine_visibility(item_id, selected_date_str):
    """
    Determine if an item should be visible based on its ID and the selected date
    This creates a pattern where items appear and disappear throughout the year
    """
    if not selected_date_str:
        return True
    
    selected_date = datetime.datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    month = selected_date.month
    
    # Use the item_id to create a pattern of visibility
    # Each item will be visible for a specific range of months
    visibility_start = (item_id % 12) + 1  # 1-12
    visibility_duration = max(1, (item_id % 6) + 3)  # 3-8 months
    
    # Calculate end month with wraparound
    visibility_end = ((visibility_start + visibility_duration - 1) % 12) + 1
    
    # Check if current month is within visibility range
    if visibility_start <= visibility_end:
        return visibility_start <= month <= visibility_end
    else:  # Wraparound case (e.g., Nov-Feb)
        return month >= visibility_start or month <= visibility_end

def load_cars(date_param=None):
    with open('cars.json', 'r') as f:
        cars = json.load(f)['cars']
        
        if not date_param:
            # If no date parameter, return all cars with generated dates
            result_cars = []
            for car in cars:
                car_copy = car.copy()
                car_copy['manufacture_date'] = generate_date_for_item(car['id'] * 3)
                car_copy['listing_start_date'] = generate_date_for_item(car['id'] * 2)
                
                # Calculate end date (6-12 months after start date)
                start_date = datetime.datetime.strptime(car_copy['listing_start_date'], '%Y-%m-%d').date()
                duration_months = 6 + (car['id'] % 7)  # 6-12 months
                end_date = start_date.replace(year=start_date.year + 1) if start_date.month + duration_months > 12 else start_date.replace(month=min(start_date.month + duration_months, 12))
                car_copy['listing_end_date'] = end_date.isoformat()
                
                result_cars.append(car_copy)
            return result_cars
        
        # Parse the selected date
        selected_date = parse_date_param(date_param)
        
        filtered_cars = []
        for car in cars:
            # Determine if this car should be visible based on its ID and the selected date
            if determine_visibility(car['id'], selected_date):
                # Create a copy of the car to modify
                car_copy = car.copy()
                
                # Generate dates based on the car's ID and selected date
                car_copy['manufacture_date'] = generate_date_for_item(car['id'] * 3, selected_date)
                car_copy['listing_start_date'] = generate_date_for_item(car['id'] * 2, selected_date)
                
                # Calculate end date (6-12 months after start date)
                start_date = datetime.datetime.strptime(car_copy['listing_start_date'], '%Y-%m-%d').date()
                duration_months = 6 + (car['id'] % 7)  # 6-12 months
                
                # For simplicity, just add days instead of calculating exact months
                end_date = start_date + datetime.timedelta(days=duration_months * 30)
                car_copy['listing_end_date'] = end_date.isoformat()
                
                # Add price history based on the selected date
                car_copy['price_history'] = [
                    {"date": generate_date_for_item(car['id'] * 5, selected_date), "price": car['price']},
                    {"date": generate_date_for_item(car['id'] * 7, selected_date), "price": f"${int(car['price'].replace('$', '').replace(',', '')) * 1.05:,.0f}"}
                ]
                
                # Add the car to the filtered list
                filtered_cars.append(car_copy)
        
        return filtered_cars

def load_news(date_param=None):
    with open('news.json', 'r') as f:
        articles = json.load(f)['articles']
        
        if not date_param:
            # If no date parameter, return all articles with generated dates
            result_articles = []
            for article in articles:
                article_copy = article.copy()
                article_copy['date'] = generate_date_for_item(article['id'])
                article_copy['timestamp'] = generate_timestamp_for_item(article['id'])
                result_articles.append(article_copy)
            return result_articles
        
        # Parse the selected date
        selected_date = parse_date_param(date_param)
        
        filtered_articles = []
        for article in articles:
            # Determine if this article should be visible based on its ID and the selected date
            if determine_visibility(article['id'], selected_date):
                # Create a copy of the article to modify
                article_copy = article.copy()
                
                # Generate dates based on the article's ID and selected date
                article_copy['date'] = generate_date_for_item(article['id'], selected_date)
                article_copy['timestamp'] = generate_timestamp_for_item(article['id'], selected_date)
                
                # Add the article to the filtered list
                filtered_articles.append(article_copy)
        
        return filtered_articles

def load_brokers(date_param=None):
    with open('brokers.json', 'r') as f:
        brokers = json.load(f)['brokers']
        
        if not date_param:
            # If no date parameter, return all brokers with generated dates
            result_brokers = []
            for broker in brokers:
                broker_copy = broker.copy()
                broker_copy['join_date'] = generate_date_for_item(broker['id'] * 4)
                
                # Only some brokers have end dates (those with even IDs)
                if broker['id'] % 2 == 0:
                    broker_copy['end_date'] = generate_date_for_item(broker['id'] * 6)
                
                result_brokers.append(broker_copy)
            return result_brokers
        
        # Parse the selected date
        selected_date = parse_date_param(date_param)
        
        filtered_brokers = []
        for broker in brokers:
            # Determine if this broker should be visible based on its ID and the selected date
            if determine_visibility(broker['id'], selected_date):
                # Create a copy of the broker to modify
                broker_copy = broker.copy()
                
                # Generate dates based on the broker's ID and selected date
                broker_copy['join_date'] = generate_date_for_item(broker['id'] * 4, selected_date)
                
                # Only some brokers have end dates (those with even IDs)
                if broker['id'] % 2 == 0:
                    broker_copy['end_date'] = generate_date_for_item(broker['id'] * 6, selected_date)
                
                # Add the broker to the filtered list
                filtered_brokers.append(broker_copy)
        
        return filtered_brokers

# Helper function to preserve date parameter across pages
def add_date_to_template_context():
    date_param = request.args.get('date', None)
    return {'current_date': date_param}

@app.context_processor
def inject_date():
    return add_date_to_template_context()

@app.route('/')
def home():
    date_param = request.args.get('date', None)
    featured_cars = load_cars(date_param)[:3]  # Get first 3 cars for featured section
    latest_news = load_news(date_param)[:3]    # Get latest 3 news articles
    # Get top 3 brokers sorted by rating
    all_brokers = load_brokers(date_param)
    featured_brokers = sorted(all_brokers, key=lambda x: x['rating'], reverse=True)[:3]
    return render_template('home.html', 
                         featured_cars=featured_cars, 
                         latest_news=latest_news,
                         featured_brokers=featured_brokers)

@app.route('/cars')
def car_search():
    query = request.args.get('q', '')
    date_param = request.args.get('date', None)
    cars = load_cars(date_param)
    if query:
        filtered_cars = [car for car in cars if query.lower() in car['name'].lower()]
    else:
        filtered_cars = cars
    return render_template('car_search.html', cars=filtered_cars, query=query)

@app.route('/cars/<int:car_id>')
def car_details(car_id):
    date_param = request.args.get('date', None)
    cars = load_cars(date_param)
    car = next((car for car in cars if car['id'] == car_id), None)
    if not car:
        abort(404)
    return render_template('car_details.html', car=car)

@app.route('/news')
def news():
    date_param = request.args.get('date', None)
    news_articles = load_news(date_param)
    return render_template('news.html', news_articles=news_articles)

@app.route('/news/<int:news_id>')
def news_details(news_id):
    date_param = request.args.get('date', None)
    news_articles = load_news(date_param)
    article = next((article for article in news_articles if article['id'] == news_id), None)
    if not article:
        abort(404)
    return render_template('news_details.html', article=article)

@app.route('/brokers')
def broker_search():
    query = request.args.get('q', '')
    date_param = request.args.get('date', None)
    brokers = load_brokers(date_param)
    if query:
        filtered_brokers = [broker for broker in brokers if query.lower() in broker['name'].lower() 
                           or query.lower() in broker['specialization'].lower()]
    else:
        filtered_brokers = brokers
    return render_template('broker_search.html', brokers=filtered_brokers, query=query)

@app.route('/brokers/<int:broker_id>')
def broker_details(broker_id):
    date_param = request.args.get('date', None)
    brokers = load_brokers(date_param)
    broker = next((broker for broker in brokers if broker['id'] == broker_id), None)
    if not broker:
        abort(404)
    cars = load_cars(date_param)
    return render_template('broker_details.html', broker=broker, cars=cars)

@app.route('/simulate-day')
def simulate_day():
    """Endpoint to simulate the passage of a day for testing crawlers"""
    current_date = request.args.get('current_date', get_current_date())
    
    # Parse the current date
    date_obj = datetime.datetime.strptime(current_date, '%Y-%m-%d').date()
    
    # Add one day
    next_date = (date_obj + datetime.timedelta(days=1)).isoformat()
    
    # Redirect to home with the new date
    return render_template('simulate_day.html', 
                          current_date=current_date, 
                          next_date=next_date)

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
    pages.append({
        'loc': base_url + '/brokers',
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
    
    # Add broker detail pages
    for broker in load_brokers():
        pages.append({
            'loc': f"{base_url}/brokers/{broker['id']}",
            'lastmod': datetime.date.today().isoformat(),
            'priority': '0.7'
        })

    sitemap_xml = render_template('sitemap.xml', pages=pages)
    return Response(sitemap_xml, mimetype='application/xml')

if __name__ == '__main__':
    app.run(debug=True, port=5530)
