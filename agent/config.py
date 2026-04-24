# agent/config.py
# Shared Neo4j connection config and LLM factory for all agent modules.

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from langchain_anthropic import ChatAnthropic

load_dotenv()

NEO4J_URI      = os.getenv("NEO4J_URI")
NEO4J_USER     = os.getenv("NEO4J_USERNAME")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def get_llm(max_tokens: int = None) -> ChatAnthropic:
    """
    Returns a Claude Sonnet instance.
    Pass max_tokens to cap output length (useful for narrative-only calls).
    """
    kwargs = dict(
        model="claude-sonnet-4-6",
        temperature=0,
        anthropic_api_key=os.getenv("ANTHROPIC_API_KEY"),
    )
    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens
    return ChatAnthropic(**kwargs)
