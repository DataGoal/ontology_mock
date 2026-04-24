# agent/graph_chain.py

import os
from dotenv import load_dotenv
from langchain_community.graphs import Neo4jGraph
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from neo4j.exceptions import CypherSyntaxError, ClientError

# Choose your LLM — uncomment ONE block:

# --- Option A: OpenAI ---
# from langchain_openai import ChatOpenAI
# def get_llm():
#     return ChatOpenAI(
#         model="gpt-4o",
#         temperature=0,              # temperature=0 = deterministic, critical for Cypher
#         openai_api_key=os.getenv("OPENAI_API_KEY")
#    )

# --- Option B: Anthropic Claude ---
from langchain_anthropic import ChatAnthropic
def get_llm():
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
    )

load_dotenv()

from agent.schema_context import GRAPH_SCHEMA_CONTEXT
from agent.prompts import (
    CYPHER_GENERATION_PROMPT,
    ANSWER_GENERATION_PROMPT,
    FALLBACK_PROMPT
)


# ── Neo4j connection ──────────────────────────────────────────────────────────

def get_neo4j_graph():
    """
    Returns a LangChain Neo4jGraph connection to your Aura instance.
    Neo4jGraph is a thin wrapper that handles session management.
    """
    return Neo4jGraph(
        url=os.getenv("NEO4J_URI"),
        username=os.getenv("NEO4J_USERNAME"),
        password=os.getenv("NEO4J_PASSWORD"),
        database=os.getenv("NEO4J_DATABASE", "neo4j"),
    )


# ── Cypher generation chain ───────────────────────────────────────────────────

def build_cypher_generation_chain(llm):
    """
    Chain 1: Question → Cypher query
    The LLM reads the schema context and generates a Cypher query.
    """
    prompt = PromptTemplate(
        input_variables=["schema", "question"],
        template=CYPHER_GENERATION_PROMPT
    )
    return prompt | llm | StrOutputParser()


# ── Answer generation chain ───────────────────────────────────────────────────

def build_answer_chain(llm):
    """
    Chain 2: Question + DB results → Natural language answer
    The LLM converts raw Cypher results into a readable response.
    """
    prompt = PromptTemplate(
        input_variables=["question", "results"],
        template=ANSWER_GENERATION_PROMPT
    )
    return prompt | llm | StrOutputParser()


def build_fallback_chain(llm):
    """
    Chain 3: Fallback when query fails or returns nothing
    """
    prompt = PromptTemplate(
        input_variables=["question"],
        template=FALLBACK_PROMPT
    )
    return prompt | llm | StrOutputParser()


# ── Main agent function ───────────────────────────────────────────────────────

def run_supply_chain_agent(question: str) -> dict:
    """
    Full pipeline:
      1. Generate Cypher from the question
      2. Execute Cypher against Neo4j Aura
      3. Convert results to natural language answer
      4. Return structured response with all intermediate steps
         (useful for debugging and transparency)
    """
    llm = get_llm()

    try:
        graph = get_neo4j_graph()
    except Exception as e:
        return {
            "question":     question,
            "cypher_query": None,
            "raw_results":  None,
            "answer":       f"Database connection failed: {str(e)}",
            "status":       "db_connection_failed"
        }

    cypher_chain   = build_cypher_generation_chain(llm)
    answer_chain   = build_answer_chain(llm)
    fallback_chain = build_fallback_chain(llm)

    # ── Step 1: Generate Cypher ───────────────────────────────────────────────
    try:
        cypher_query = cypher_chain.invoke({
            "schema":   GRAPH_SCHEMA_CONTEXT,
            "question": question
        })
        # Clean up any accidental markdown fences the LLM might include
        cypher_query = cypher_query.strip()
        cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()

    except Exception as e:
        return {
            "question":     question,
            "cypher_query": None,
            "raw_results":  None,
            "answer":       f"Failed to generate query: {str(e)}",
            "status":       "cypher_generation_failed"
        }

    # ── Step 2: Execute Cypher against Neo4j ─────────────────────────────────
    try:
        raw_results = graph.query(cypher_query)

    except (CypherSyntaxError, ClientError) as e:
        # Cypher was generated but is syntactically invalid
        fallback_answer = fallback_chain.invoke({"question": question})
        return {
            "question":     question,
            "cypher_query": cypher_query,
            "raw_results":  None,
            "answer":       fallback_answer,
            "status":       "cypher_execution_failed",
            "error":        str(e)
        }

    except Exception as e:
        return {
            "question":     question,
            "cypher_query": cypher_query,
            "raw_results":  None,
            "answer":       f"Database error: {str(e)}",
            "status":       "db_error"
        }

    # ── Step 3: Handle empty results ─────────────────────────────────────────
    if not raw_results:
        fallback_answer = fallback_chain.invoke({"question": question})
        return {
            "question":     question,
            "cypher_query": cypher_query,
            "raw_results":  [],
            "answer":       fallback_answer,
            "status":       "no_results"
        }

    # ── Step 4: Generate natural language answer ──────────────────────────────
    # Format raw results cleanly for the LLM
    results_text = "\n".join([str(row) for row in raw_results[:50]])
    # Cap at 50 rows — more than enough context for an answer

    try:
        answer = answer_chain.invoke({
            "question": question,
            "results":  results_text
        })
    except Exception as e:
        # Raw results exist but answer generation failed — still return data
        answer = f"Data retrieved but answer formatting failed: {str(e)}"

    return {
        "question":     question,
        "cypher_query": cypher_query,
        "raw_results":  raw_results,
        "answer":       answer,
        "status":       "success"
    }