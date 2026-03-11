# Smart Food Discovery Agent

AI-powered restaurant and food recommendations. Click any city on an interactive 3D Earth globe and get personalized recommendations.

## Setup

### 1. Get API Keys (all free)

- **Groq**: [console.groq.com](https://console.groq.com) — for the AI agent
- **Ticketmaster**: [developer.ticketmaster.com](https://developer.ticketmaster.com) — for food events
- **RapidAPI**: [rapidapi.com](https://rapidapi.com) — subscribe to Tasty API (free tier)

### 2. Backend

```bash
cd backend
cp .env.example .env
# Edit .env and add your keys
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend
npm install
npm run dev
```

### 4. Use

Open [http://localhost:3000](http://localhost:3000), click any city on the globe, and explore food recommendations.

## APIs Used

- **Overpass (OpenStreetMap)** — restaurants, cafes, bars (no key)
- **Wikipedia REST API** — city food culture (no key)
- **Ticketmaster** — food festivals and events
- **Tasty (RapidAPI)** — trending dishes and recipes
