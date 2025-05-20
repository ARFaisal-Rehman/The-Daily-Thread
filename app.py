from flask import Flask, request, jsonify, render_template, redirect, url_for, session
from flask_cors import CORS
import os
import random
import datetime # For timestamping purchase decisions
import pandas as pd # For reading data files
import glob # For finding data files
from collections import Counter # ADDED IMPORT
from pytrends.request import TrendReq # For Google Trends
import praw # For Reddit

import pandas as pd # Make sure pandas is imported
import datetime
from collections import Counter

def normalize_season(season_str):
    season_str = str(season_str).lower().strip()
    if not season_str or season_str == 'nan': return 'Unknown'
    if 'spring' in season_str: return 'Spring'
    if 'summer' in season_str: return 'Summer'
    if 'fall' in season_str or 'autumn' in season_str: return 'Fall'
    if 'winter' in season_str: return 'Winter'
    # Handle combined seasons like "Fall/Winter"
    if '/' in season_str:
        parts = season_str.split('/')
        # Prioritize common single season names if present
        for part in parts:
            if part in ['spring', 'summer', 'fall', 'winter']:
                return normalize_season(part) # Recursive call for simplicity
    return 'Unknown'

def extract_year(date_val):
    if pd.isna(date_val): return None
    try:
        if isinstance(date_val, (datetime.datetime, datetime.date)):
            return date_val.year
        # Try to convert to datetime and extract year
        dt = pd.to_datetime(date_val, errors='coerce')
        if pd.notna(dt):
            return dt.year
        # If it's already a year-like number
        if isinstance(date_val, (int, float)) and 1900 < date_val < 2100:
            return int(date_val)
        # Try extracting 4-digit number as a last resort
        match = pd.Series(str(date_val)).str.extract(r'(\d{4})')[0].iloc[0]
        if pd.notna(match):
            return int(match)
    except Exception:
        pass
    return None

def date_to_season(date_val):
    if pd.isna(date_val): return 'Unknown'
    try:
        dt = pd.to_datetime(date_val, errors='coerce')
        if pd.isna(dt): return 'Unknown'
        month = dt.month
        if month in [3, 4, 5]: return 'Spring'
        if month in [6, 7, 8]: return 'Summer'
        if month in [9, 10, 11]: return 'Fall'
        if month in [12, 1, 2]: return 'Winter'
    except Exception:
        pass
    return 'Unknown'

def get_age_group(age):
    if pd.isna(age): return 'Unknown'
    try:
        age = int(float(age)) # Convert to float first for strings like "25.0"
        if age < 18: return '<18'
        if 18 <= age <= 24: return '18-24'
        if 25 <= age <= 34: return '25-34'
        if 35 <= age <= 44: return '35-44'
        if 45 <= age <= 54: return '45-54'
        if age >= 55: return '55+'
    except ValueError:
        pass # If age is not a number
    return 'Unknown'

app = Flask(__name__)
CORS(app)
app.secret_key = os.urandom(24) # Needed for session management

STATIC_PET_IMAGE_FOLDER = 'static/img/pets'
if not os.path.exists(STATIC_PET_IMAGE_FOLDER):
    os.makedirs(STATIC_PET_IMAGE_FOLDER, exist_ok=True) # exist_ok=True to avoid error if running multiple times


@app.route('/')
def index():
    # Initialize session variables if not present
    if 'pet_mood' not in session:
        session['pet_mood'] = 'neutral'
    if 'chosen_pet_type' not in session: # Add pet type to session
        session['chosen_pet_type'] = 'dog' # Default pet type
    if 'purchase_history' not in session:
        session['purchase_history'] = []
    if 'wardrobe_items' not in session:
        session['wardrobe_items'] = []
    return render_template('index.html', current_pet_type=session['chosen_pet_type'])

@app.route('/wardrobe', methods=['GET', 'POST'])
def wardrobe():
    if 'wardrobe_items' not in session:
        session['wardrobe_items'] = []

    if request.method == 'POST':
        item_name = request.form.get('item_name')
        item_type = request.form.get('item_type')
        color = request.form.get('color')
        brand = request.form.get('brand')
        purchase_date = request.form.get('purchase_date')

        if item_name and item_type: # Basic validation
            session['wardrobe_items'].append({
                'id': len(session['wardrobe_items']) + 1, # Simple ID for deletion
                'item_name': item_name,
                'item_type': item_type,
                'color': color,
                'brand': brand,
                'purchase_date': purchase_date
            })
            session.modified = True
            return redirect(url_for('wardrobe'))
        else:
            # Add error handling/flash message for missing fields
            pass 

    return render_template('wardrobe.html', wardrobe_items=session['wardrobe_items'])

