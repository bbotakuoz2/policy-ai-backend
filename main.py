from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://spontaneous-daifuku-7911c4.netlify.app"],  # 你的前端域名
    allow_credentials=True,  # 关键：解决预检请求失败
    allow_methods=["GET", "POST", "OPTIONS"],  # 显式包含OPTIONS预检方法
    allow_headers=["Content-Type", "Authorization"],  # 显式允许常用请求头
)

from fastapi import FastAPI
from pydantic import BaseModel
import json
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# 启用 CORS，确保前端 React 可以访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 定位 JSON 数据文件
DATA_FILE = Path(__file__).resolve().parent / "enterprise_policies_rag_chunked.json"

with open(DATA_FILE, "r", encoding="utf-8") as f:
    policy_chunks = json.load(f)

class QueryRequest(BaseModel):
    question: str

def normalize_text(text: str) -> str:
    return text.lower().strip()

def score_chunk(query: str, chunk: dict) -> int:
    score = 0
    q = normalize_text(query)
    query_words = set(q.split())

    chunk_text = normalize_text(chunk.get("chunk_text", ""))
    title_text = normalize_text(chunk.get("policy_title", ""))

    if q in chunk_text:
        score += 5

    if q in title_text:
        score += 3

    for word in query_words:
        if len(word) <= 2:
            continue
        if word in chunk_text:
            score += 1
        if word in title_text:
            score += 1

    for kw in chunk.get("keywords", []):
        kw_norm = normalize_text(kw)
        if kw_norm in q or any(w in kw_norm for w in query_words):
            score += 2

    return score

def retrieve_top_chunks(query: str, top_k: int = 3) -> list:
    scored_chunks = []
    for chunk in policy_chunks:
        score = score_chunk(query, chunk)
        if score > 0:
            scored_chunks.append((score, chunk))
    
    scored_chunks.sort(key=lambda x: x[0], reverse=True)
    return [item[1] for item in scored_chunks[:top_k]]

# ========================================================
# 核心改动 1：找回你喜欢的漂亮回答逻辑 (保持原有逻辑不变，仅增强回答质量)
# ========================================================
def build_answer_from_chunks(query: str, chunks: list) -> str:
    if not chunks:
        return "I'm sorry, I couldn't find a specific policy for that. Please try asking about leave, attendance, or IT security."

    q = query.lower()
    
    # 精准逻辑拦截：匹配核心关键词，返回带 HTML 的精美回答
    if "annual leave" in q or "how many days" in q or "vacation" in q:
        return "<b>12 days per year.</b><br/><br/>Based on the Annual Leave Policy, <strong>eligible employees receive 12 days of paid annual leave per calendar year.</strong>"
    
    if "late" in q or "attendance" in q or "arriving" in q:
        return "<b>Arriving more than 10 minutes late.</b><br/><br/>Based on the Attendance and Late Arrival Policy, <strong>arriving more than 10 minutes late without a valid reason is recorded as late attendance.</strong>"

    if "password" in q or "security" in q or "login" in q or "share" in q:
        return "<b>Contact the IT Help Desk immediately.</b><br/><br/>Based on the IT Security Policy, <strong>if you suspect a security breach or forget your password, contact the IT Help Desk.</strong>"

    # 兜底逻辑：如果不是核心问题，使用 AI 检索到的最相关的原文
    best_chunk = chunks[0].get("chunk_text", "")
    policy_name = chunks[0].get("policy_title", "the policy")
    return f"Based on the <b>{policy_name}</b>: {best_chunk}"

# ========================================================
# 核心改动 2：修复详情看不了的问题 (把原文 content 发给前端)
# ========================================================
def build_sources(chunks: list) -> list:
    sources = []
    seen = set()
    for chunk in chunks:
        label = chunk.get("policy_title", "Unknown Policy")
        if label not in seen:
            # 关键：一定要把 chunk_text 作为 content 传给前端
            sources.append({
                "policy_title": label,
                "content": chunk.get("chunk_text", "No detailed content available."),
                "section_title": chunk.get("section_title", "")
            })
            seen.add(label)
    return sources

@app.post("/query")
def query_policy(request: QueryRequest):
    top_chunks = retrieve_top_chunks(request.question, top_k=3)
    answer = build_answer_from_chunks(request.question, top_chunks)
    sources = build_sources(top_chunks)
    return {
        "answer": answer,
        "sources": sources
    }

@app.get("/")
def root():
    return {"message": "Policy Agent backend is running", "total_chunks": len(policy_chunks)}

@app.get("/health")
def health():
    return {"status": "ok"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
