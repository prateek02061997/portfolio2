const fs = require("fs");
const path = require("path");

const portfolioDataPath = path.join(process.cwd(), "portfolio_data.json");

function getPortfolioData() {
  try {
    const raw = fs.readFileSync(portfolioDataPath, "utf-8");
    return JSON.parse(raw);
  } catch (err) {
    console.error("Failed to read portfolio_data.json:", err);
    return {};
  }
}

function buildSystemInstruction(portfolioData) {
  return [
    "You are Prateek AI Assistant — a powerful, intelligent AI model powered by Google Gemini 2.0 Flash.",
    "You represent Prateek Parihar (Data Analyst | AI Automation Specialist | Business Intelligence Analyst in Auckland, New Zealand).",
    "",
    "### YOUR AI PERSONA & BEHAVIOR:",
    "1. FULL LLM INTELLIGENCE & REASONING: Act as an intelligent, conversational, highly fluent Google Gemini model. Use your full reasoning capacity to understand user intent, correct user typos automatically, and provide natural, articulate answers.",
    "2. PORTFOLIO EXPERT GROUNDING: You know all details of Prateek's portfolio data provided below (his projects, Master's thesis on EV & fuel prices, career history at AA NZ, Teleperformance, Upstox, Wipro, Power BI/SQL/Python skills, certifications, and contact details).",
    "3. FLEXIBLE CONVERSATIONAL SCOPE: Do not act like a rigid robot wall. If the user asks a general analytics, BI, AI, career, or spelling/grammar question, answer it intelligently like Google Gemini, and naturally connect your answer back to Prateek's skills and portfolio!",
    "4. FORMATTING & MARKDOWN: Always format your responses using clean GitHub Flavored Markdown (**bolding**, bullet points `- `, clear headings `### `, and clickable relative links for projects like `[AI CV Assistant](projects/ai-cv-assistant/index.html)` or `[Master's Thesis](projects/ev-fuel-price-thesis/index.html)`).",
    "5. RECRUITER & CLIENT FRIENDLY: Maintain a professional, articulate, executive-ready tone that highlights Prateek's technical depth, business impact, and strategic value.",
    "",
    "### PRATEEK'S PORTFOLIO KNOWLEDGE BASE:",
    JSON.stringify(portfolioData, null, 2),
  ].join("\n");
}

function formatHistoryForGemini(history) {
  if (!Array.isArray(history)) return [];

  return history
    .filter((item) => item && typeof item.text === "string" && (item.role === "user" || item.role === "ai" || item.role === "model"))
    .map((item) => ({
      role: item.role === "user" ? "user" : "model",
      parts: [{ text: item.text }],
    }));
}

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  try {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return res.status(500).json({ error: "Server missing GEMINI_API_KEY environment variable." });
    }

    const { message, history } = req.body || {};
    if (typeof message !== "string" || message.trim().length === 0) {
      return res.status(400).json({ error: "A valid message is required." });
    }

    const portfolioData = getPortfolioData();
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${encodeURIComponent(apiKey)}`;
    const formattedHistory = formatHistoryForGemini(history || []);

    const payload = {
      system_instruction: {
        parts: [{ text: buildSystemInstruction(portfolioData) }],
      },
      contents: [
        ...formattedHistory.slice(-12),
        {
          role: "user",
          parts: [{ text: message.trim() }],
        },
      ],
      generationConfig: {
        temperature: 0.3,
        topK: 20,
        topP: 0.8,
        maxOutputTokens: 800,
      },
    };

    const response = await fetch(endpoint, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const errorText = await response.text();
      return res.status(response.status).json({ error: `Gemini API error: ${errorText}` });
    }

    const data = await response.json();
    const parts = data?.candidates?.[0]?.content?.parts || [];
    const text = parts.map((part) => part.text).join("\n").trim();

    if (!text) {
      return res.status(500).json({ error: "Gemini response did not include text output." });
    }

    return res.status(200).json({ reply: text });
  } catch (error) {
    console.error("Vercel serverless chat function error:", error);
    return res.status(500).json({ error: "Internal server error", details: error.message });
  }
};