@app.route('/new-purchase', methods=['GET', 'POST'])
def new_purchase():
    if request.method == 'POST':
        potential_item_name = request.form.get('potential_item_name')
        q1_similar = request.form.get('q1_similar') == 'yes'
        q2_wear_often = request.form.get('q2_wear_often') == 'yes'
        q3_trending = request.form.get('q3_trending') == 'yes'
        q4_versatile = request.form.get('q4_versatile') == 'yes' # New question
        q5_fills_gap = request.form.get('q5_fills_gap') == 'yes'   # New question

        # Basic validation
        if (not potential_item_name or 
            request.form.get('q1_similar') is None or 
            request.form.get('q2_wear_often') is None or 
            request.form.get('q3_trending') is None or
            request.form.get('q4_versatile') is None or # New question validation
            request.form.get('q5_fills_gap') is None):   # New question validation
            # Ideally, add flash messaging for errors
            return render_template('new_purchase.html', error="Please answer all questions.")

        score = 0
        if q1_similar: # This question is reverse scored in spirit, but prompt says Yes = +1
            score += 1 # If they own similar, it's less mindful, but following prompt for now
        if q2_wear_often:
            score += 1
        if not q3_trending: # Buying NOT because it's trending is mindful
            score +=1
        
        # Corrected Logic: Score each "Yes" as +1 for the questions as phrased
        # Q1: Do you have a similar item? (Yes = less mindful)
        # Q2: Will you wear this at least 10 times? (Yes = mindful)
        # Q3: Are you buying this just because it’s trending? (Yes = less mindful)
        # To match "Mindful >= 2", we need to adjust scoring or question interpretation.
        # Let's re-interpret the scoring based on the spirit of mindful purchases:
        # - Not having a similar item is good (+1)
        # - Wearing it often is good (+1)
        # - Not buying *just* because it's trending is good (+1)
        
        mindful_score = 0
        if not q1_similar: # Don't have similar item
            mindful_score += 1
        if q2_wear_often: # Will wear often
            mindful_score += 1
        if not q3_trending: # Not buying due to trend
            mindful_score += 1
        if q4_versatile: # Item is versatile
            mindful_score += 1
        if q5_fills_gap: # Item fills a genuine gap
            mindful_score += 1

        # Adjust mindful threshold based on the new number of questions (now 5 questions)
        # Let's say 3 out of 5 positive answers make it mindful.
        classification = 'Mindful' if mindful_score >= 3 else 'Impulsive'

        if 'purchase_history' not in session:
            session['purchase_history'] = []
        
        session['purchase_history'].append({
            'item_name': potential_item_name,
            'is_similar_owned': q1_similar,
            'will_wear_often': q2_wear_often,
            'buying_due_to_trend': q3_trending,
            'is_versatile': q4_versatile, # New question data
            'fills_gap': q5_fills_gap,     # New question data
            'classification': classification,
            'timestamp': datetime.datetime.now().isoformat()
        })

        if classification == 'Mindful':
            session['pet_mood'] = 'happy'
        else:
            session['pet_mood'] = 'sad'
        
        session.modified = True # Ensure session is saved
        return redirect(url_for('pet'))

    return render_template('new_purchase.html')

@app.route('/set_pet/<string:pet_type_choice>')
def set_pet(pet_type_choice):
    if pet_type_choice in ['dog', 'cat', 'hamster']:
        session['chosen_pet_type'] = pet_type_choice
        session.modified = True
    return redirect(url_for('index')) # Redirect to home or pet page

