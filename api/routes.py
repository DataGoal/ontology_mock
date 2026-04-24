# api/routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any, List
from agent.graph_chain import run_supply_chain_agent

router = APIRouter()


# ── Request / Response models ─────────────────────────────────────────────────

class QuestionRequest(BaseModel):
    question: str
    show_cypher: Optional[bool] = False   # set True to see the generated Cypher


class AgentResponse(BaseModel):
    question:     str
    answer:       str
    status:       str
    cypher_query: Optional[str]  = None   # only returned if show_cypher=True
    result_count: Optional[int]  = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/ask", response_model=AgentResponse)
async def ask_question(request: QuestionRequest):
    """
    Main chatbox endpoint.
    POST { "question": "Which vendors are at high risk?" }
    Returns a natural language answer grounded in the knowledge graph.
    """
    if not request.question or len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="Question is too short.")

    result = run_supply_chain_agent(request.question.strip())

    return AgentResponse(
        question     = result["question"],
        answer       = result["answer"],
        status       = result["status"],
        cypher_query = result["cypher_query"] if request.show_cypher else None,
        result_count = len(result["raw_results"]) if result["raw_results"] else 0
    )


@router.get("/health")
async def health_check():
    """Quick check that the service is running."""
    return {"status": "ok", "service": "CPG Supply Chain AI Agent"}


@router.get("/sample-questions")
async def sample_questions():
    """
    Returns example questions the agent can answer.
    Useful for the chatbox UI to show suggestions.
    """
    return {
        "vendor_risk": [
            "Which vendors are at high risk right now?",
            "Show me all critical vendors with single-source products",
            "Which Tier 1 vendors in APAC have a risk score above 50?",
            "What are the risk reasons for the top 5 most risky vendors?"
        ],
        "inventory": [
            "Which warehouses have stockouts?",
            "Show me products that are in stockout and single-sourced",
            "Which warehouse is operating over capacity?",
            "What products are below their reorder point?"
        ],
        "manufacturing": [
            "Which plants are underperforming?",
            "Show me plants with high defect rates",
            "Which plants are over capacity?",
            "What is the average machine utilization across all plants?"
        ],
        "recommendations": [
            "How can I rebalance vendor supply for at-risk vendors?",
            "Which vendors can replace a high-risk supplier?",
            "Show me actionable vendor alternatives with HIGH priority",
            "Which carrier should I use for North America routes?"
        ],
        "customer_risk": [
            "Which high-value customers have low fulfillment rates?",
            "Show me VIP customers at risk of being under-served",
            "What is the fulfillment rate for Retail segment customers?"
        ]
    }

# api/routes.py — ADD these blocks to the existing file

from agent.rag_chain import run_hybrid_agent   # add to imports at top

# ── New request/response models ───────────────────────────────────────────────

class HybridQuestionRequest(BaseModel):
    question:          str
    show_cypher:       Optional[bool] = False
    show_doc_sources:  Optional[bool] = False   # show which documents were used


class HybridAgentResponse(BaseModel):
    question:         str
    answer:           str
    answer_source:    str    # hybrid / graph_only / docs_only / no_results
    status:           str
    cypher_query:     Optional[str]        = None
    doc_sources:      Optional[List[str]]  = None
    graph_result_count: Optional[int]      = None
    doc_chunk_count:    Optional[int]      = None


# ── New endpoint ──────────────────────────────────────────────────────────────

@router.post("/ask-with-docs", response_model=HybridAgentResponse)
async def ask_with_docs(request: HybridQuestionRequest):
    """
    Hybrid chatbox endpoint — combines graph data AND document knowledge base.
    POST { "question": "How should I rebalance vendor supply per our procurement policy?" }
    Returns an answer grounded in both live graph data and your SOP documents.
    """
    if not request.question or len(request.question.strip()) < 5:
        raise HTTPException(status_code=400, detail="Question is too short.")

    result = run_hybrid_agent(request.question.strip())

    # Extract document source file names for transparency
    doc_sources = None
    if request.show_doc_sources and result.get("doc_chunks"):
        doc_sources = list({
            c["source_file"] for c in result["doc_chunks"]
        })

    return HybridAgentResponse(
        question           = result["question"],
        answer             = result["answer"],
        answer_source      = result["answer_source"],
        status             = result["status"],
        cypher_query       = result["cypher_query"] if request.show_cypher else None,
        doc_sources        = doc_sources,
        graph_result_count = len(result.get("graph_results") or []),
        doc_chunk_count    = len(result.get("doc_chunks") or []),
    )


@router.get("/knowledge-base/stats")
async def knowledge_base_stats():
    """
    Returns stats about what's in the document knowledge base.
    Useful for confirming ingestion worked correctly.
    """
    from neo4j import GraphDatabase
    import os

    driver = GraphDatabase.driver(
        os.getenv("NEO4J_URI"),
        auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )
    try:
        with driver.session(database=os.getenv("NEO4J_DATABASE", "neo4j")) as session:
            result = session.run("""
                MATCH (kc:KnowledgeChunk)
                RETURN kc.entity_type  AS entity_type,
                       count(kc)       AS chunk_count,
                       collect(DISTINCT kc.source_file) AS files
                ORDER BY chunk_count DESC
            """)
            rows = [dict(r) for r in result]

            total = session.run(
                "MATCH (kc:KnowledgeChunk) RETURN count(kc) AS total"
            ).single()["total"]

        return {"total_chunks": total, "breakdown": rows}
    finally:
        driver.close()


