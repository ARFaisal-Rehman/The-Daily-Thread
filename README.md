# The Daily Thread - Mindful Fashion Companion

## Overview
The Daily Thread is a web application designed to promote mindful fashion consumption. It helps users manage their wardrobe, make thoughtful purchase decisions, and visualize fashion trends through data analysis. The application features a virtual pet companion that responds to your shopping habits, encouraging sustainable fashion choices.

## Features

### 🧥 Wardrobe Management
- Add, view, and delete clothing items in your digital wardrobe
- Track details like item name, type, color, brand, and purchase date
- Organize your collection for better visibility of what you own

### 🛍️ Mindful Purchase Decision Helper
- Answer questions about potential purchases to determine if they're mindful or impulsive
- Assessment based on criteria like:
  - Whether you already own similar items
  - How often you'll wear the item
  - If you're buying just because it's trending
  - The item's versatility
  - Whether it fills a genuine gap in your wardrobe

### 🐶 Virtual Pet Companion
- Choose between different pet types (dog, cat, hamster)
- Pet's mood changes based on your purchase decisions
- Provides visual feedback on your shopping habits

### 📊 Fashion Trend Analysis
- Visualize fashion data from multiple sources
- Analyze trends across seasons, brands, colors, and styles
- View shopping patterns and brand popularity over time
- Geographic style distribution and age-based preferences

## Installation

### Prerequisites
- Python 3.7+
- pip package manager

### Setup
1. Clone the repository
2. Install the required dependencies:
   ```
   pip install -r requirements.txt
   ```

### Dependencies
The application relies on the following main packages:
- Flask - Web framework
- Pandas - Data analysis and manipulation
- PyTrends - Google Trends API interface
- PRAW - Reddit API wrapper
- Flask-CORS - Cross-Origin Resource Sharing for Flask
- Pillow - Image processing
- TensorFlow - Machine learning (for potential future features)

## Usage

1. Start the application:
   ```
   python app.py
   ```
2. Open your web browser and navigate to `http://localhost:5000`
3. Navigate through the different sections:
   - Home: Overview and pet selection
   - My Wardrobe: Manage your clothing items
   - New Purchase: Evaluate potential purchases
   - Virtual Pet: Check your pet's mood based on your decisions
   - Fashion Trends: Explore data visualizations of fashion trends
   - Timeless Fashion: View classic fashion pieces that never go out of style
   - Dashboard: Get an overview of your wardrobe and purchase history

## Project Structure

- `app.py` - Main application file with Flask routes and data processing functions
- `templates/` - HTML templates for the web interface
  - `index.html` - Home page
  - `wardrobe.html` - Wardrobe management interface
  - `new_purchase.html` - Purchase decision helper
  - `pet.html` - Virtual pet companion interface
  - `trends.html` - Fashion trend analysis visualizations
  - `timeless.html` - Timeless fashion pieces
  - `dashboard.html` - User dashboard with statistics
- `static/` - Static files (CSS, images)
  - `css/newspaper.css` - Styling for the application
  - `img/pets/` - Pet images for different moods and types
- `*.csv`, `*.xls`, `*.xlsx` - Fashion datasets for trend analysis

## Data Analysis

The application processes various fashion datasets to provide insights on:
- Current shopping trends by season and category
- Brand popularity analysis over time
- Seasonal color trends
- Fashion cycle analysis
- Geographic style distribution
- Age-based style preferences
- Optimal purchase periods

## Contributing

Contributions to improve The Daily Thread are welcome. Please feel free to submit pull requests or open issues to suggest improvements or report bugs.

## License

This project is available for personal and educational use.