@app.route('/pet')
def pet():
    pet_mood = session.get('pet_mood', 'neutral') # Default to neutral
    chosen_pet_type = session.get('chosen_pet_type', 'dog') # Default to dog if not set
    mood_messages = {
        'happy': "I'm proud of your mindful choice!",
        'sad': "Oops, let's do better next time.",
        'neutral': "How are you feeling today? Let's make some good choices!"
    }
    message = mood_messages.get(pet_mood, mood_messages['neutral'])
    
    # Updated pet image logic for different pet types
    pet_image_url = f"/static/img/pets/{chosen_pet_type}_{pet_mood}.png"
    # Example: /static/img/pets/dog_happy.png, /static/img/pets/cat_sad.png

    return render_template('pet.html', pet_mood=pet_mood, message=message, pet_image_url=pet_image_url, chosen_pet_type=chosen_pet_type)

@app.route('/wardrobe/delete/<int:item_id>', methods=['POST'])
def delete_wardrobe_item(item_id):
    if 'wardrobe_items' in session:
        session['wardrobe_items'] = [item for item in session['wardrobe_items'] if item.get('id') != item_id]
        session.modified = True
    return redirect(url_for('wardrobe'))

@app.route('/trends')
def trends():
    data_files_dir = '/Users/abdulrehmanfaisal/Desktop/projects /experiments/'  # Base directory for data files
    csv_files = glob.glob(os.path.join(data_files_dir, '*.csv'))
    xls_files = glob.glob(os.path.join(data_files_dir, '*.xls'))
    xlsx_files = glob.glob(os.path.join(data_files_dir, '*.xlsx')) # Added to include .xlsx files
    all_data_files = csv_files + xls_files + xlsx_files

    trends_data_for_tables = [] # For displaying raw data snippets
    max_rows_to_display = 5

    # Data structures for new line charts
    # 1. Current Shopping Trends (people_buying_chart_data)
    #    Structure: {item_category: {season: count}}
    shopping_trends_data = Counter() # (season, item_category) -> count

    # 2. Brand Popularity Analysis (brand_trends_chart_data) - Existing logic is mostly fine
    brand_yearly_data = {}  # {(brand, year): metric_sum} - Existing

    # 3. Seasonal Color Trends (seasonal_color_chart_data)
    #    Structure: {color: {season: count}}
    seasonal_color_data = Counter() # (season, color) -> count

    # 4. Fashion Cycle Analysis (trend_lifecycle_chart_data)
    #    Structure: {style_attribute: {season: count}}
    fashion_cycle_data = Counter() # (season, style_attribute) -> count

    # 5. Geographic Style Distribution (regional_trends_chart_data)
    #    Structure: {country: {style_attribute: count}}
    #    For line chart: X-axis styles, lines per country
    geographic_style_data = Counter() # (country, style_attribute) -> count

    # 6. Style Preference Analysis (style_preference_chart_data)
    #    Structure: {age_group: {style_attribute: count}}
    #    For line chart: X-axis styles, lines per age_group
    style_preference_data = Counter() # (age_group, style_attribute) -> count

    # 7. Optimal Purchase Periods (purchase_timing_chart_data)
    #    Structure: {purchase_time_period: {season: count_of_purchases}}
    #    X-axis seasons, lines per purchase_time_period
    purchase_timing_data = Counter() # (season, purchase_time_period) -> count

    # Define file groups for each chart type to target processing
    # These are illustrative; actual column presence will determine usability
    files_for_shopping_trends = [
        'fashion_data_2018_2022.xls',
        'mock_fashion_data_uk_us.csv',
        'Fashion_Dataset_Global.csv',
        'Fashion_Retail_Sales.csv' # Contains 'Product Category' and 'Date'
    ]
    files_for_brand_trends = [
        'Dataset Global Fashion Brands Brand Equity Ranking Growth Rate COO ROO 2001-2021.xlsx',
        'Fashion_Retail_Sales.csv',
        'Global Fashion Dataset_Update.csv'
    ] # Existing
    files_for_seasonal_colors = [
        'mock_fashion_data_uk_us.csv', # Has 'Color', 'Season'
        'Fashion_Dataset_Global.csv' # Assuming it might have color/season
    ]
    files_for_fashion_cycle = [
        'mock_fashion_data_uk_us.csv' # Has 'Style Attributes', 'Season'
    ]
    files_for_geographic_styles = [
        'mock_fashion_data_uk_us.csv', # Can infer UK/US, has 'Style Attributes'
        'Fashion_Dataset_Global.csv', # Assuming 'Country', 'Category'/'Style'
        'Buyers-repartition-by-country.csv' # Has 'Country'
    ]
    files_for_style_preferences = [
        'mock_fashion_data_uk_us.csv' # Has 'Age', 'Style Attributes'
    ]
    files_for_purchase_timing = [
        'mock_fashion_data_uk_us.csv', # Has 'Season', 'Time Period Highest Purchase'
        'Fashion_Retail_Sales.csv' # Has 'Date'
    ]

    files_for_people_buying = [
        'fashion_data_2018_2022.xls',
        'mock_fashion_data_uk_us.csv',
        'Fashion_Dataset_Global.csv'
    ]
    
    files_for_brand_trends = [
        'Dataset Global Fashion Brands Brand Equity Ranking Growth Rate COO ROO 2001-2021.xlsx',
        'Fashion_Retail_Sales.csv',
        'Global Fashion Dataset_Update.csv'
    ]

    for file_path in all_data_files:
        df = None
        file_name = os.path.basename(file_path)
        try:
            if file_path.endswith('.csv'):
                df = pd.read_csv(file_path, low_memory=False)
            elif file_path.endswith('.xls') or file_path.endswith('.xlsx'):
                df = pd.read_excel(file_path)
            else:
                continue

            # For table display (original functionality - kept for context if needed)
            df_display = df.iloc[:max_rows_to_display, :df.shape[1]]
            table_html = df_display.to_html(classes='table table-striped table-bordered', index=False, border=0)
            trends_data_for_tables.append({
                'file_name': file_name,
                'table_html': table_html,
                'columns': list(df_display.columns),
                'total_rows': len(df),
                'displayed_rows': len(df_display),
                'max_rows_limit': max_rows_to_display
            })

            df.columns = [str(col).lower().strip() for col in df.columns]

            # --- Data processing for each chart type ---

            # 1. Current Shopping Trends (by item category and season)
            if file_name in files_for_shopping_trends:
                cat_col, season_col_from_data, date_col = None, None, None
                potential_cat_cols = ['category', 'product category', 'item_type', 'type']
                potential_season_cols = ['season']
                potential_date_cols = ['date', 'purchase date', 'order date']

                for col in potential_cat_cols: 
                    if col in df.columns: cat_col = col; break
                for col in potential_season_cols:
                    if col in df.columns: season_col_from_data = col; break
                for col in potential_date_cols:
                    if col in df.columns: date_col = col; break
                
                if cat_col:
                    for _, row in df.iterrows():
                        category = str(row[cat_col]).strip() if pd.notna(row[cat_col]) else 'Unknown'
                        season = 'Unknown'
                        if season_col_from_data and pd.notna(row[season_col_from_data]):
                            season = normalize_season(row[season_col_from_data])
                        elif date_col and pd.notna(row[date_col]):
                            season = date_to_season(row[date_col])
                        
                        if category != 'Unknown' and season != 'Unknown':
                            shopping_trends_data[(season, category)] += 1

            # 2. Brand Popularity Analysis (by brand and year) - Existing logic adapted
            if file_name in files_for_brand_trends:
                brand_col, year_data_col, metric_col = None, None, None
                potential_brand_cols = ['brand name', 'brand']
                potential_year_data_cols = ['year', 'date', 'period'] # Column that contains year or date info
                potential_metric_cols = ['sales', 'sales amount', 'growth rate', 'rank', 'equity', 'value', 'revenue', 'brand equity score']

                for col in potential_brand_cols: 
                    if col in df.columns: brand_col = col; break
                for col in potential_year_data_cols:
                    if col in df.columns: year_data_col = col; break
                for col in potential_metric_cols:
                    if col in df.columns: metric_col = col; break
                
                if brand_col and year_data_col and metric_col:
                    temp_df = df[[brand_col, year_data_col, metric_col]].copy()
                    temp_df.dropna(subset=[brand_col, year_data_col, metric_col], inplace=True)
                    temp_df['year_extracted'] = temp_df[year_data_col].apply(extract_year)
                    temp_df.dropna(subset=['year_extracted'], inplace=True)
                    temp_df['year_extracted'] = temp_df['year_extracted'].astype(int)
                    temp_df[metric_col] = pd.to_numeric(temp_df[metric_col], errors='coerce')
                    temp_df.dropna(subset=[metric_col], inplace=True)

                    for _, row in temp_df.iterrows():
                        brand = str(row[brand_col]).strip()
                        year = int(row['year_extracted'])
                        metric = row[metric_col]
                        key = (brand, year)
                        brand_yearly_data[key] = brand_yearly_data.get(key, 0) + metric
            
            # 3. Seasonal Color Trends (by color and season)
            if file_name in files_for_seasonal_colors:
                color_col, season_col_from_data, date_col = None, None, None
                potential_color_cols = ['color', 'colour']
                potential_season_cols = ['season']
                potential_date_cols = ['date', 'purchase date']

                for col in potential_color_cols: 
                    if col in df.columns: color_col = col; break
                for col in potential_season_cols:
                    if col in df.columns: season_col_from_data = col; break
                for col in potential_date_cols:
                    if col in df.columns: date_col = col; break

                if color_col:
                    for _, row in df.iterrows():
                        color = str(row[color_col]).strip() if pd.notna(row[color_col]) else 'Unknown'
                        season = 'Unknown'
                        if season_col_from_data and pd.notna(row[season_col_from_data]):
                            season = normalize_season(row[season_col_from_data])
                        elif date_col and pd.notna(row[date_col]):
                            season = date_to_season(row[date_col])
                        
                        if color != 'Unknown' and season != 'Unknown':
                           seasonal_color_data[(season, color)] += 1

            # 4. Fashion Cycle Analysis (by style attribute and season)
            if file_name in files_for_fashion_cycle:
                style_col, season_col_from_data, date_col = None, None, None
                potential_style_cols = ['style attributes', 'style', 'trend type']
                potential_season_cols = ['season']
                potential_date_cols = ['date']

                for col in potential_style_cols: 
                    if col in df.columns: style_col = col; break
                for col in potential_season_cols:
                    if col in df.columns: season_col_from_data = col; break
                for col in potential_date_cols:
                    if col in df.columns: date_col = col; break
                
                if style_col:
                    for _, row in df.iterrows():
                        style = str(row[style_col]).strip() if pd.notna(row[style_col]) else 'Unknown'
                        season = 'Unknown'
                        if season_col_from_data and pd.notna(row[season_col_from_data]):
                            season = normalize_season(row[season_col_from_data])
                        elif date_col and pd.notna(row[date_col]):
                            season = date_to_season(row[date_col])
                        
                        if style != 'Unknown' and season != 'Unknown':
                            fashion_cycle_data[(season, style)] += 1

            # 5. Geographic Style Distribution (by country and style attribute)
            if file_name in files_for_geographic_styles:
                country_col, style_col = None, None
                potential_country_cols = ['country', 'location', 'region']
                potential_style_cols = ['style attributes', 'style', 'category'] # Category might be a proxy

                for col in potential_country_cols: 
                    if col in df.columns: country_col = col; break
                for col in potential_style_cols:
                    if col in df.columns: style_col = col; break
                
                # Special handling for mock_fashion_data_uk_us.csv if no explicit country column
                is_mock_uk_us = 'mock_fashion_data_uk_us.csv' in file_name
                if not country_col and is_mock_uk_us:
                    # Infer country from filename or assume a default if not specified
                    # This is a simplification; real-world might need more robust logic or data cleaning
                    df['inferred_country'] = 'UK/US' # Example, could be split if data allows
                    country_col = 'inferred_country'

                if country_col and style_col:
                    for _, row in df.iterrows():
                        country = str(row[country_col]).strip() if pd.notna(row[country_col]) else 'Unknown'
                        style = str(row[style_col]).strip() if pd.notna(row[style_col]) else 'Unknown'
                        if country != 'Unknown' and style != 'Unknown':
                            geographic_style_data[(country, style)] += 1
            
            # 6. Style Preference Analysis (by age group and style attribute)
            if file_name in files_for_style_preferences:
                age_col, style_col = None, None
                potential_age_cols = ['age', 'age group']
                potential_style_cols = ['style attributes', 'style', 'preferred style']

                for col in potential_age_cols: 
                    if col in df.columns: age_col = col; break
                for col in potential_style_cols:
                    if col in df.columns: style_col = col; break
                
                if age_col and style_col:
                    for _, row in df.iterrows():
                        age_group = get_age_group(row[age_col])
                        style = str(row[style_col]).strip() if pd.notna(row[style_col]) else 'Unknown'
                        if age_group != 'Unknown' and style != 'Unknown':
                            style_preference_data[(age_group, style)] += 1

            # 7. Optimal Purchase Periods (by purchase time period and season)
            if file_name in files_for_purchase_timing:
                time_period_col, season_col_from_data, date_col = None, None, None
                potential_time_period_cols = ['time period highest purchase', 'purchase time', 'best time to buy']
                potential_season_cols = ['season']
                potential_date_cols = ['date', 'purchase date']

                for col in potential_time_period_cols:
                    if col in df.columns: time_period_col = col; break
                for col in potential_season_cols:
                    if col in df.columns: season_col_from_data = col; break
                for col in potential_date_cols:
                    if col in df.columns: date_col = col; break
                
                if time_period_col:
                    for _, row in df.iterrows():
                        time_period = str(row[time_period_col]).strip() if pd.notna(row[time_period_col]) else 'Unknown'
                        season = 'Unknown'
                        if season_col_from_data and pd.notna(row[season_col_from_data]):
                            season = normalize_season(row[season_col_from_data])
                        elif date_col and pd.notna(row[date_col]):
                            season = date_to_season(row[date_col])
                        
                        if time_period != 'Unknown' and season != 'Unknown':
                            purchase_timing_data[(season, time_period)] += 1

        except Exception as e:
            trends_data_for_tables.append({'file_name': file_name, 'error': str(e)})
            print(f"Error processing {file_path} for chart data: {e}")

    # --- Prepare data for Chart.js --- 

    default_chart_js_config = {
        'type': 'line',
        'options': {
            'responsive': True,
            'maintainAspectRatio': False,
            'scales': {
                'y': {
                    'beginAtZero': True
                }
            }
        }
    }

    def format_for_line_chart(counter_data, x_axis_label, y_axis_label_prefix):
        """Transforms Counter data into Chart.js line chart format."""
        # counter_data is expected to be like {(x_val, line_label): count}
        # We want: {line_label: {x_val: count}}
        processed = {}
        all_x_values = set()
        all_line_labels = set()

        for (x_val, line_label), count in counter_data.items():
            all_x_values.add(x_val)
            all_line_labels.add(line_label)
            if line_label not in processed:
                processed[line_label] = {}
            processed[line_label][x_val] = processed[line_label].get(x_val, 0) + count
        
        sorted_x_values = sorted(list(all_x_values))
        # Limit the number of lines to avoid clutter, e.g., top 5-7 lines by total count
        line_totals = {line: sum(data.values()) for line, data in processed.items()}
        top_line_labels = sorted(line_totals, key=line_totals.get, reverse=True)[:7] # Show top 7 lines

        datasets = []
        for line_label in top_line_labels:
            if line_label in processed:
                data_points = [processed[line_label].get(x, 0) for x in sorted_x_values]
                datasets.append({
                    'label': str(line_label),
                    'data': data_points,
                    'fill': False,
                    'tension': 0.1
                })
        
        return {'labels': sorted_x_values, 'datasets': datasets}

    # 1. Current Shopping Trends (people_buying_chart)
    # shopping_trends_data: (season, item_category) -> count
    # X-axis: Seasons, Lines: Item Categories
    people_buying_chart_data = format_for_line_chart(shopping_trends_data, 'Season', 'Category')

    # 2. Brand Popularity Analysis (brand_trends_chart) - Existing logic adapted
    processed_brand_trends = {}
    for (brand, year), metric_sum in brand_yearly_data.items():
        if brand not in processed_brand_trends:
            processed_brand_trends[brand] = {}
        processed_brand_trends[brand][year] = processed_brand_trends[brand].get(year, 0) + metric_sum

    all_years_brand = sorted(list(set(year for data in processed_brand_trends.values() for year in data.keys())))
    brand_totals = {brand: sum(data.values()) for brand, data in processed_brand_trends.items()}
    top_brands_for_chart = sorted(brand_totals, key=brand_totals.get, reverse=True)[:5]

    brand_trends_chart_js_data = {'labels': all_years_brand, 'datasets': []}
    for brand_name in top_brands_for_chart:
        if brand_name in processed_brand_trends:
            brand_data_points = [processed_brand_trends[brand_name].get(year, 0) for year in all_years_brand]
            brand_trends_chart_js_data['datasets'].append({
                'label': brand_name,
                'data': brand_data_points,
                'fill': False,
                'tension': 0.1
            })

    # 3. Seasonal Color Trends (color_palettes_chart)
    # seasonal_color_data: (season, color) -> count
    # X-axis: Seasons, Lines: Colors
    color_palettes_chart_data = format_for_line_chart(seasonal_color_data, 'Season', 'Color')

    # 4. Fashion Cycle Analysis (trend_lifecycle_chart)
    # fashion_cycle_data: (season, style_attribute) -> count
    # X-axis: Seasons, Lines: Style Attributes
    trend_lifecycle_chart_data = format_for_line_chart(fashion_cycle_data, 'Season', 'Style')

    # 5. Geographic Style Distribution (regional_trends_chart)
    # geographic_style_data: (country, style_attribute) -> count
    # X-axis: Style Attributes, Lines: Countries
    # Need to swap for format_for_line_chart: (style_attribute, country) -> count
    swapped_geo_data = Counter({(style, country): count for (country, style), count in geographic_style_data.items()})
    regional_trends_chart_data = format_for_line_chart(swapped_geo_data, 'Style Attribute', 'Country')

    # 6. Style Preference Analysis (mood_fashion_chart -> renamed to style_preference_chart)
    # style_preference_data: (age_group, style_attribute) -> count
    # X-axis: Style Attributes, Lines: Age Groups
    # Need to swap for format_for_line_chart: (style_attribute, age_group) -> count
    swapped_style_pref_data = Counter({(style, age_group): count for (age_group, style), count in style_preference_data.items()})
    style_preference_chart_data = format_for_line_chart(swapped_style_pref_data, 'Style Attribute', 'Age Group')

    # 7. Optimal Purchase Periods (purchase_timing_chart)
    # purchase_timing_data: (season, purchase_time_period) -> count
    # X-axis: Seasons, Lines: Purchase Time Periods
    purchase_timing_chart_data = format_for_line_chart(purchase_timing_data, 'Season', 'Purchase Period')

    # Fetch Google Trends and Reddit data (existing functionality)
    google_trends_data = get_google_trends()
    reddit_trends_data = get_reddit_trends()

    return render_template('trends.html', 
                           trends_data=trends_data_for_tables, # For raw data tables
                           # Chart data for the 7 line graphs
                           people_buying_chart_data=people_buying_chart_data,
                           brand_trends_chart_data=brand_trends_chart_js_data, 
                           color_palettes_chart_data=color_palettes_chart_data,
                           trend_lifecycle_chart_data=trend_lifecycle_chart_data,
                           regional_trends_chart_data=regional_trends_chart_data,
                           style_preference_chart_data=style_preference_chart_data,
                           purchase_timing_chart_data=purchase_timing_chart_data,
                           # External trends data
                           google_trends_data=google_trends_data,
                           reddit_trends_data=reddit_trends_data,
                           default_chart_config=default_chart_js_config
                           )

