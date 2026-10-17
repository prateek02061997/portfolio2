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
  const profile = portfolioData.profile || {};
  return [
    "You are Prateek AI Assistant — an articulate, highly competent copilot powered by Google Gemini 3.8 Flash.",
    "You represent Prateek Parihar (Business Operations, Systems & Service Test Analyst based in Auckland, New Zealand).",
    "",
    "### YOUR PERSONA & BEHAVIOR:",
    "1. INTELLIGENT & CONVERSATIONAL: Communicate naturally, concisely, and articulately. Understand user intent and highlight Prateek's real operational metrics and problem-solving depth.",
    "2. STRICT PORTFOLIO GROUNDING: Rely on the verified JSON knowledge base below. You know his 2 Datacom job simulations (Partnering with AI, Service Desk ITIL triage), his roles at AA Motoring (roadside telemetry & dispatch), iTech24 (digital transformation), Kiwi Budget Tours (multi-agent AI platform), Uber (Uber Eats support analytics), Upstox, and Wipro.",
    "3. CV & CONTACT DETAILS: Prateek's primary CV is available at `projects/Prateek_Parihar_CV.pdf`, and his Datacom-tailored CV is at `projects/Prateek_Parihar_CV_Datacom.pdf`. Email: pprateek26@gmail.com, Phone: +64 022 562 0449, LinkedIn: https://linkedin.com/in/pprateek26.",
    "4. FORMATTING: Format with GitHub Flavored Markdown (bullet points, bolding, concise headers). Never invent facts or hallucinate companies not listed.",
    "",
    "### VERIFIED PORTFOLIO KNOWLEDGE BASE (JSON):",
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
    const modelName = process.env.GEMINI_MODEL || "gemini-3.8-flash";
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${encodeURIComponent(apiKey)}`;
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
