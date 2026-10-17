import os
import json
import math
from typing import List, Dict, Any

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
PORT = int(os.getenv("PORT", 3000))

# Manually load .env if not populated
if not GEMINI_API_KEY:
    env_file = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_file):
        with open(env_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("GEMINI_API_KEY="):
                    GEMINI_API_KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
                elif line.startswith("PORT="):
                    try:
                        PORT = int(line.split("=", 1)[1].strip())
                    except Exception:
                        pass
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "gemini-embedding-001")

class DocumentChunk:
    def __init__(self, doc_id: str, title: str, category: str, content: str, metadata: Dict[str, Any] = None):
        self.doc_id = doc_id
        self.title = title
        self.category = category
        self.content = content
        self.metadata = metadata or {}
        self.embedding: List[float] = []

class LocalVectorIndex:
    """
    Lightweight, high-performance in-memory Vector Index conforming to LlamaIndex Node & VectorStore semantics.
    Supports cosine similarity retrieval, top-k scoring, and metadata filtering.
    """
    def __init__(self):
        self.nodes: List[DocumentChunk] = []

    def add_node(self, node: DocumentChunk):
        self.nodes.append(node)

    def search(self, query_embedding: List[float], top_k: int = 4) -> List[Dict[str, Any]]:
        if not query_embedding:
            return []
        
        results = []
        for node in self.nodes:
            if not node.embedding:
                continue
            sim = self._cosine_similarity(query_embedding, node.embedding)
            results.append({"node": node, "score": sim})
        
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def keyword_search(self, query: str, top_k: int = 4) -> List[Dict[str, Any]]:
        tokens = set(query.lower().split())
        scored = []
        for node in self.nodes:
            text = (node.title + " " + node.content).lower()
            score = sum(1 for t in tokens if t in text and len(t) > 2)
            if score > 0:
                scored.append({"node": node, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    @staticmethod
    def _cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a * a for a in vec_a))
        norm_b = math.sqrt(sum(b * b for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

class GeminiClient:
    """
    Direct client for Google Gemini 3.8 Flash and Embedding API.
    """
    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_embedding(self, text: str) -> List[float]:
        if not self.api_key:
            return []
        import urllib.request
        import urllib.parse
        
        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:embedContent?key={urllib.parse.quote(self.api_key)}"
        payload = {
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text[:2000]}]}
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return data.get("embedding", {}).get("values", [])
        except Exception as e:
            # Fallback gracefully
            return []

    def generate_chat_response(self, system_instruction: str, contents: List[Dict[str, Any]]) -> str:
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured.")
        import urllib.request
        import urllib.parse

        endpoint = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={urllib.parse.quote(self.api_key)}"
        payload = {
            "system_instruction": {"parts": [{"text": system_instruction}]},
            "contents": contents,
            "generationConfig": {
                "temperature": 0.25,
                "topK": 20,
                "topP": 0.85,
                "maxOutputTokens": 900
            }
        }
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
            return "\n".join(p.get("text", "") for p in parts).strip()