@app.route('/timeless')
def timeless():
    # This page is mostly static with client-side filtering, 
    # but you could pass initial data if needed in the future.
    return render_template('timeless.html')
# Helper function for Google Trends (basic example)
def get_google_trends():
    try:
        pytrends = TrendReq(hl='en-US', tz=360)
        # Using related queries for a general fashion keyword for more stability
        kw_list = ['fashion'] # Can be expanded or made dynamic
        pytrends.build_payload(kw_list, cat=0, timeframe='today 1-m', geo='US', gprop='')
        
        # Fetch related queries
        related_queries_data = pytrends.related_queries()
        
        # The result is a dictionary where keys are your keywords
        # Each value is another dictionary with 'top' and 'rising' DataFrames
        # We'll use 'top' related queries for the primary keyword
        top_related_df = related_queries_data[kw_list[0]]['top']
        
        if top_related_df is not None and not top_related_df.empty:
            # Convert DataFrame to list of lists/tuples as expected by template
            # The template expects: query[0] for the query string
            related_queries_list = top_related_df[['query']].head(10).values.tolist()
            return {'related_queries': related_queries_list, 'error': None}
        else:
            # Try 'rising' if 'top' is empty, or handle as no data
            rising_related_df = related_queries_data[kw_list[0]]['rising']
            if rising_related_df is not None and not rising_related_df.empty:
                related_queries_list = rising_related_df[['query']].head(10).values.tolist()
                return {'related_queries': related_queries_list, 'error': None}
            else:
                return {'related_queries': [], 'error': 'No related Google Trends searches found for the keyword.'}
    except Exception as e:
        error_message = str(e)
        # Check for common pytrends errors that might result in 404-like behavior
        if "The request failed: Google returned a response with code 404" in error_message or \
           "ResponseCodeError: The request failed: Google returned a response with code 429" in error_message or \
           "TooManyRequestsError" in error_message:
            error_message = "Could not retrieve data from Google Trends at this time. This might be due to request limits or service availability."
        print(f"Error fetching Google Trends: {error_message}")
        return {'related_queries': [], 'error': error_message}