# api/routes.py — ADD these blocks to the existing file

from agent.anomaly_agent import run_anomaly_detection   # add to imports
from models.anomaly import ANOMALY_TYPE_REGISTRY        # add to imports


# ── Request / Response models ─────────────────────────────────────────────────

class AnomalyRunRequest(BaseModel):
    severity_filter:    Optional[str]       = None  # CRITICAL / HIGH / MEDIUM
    entity_type_filter: Optional[str]       = None  # Vendor / Product / Plant etc
    anomaly_types:      Optional[List[str]] = None  # specific types only
    with_narratives:    Optional[bool]      = True  # generate Claude narratives
    max_signals:        Optional[int]       = 100


class AnomalyRunResponse(BaseModel):
    run_at:           str
    total_anomalies:  int
    by_severity:      Dict[str, int]
    by_entity_type:   Dict[str, int]
    signals:          List[Dict]
    critical_signals: List[Dict]


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/anomaly/detect", response_model=AnomalyRunResponse)
async def detect_anomalies(request: AnomalyRunRequest):
    """
    Runs the full anomaly detection sweep.
    Returns all detected anomaly signals sorted by severity then score.

    Examples:
      POST /anomaly/detect                              → all anomalies
      POST /anomaly/detect {"severity_filter":"CRITICAL"} → only CRITICAL
      POST /anomaly/detect {"entity_type_filter":"Vendor"} → vendors only
      POST /anomaly/detect {"with_narratives": false}   → fast, no LLM
    """
    result = run_anomaly_detection(
        anomaly_types      = request.anomaly_types,
        severity_filter    = request.severity_filter,
        entity_type_filter = request.entity_type_filter,
        with_narratives    = request.with_narratives,
        max_signals        = request.max_signals or 100
    )
    return AnomalyRunResponse(**result)


@router.get("/anomaly/types")
async def list_anomaly_types():
    """
    Returns all registered anomaly types with their severity and description.
    Useful for building filter UIs.
    """
    return {
        "total": len(ANOMALY_TYPE_REGISTRY),
        "types": ANOMALY_TYPE_REGISTRY
    }


@router.post("/anomaly/detect/critical")
async def detect_critical_only():
    """
    Shortcut endpoint — runs only CRITICAL severity detections.
    Faster for dashboards that need a quick health check.
    """
    result = run_anomaly_detection(
        severity_filter = "CRITICAL",
        with_narratives = True,
        max_signals     = 50
    )
    return result     

# api/routes.py — ADD these blocks

from agent.root_cause_agent import run_root_cause_analysis     # add to imports
from agent.impact_agent import run_impact_analysis             # add to imports
from agent.recommendation_agent import run_recommendation_agent # add to imports
from pipeline import run_full_pipeline                         # add to imports
from models.anomaly import AnomalySignal                       # add to imports


# ── Pipeline endpoint — runs all 4 agents for CRITICAL signals ────────────────

@router.post("/pipeline/run")
async def run_pipeline(
    severity_filter: Optional[str] = "CRITICAL",
    max_signals:     int            = 10,
    with_narratives: bool           = True
):
    """
    Runs the complete 4-agent pipeline.
    Detect → Root Cause → Impact → Recommend

    Returns fully enriched signal list sorted by severity + score.
    """
    results = run_full_pipeline(
        severity_filter = severity_filter,
        with_narratives = with_narratives,
        max_signals     = max_signals
    )
    return {
        "total_processed": len(results),
        "severity_filter": severity_filter,
        "results": results
    }


# ── Individual agent endpoints (useful for testing each agent alone) ──────────

@router.post("/anomaly/{anomaly_id}/root-cause")
async def get_root_cause(anomaly_id: str, signal: dict):
    """
    Runs root cause analysis for a provided AnomalySignal dict.
    Pass the signal dict from /anomaly/detect in the request body.
    """
    s      = AnomalySignal(**signal)
    result = run_root_cause_analysis(s, with_narrative=True)
    return result.model_dump()


@router.post("/anomaly/{anomaly_id}/impact")
async def get_impact(anomaly_id: str, signal: dict):
    """Runs impact analysis for a provided AnomalySignal dict."""
    s      = AnomalySignal(**signal)
    result = run_impact_analysis(s, with_narrative=True)
    return result.model_dump()


@router.post("/anomaly/{anomaly_id}/recommend")
async def get_recommendations(anomaly_id: str, signal: dict):
    """Runs recommendation agent for a provided AnomalySignal dict."""
    s      = AnomalySignal(**signal)
    result = run_recommendation_agent(s, with_narrative=True)
    return result.model_dump()   