class PortfolioRAGService:
    """
    RAG & Model Context Protocol (MCP) engine for Prateek Parihar's Portfolio.
    """
    def __init__(self, data_file: str = "portfolio_data.json"):
        self.client = GeminiClient(GEMINI_API_KEY)
        self.index = LocalVectorIndex()
        self.portfolio_data = {}
        self.load_and_index(data_file)

    def load_and_index(self, data_file: str):
        if os.path.exists(data_file):
            with open(data_file, "r", encoding="utf-8") as f:
                self.portfolio_data = json.load(f)

        profile = self.portfolio_data.get("profile", {})
        
        # 1. Profile Node
        self.index.add_node(DocumentChunk(
            doc_id="profile",
            title=f"About {profile.get('name')}",
            category="Profile",
            content=f"Name: {profile.get('name')}\nHeadline: {profile.get('headline')} - {profile.get('subheadline')}\nLocation: {profile.get('location')}\nPhone: {profile.get('phone')}\nEmail: {profile.get('email')}\nSummary: {profile.get('summary')}"
        ))

        # 2. Experience Nodes
        for idx, exp in enumerate(self.portfolio_data.get("professional_experience", [])):
            bullets = "\n- ".join(exp.get("bullets", []))
            self.index.add_node(DocumentChunk(
                doc_id=f"exp_{idx}",
                title=f"{exp.get('role')} at {exp.get('company')}",
                category="Experience",
                content=f"Company: {exp.get('company')}\nRole: {exp.get('role')}\nPeriod: {exp.get('period')}\nLocation: {exp.get('location')}\nFocus: {exp.get('type')}\nKey Deliverables:\n- {bullets}"
            ))

        # 3. Project Nodes
        for p in self.portfolio_data.get("projects", []):
            tech_str = ", ".join(p.get("tech", []))
            self.index.add_node(DocumentChunk(
                doc_id=f"project_{p.get('id')}",
                title=p.get("name"),
                category="Project Case Study",
                content=f"Project: {p.get('name')} ({p.get('status')})\nCategory: {p.get('category')}\nTagline: {p.get('tagline')}\nProblem: {p.get('problem')}\nSolution: {p.get('solution')}\nTechnologies: {tech_str}\nBusiness Impact: {p.get('impact')}\nCase Study Link: {p.get('link')}"
            ))

        # 4. Workshops Node
        workshop_lines = []
        for w in self.portfolio_data.get("workshops", []):
            workshop_lines.append(f"- {w.get('title')} ({w.get('host')}): {w.get('focus')}")
        self.index.add_node(DocumentChunk(
            doc_id="workshops",
            title="AI & Technical Workshops Attended",
            category="Continuous Learning",
            content="Workshops Attended:\n" + "\n".join(workshop_lines)
        ))

        # 5. Skills & Certifications Node
        skills = self.portfolio_data.get("skills", {})
        certs = self.portfolio_data.get("certifications", [])
        self.index.add_node(DocumentChunk(
            doc_id="skills_and_certs",
            title="Technical Skills & Professional Certifications",
            category="Skills",
            content=f"AI & Automation Skills: {', '.join(skills.get('ai_automation', []))}\nData & Analytics Skills: {', '.join(skills.get('data_analytics', []))}\nBusiness Delivery Skills: {', '.join(skills.get('business_delivery', []))}\nSystems & Cloud: {', '.join(skills.get('systems_cloud', []))}\n\nOfficial Certifications:\n- " + "\n- ".join(certs)
        ))

        # 6. Education Node
        edu_lines = []
        for ed in self.portfolio_data.get("education", []):
            edu_lines.append(f"- {ed.get('degree')} at {ed.get('institution')} ({ed.get('period')}): {ed.get('highlights')}")
        self.index.add_node(DocumentChunk(
            doc_id="education",
            title="Academic Background & Thesis",
            category="Education",
            content="Education & Academic Research:\n" + "\n".join(edu_lines)
        ))

        # Compute embeddings if API key is active
        if self.client.api_key:
            for node in self.index.nodes:
                emb = self.client.get_embedding(f"{node.title}\n{node.content}")
                if emb:
                    node.embedding = emb

    def retrieve_context(self, query: str, top_k: int = 4) -> List[DocumentChunk]:
        """Hybrid Vector + Semantic Keyword RAG retrieval"""
        query_emb = self.client.get_embedding(query)
        if query_emb:
            matches = self.index.search(query_emb, top_k=top_k)
            if matches:
                return [m["node"] for m in matches]
        
        # Keyword semantic fallback
        keyword_matches = self.index.keyword_search(query, top_k=top_k)
        if keyword_matches:
            return [m["node"] for m in keyword_matches]
        
        return self.index.nodes[:top_k]

    def build_mcp_system_prompt(self, retrieved_nodes: List[DocumentChunk]) -> str:
        profile = self.portfolio_data.get("profile", {})
        context_blocks = "\n\n".join([
            f"### [DOCUMENT: {n.title}] ({n.category})\n{n.content}"
            for n in retrieved_nodes
        ])

        return (
            "You are Prateek AI Assistant — an executive, highly articulate portfolio representative for Prateek Parihar "
            "(AI & Data Operations Analyst in Auckland, New Zealand).\n\n"
            "### CORE PERSONA & BEHAVIOR:\n"
            "1. NATURAL CONVERSATIONAL INTELLIGENCE: Be warm, professional, concise, and executive-ready. Synthesize answers directly and naturally. Never sound like a rigid script.\n"
            "2. MULTI-INTENT ANSWERING: If the user asks multiple things in one prompt (e.g. asking about experience AND contact details), address BOTH questions with clarity.\n"
            "3. ACCURATE RAG GROUNDING: Ground your answers in the retrieved context below. Highlight Prateek's real-world impact (e.g. AA Motoring telemetry, iTech24 digital transformation, Kiwi Budget Tours AI booking platform, Master's thesis on EV fuel elasticity).\n"
            "4. CLEAN MARKDOWN FORMATTING: Use clear bolding, crisp bullet points, and clean links where relevant (e.g. [Kiwi Budget Tours](https://kiwibudgettours.com) or [Thesis Case Study](projects/ev-fuel-price-thesis/index.html)).\n"
            "5. NO UNNECESSARY FLUFF: Keep answers dense with value, free of robotic preambles like 'Based on my data'. Answer with natural authority.\n\n"
            f"### CONTACT DETAILS FOR PRATEEK:\n"
            f"Email: {profile.get('email')} | Phone: {profile.get('phone')} | LinkedIn: {profile.get('linkedin')} | GitHub: {profile.get('github')} | CV: {profile.get('resume_pdf')}\n\n"
            "### RETRIEVED KNOWLEDGE CONTEXT:\n"
            f"{context_blocks}"
        )

    def ask(self, message: str, history: List[Dict[str, str]] = None) -> str:
        history = history or []
        retrieved_nodes = self.retrieve_context(message, top_k=3)
        system_instruction = self.build_mcp_system_prompt(retrieved_nodes)

        # Build conversation turns for Gemini
        contents = []
        for item in history[-8:]:
            role = "user" if item.get("role") == "user" else "model"
            contents.append({"role": role, "parts": [{"text": item.get("text", "")}]})
        
        contents.append({"role": "user", "parts": [{"text": message}]})

        try:
            return self.client.generate_chat_response(system_instruction, contents)
        except Exception as e:
            # Graceful RAG synthesis fallback
            return self._build_deterministic_synthesis(message, retrieved_nodes)

    def _build_deterministic_synthesis(self, query: str, nodes: List[DocumentChunk]) -> str:
        summary_lines = []
        for n in nodes:
            summary_lines.append(f"**{n.title}** ({n.category}):\n{n.content}")
        return "\n\n".join(summary_lines)

# Global Service Instance
rag_service = PortfolioRAGService("portfolio_data.json")

def handle_chat(message: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    reply = rag_service.ask(message, history)
    return {"reply": reply, "model": MODEL_NAME}