# Helper function for Reddit Trends (placeholder)
# IMPORTANT: PRAW setup is required for actual Reddit API calls.
# This function needs to be configured with your Reddit API credentials.
# Store your credentials securely, for example, as environment variables:
# REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT
def get_reddit_trends(subreddit_name='fashion', limit=5):
    reddit_client_id = os.getenv('REDDIT_CLIENT_ID')
    reddit_client_secret = os.getenv('REDDIT_CLIENT_SECRET')
    reddit_user_agent = os.getenv('REDDIT_USER_AGENT')

    if not all([reddit_client_id, reddit_client_secret, reddit_user_agent]):
        # print("Reddit API credentials not found in environment variables. Showing placeholder data.")
        return {
            'posts': [
                {'title': 'Placeholder: Discover the latest autumn styles!', 'score': 120, 'url': '#'},
                {'title': 'Placeholder: Your top thrift store finds this month?', 'score': 88, 'url': '#'}
            ],
            'error': 'PRAW not fully configured; showing placeholder data. API key needed. Please set REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, and REDDIT_USER_AGENT environment variables.'
        }

    try:
        reddit = praw.Reddit(client_id=reddit_client_id,
                             client_secret=reddit_client_secret,
                             user_agent=reddit_user_agent)
        # Check if connection is read-only (i.e., successful anonymous or authenticated connection)
        # print(f"Reddit instance read_only: {reddit.read_only}") 
        subreddit = reddit.subreddit(subreddit_name)
        top_posts = []
        for post in subreddit.hot(limit=limit):
            top_posts.append({'title': post.title, 'score': post.score, 'url': post.url})
        if not top_posts:
             return {'posts': [], 'error': f'No posts found in r/{subreddit_name} or subreddit is inaccessible.'}
        return {'posts': top_posts, 'error': None}
        
    except praw.exceptions.PrawcoreException as e:
        # Catch specific PRAW core exceptions which might indicate auth issues or other API problems
        print(f"PRAW core error fetching Reddit trends: {e}")
        return {'posts': [], 'error': f'Reddit API error: {str(e)}. Please check your credentials and API access.'}
    except Exception as e:
        # General exception for other issues
        print(f"General error fetching Reddit trends: {e}")
        return {'posts': [], 'error': str(e)}

@app.route('/dashboard')
def dashboard():
    wardrobe_items_count = len(session.get('wardrobe_items', []))
    
    purchase_history = session.get('purchase_history', [])
    mindful_decisions = sum(1 for decision in purchase_history if decision['classification'] == 'Mindful')
    impulsive_decisions = sum(1 for decision in purchase_history if decision['classification'] == 'Impulsive')
    
    # For pet mood history, we can show the sequence of classifications or a summary
    # For simplicity, we'll pass the counts and the current mood.
    current_pet_mood = session.get('pet_mood', 'neutral')

    return render_template('dashboard.html', 
                           wardrobe_items_count=wardrobe_items_count,
                           mindful_decisions=mindful_decisions,
                           impulsive_decisions=impulsive_decisions,
                           current_pet_mood=current_pet_mood,
                           purchase_history_count=len(purchase_history)
                           )

@app.errorhandler(404)
def not_found(error):
    return jsonify({'error': 'Not found', 'message': 'The requested endpoint does not exist'}), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)