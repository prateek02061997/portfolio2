# Prateek Parihar - AI-Powered Data Analyst Portfolio

Modern recruiter-focused portfolio with a premium SaaS-style UI, featured project storytelling, and a secure Gemini-powered assistant.

## What Was Upgraded

- Complete UI/UX redesign of the main portfolio experience
- New single-page flow: Home, About, Skills, Projects, Certifications, Contact
- Experience page removed from website navigation and routing
- ChatGPT-style "Prateek AI Assistant" widget (desktop and mobile responsive)
- Secure backend API integration for Gemini (no API key exposed in frontend)
- Portfolio knowledge base added in `portfolio_data.json`

## Tech Stack

- Frontend: HTML, CSS, JavaScript
- Backend: Node.js + Express
- AI: Google Gemini API

## Project Structure

- `index.html` - redesigned primary portfolio page
- `styles.css` - complete modern design system and responsive UI
- `script.js` - interactions, animations, chatbot behavior
- `server.js` - secure API endpoint for Gemini chat
- `portfolio_data.json` - portfolio-specific assistant knowledge base
- `.env.example` - environment variable template

## Setup

1. Install dependencies:

```bash
npm install
```

2. Create a `.env` file from `.env.example` and add your Gemini key:

```env
GEMINI_API_KEY=your_real_key_here
PORT=3000
```

3. Start the server:

```bash
npm start
```

4. Open:

`http://localhost:3000`

## Security Notes

- API key is server-side only in `.env`
- Frontend calls `/api/chat`
- Assistant is instructed to answer only from `portfolio_data.json`

## Contact

- Email: pprateek26@gmail.com
- LinkedIn: https://linkedin.com/in/pprateek26
- GitHub: https://github.com/prateek02061997
