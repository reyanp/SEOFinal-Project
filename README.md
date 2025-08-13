# Let's Meet -- Find the Perfect Middle Ground

A tool that helps two people find the best meeting spot! Enter two addresses, choose a category, and discover nearby options!

## Features

- **Smart Midpoint Calculation** - Automatically find the geographic center between two addresses
- **Place Discovery** - Sort by restaurants, cafes, parks, and more near the midpoint
- **Interactive Map** - Visual results with markers and directions
- **Travel Times** - Shows driving time from both locations to each place
- **Quick Directions** - One-click navigation links


### Prerequisites
- Python 3.10 or higher
- Google Cloud account with billing enabled
- Google Maps API key

### Setup

1. **Clone the repo to your local machine**
   ```bash
   git clone https://github.com/reyanp/SEOFinal.git
   ```

2. **Create virtual environment and install dependencies:**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Get your Google Maps API key:**
   - Go to [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing one
   - Enable these APIs: Geocoding, Places, Maps JavaScript, Distance Matrix
   - Create API key in "APIs & Services" → "Credentials"

4. **Configure API key:**
   - Add to `backend/.env` --> `Maps_API_KEY=your_key_here`
   - Add to `frontend/index.html` --> "YOUR_API_KEY"

5. **Run the app:**
   ```bash
   # Terminal 1: Start backend
   venv\Scripts\python backend/app.py
   
   # Terminal 2: Start frontend
   cd frontend
   python -m http.server 5500
   ```

6. **Open in browser:** `http://localhost:5500`


## How to Use

1. **Enter addresses** - Your location and your friend's location
2. **Choose place type** - Restaurant, coffee shop, park, etc.
3. **Explore results** - View on map or in the list below

**Happy meeting!** 🎉


