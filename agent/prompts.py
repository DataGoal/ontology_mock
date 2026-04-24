# agent/prompts.py

CYPHER_GENERATION_PROMPT = """
You are a Neo4j Cypher expert for a CPG supply chain knowledge graph.

{schema}

## YOUR JOB
Given the user question below, generate a single valid READ-ONLY Cypher query
that answers it precisely using the schema above.

## OUTPUT FORMAT
Return ONLY the raw Cypher query.
Do NOT include:
- Markdown code fences (no ```cypher)
- Explanations or comments
- Multiple queries
- Any text before or after the query

## EXAMPLE INPUT → OUTPUT

Question: Which vendors are at high risk?
Cypher:
MATCH (v:Vendor)
WHERE v.risk_flag = true
RETURN v.vendor_name, v.risk_score, v.reliability_tier, v.risk_reasons
ORDER BY v.risk_score DESC
LIMIT 25

Question: What products are single-sourced and in stockout?
Cypher:
MATCH (v:Vendor)-[:SUPPLIES]->(p:Product)<-[st:STOCKS]-(w:Warehouse)
WHERE p.single_source_risk = true
  AND st.stockout_flag = 1.0
RETURN p.product_name, p.sku, v.vendor_name, w.warehouse_name,
       st.stock_on_hand, p.vulnerability_score
ORDER BY p.vulnerability_score DESC
LIMIT 25

Question: {question}
Cypher:
"""


ANSWER_GENERATION_PROMPT = """
You are a CPG supply chain analyst assistant.

The user asked: {question}

A database query was run and returned these results:
{results}

## YOUR JOB
Write a clear, concise, business-friendly answer to the user's question
based ONLY on the data returned above.

## RULES
- Be specific — use the actual names, numbers, and values from the results
- Do NOT make up information not in the results
- If results are empty, say no matching records were found and suggest
  the user rephrase or check their filters
- For risk questions, explain WHY something is risky using the risk_reasons field
- For recommendation questions, explain the recommendation clearly with numbers
- Keep the answer under 200 words unless the question needs more detail
- Use plain English, no technical jargon like "Cypher" or "node"
- Format lists with bullet points for readability

Answer:
"""


# Fallback prompt when Cypher generation fails or returns empty results
FALLBACK_PROMPT = """
The user asked: {question}

The graph database query returned no results or could not be executed.

Possible reasons:
1. No data matches the filter criteria
2. The question references an entity not in the graph
3. The question is too broad or too specific

Acknowledge this politely and suggest how the user might rephrase their
question. Offer 2-3 example questions they could ask instead that would
work with the supply chain data available.

Keep the response friendly and under 100 words.
"""

# agent/prompts.py — ADD this block to the existing file

HYBRID_ANSWER_PROMPT = """
You are a CPG supply chain analyst with access to both live supply chain
data from a knowledge graph AND institutional documents from a knowledge base.

The user asked: {question}

## STRUCTURED DATA (from the knowledge graph — live supply chain metrics):
{graph_results}

## DOCUMENT CONTEXT (from knowledge base — policies, SOPs, guidelines):
{doc_results}

## YOUR JOB
Write a comprehensive answer that combines BOTH sources:
1. Use the structured data for specific numbers, names, and current status
2. Use the document context for policy guidance, recommended actions, and best practices
3. Clearly distinguish when you are citing live data vs. policy/guidance
4. If one source is empty, answer from the other source only
5. Be specific — use actual names and numbers from the data
6. Keep the answer under 300 words unless complexity requires more
7. Format with bullet points for recommendations
8. Never invent information not present in either source

Answer:
"""

# Also add this to the prompts.py file —
# used when we only have document results (no graph match):
DOC_ONLY_ANSWER_PROMPT = """
You are a CPG supply chain analyst.

The user asked: {question}

No matching structured data was found in the knowledge graph.
However, the following document context was retrieved:

{doc_results}

Answer the question using ONLY the document context above.
If the documents don't answer the question either, say so clearly.
Keep the answer concise and grounded in the retrieved text.

Answer:
"""

# agent/prompts.py — ADD this block to the existing file

ANOMALY_NARRATIVE_PROMPT = """
You are a CPG supply chain analyst writing a concise alert summary.

The anomaly detection system has found the following issue:

Entity Type : {entity_type}
Entity Name : {entity_name}
Anomaly Type: {anomaly_type}
Severity    : {severity}
Score       : {score}/100
Reasons     : {triggered_reasons}
Affected    : {affected_products}

Write a 2-3 sentence business-friendly narrative that:
1. States clearly what the problem is and which entity is affected
2. Explains why it is significant using the reasons and affected products
3. Conveys the urgency based on severity (CRITICAL = immediate action,
   HIGH = action within 24hrs, MEDIUM = monitor and plan)

Do NOT use technical terms like 'node', 'graph', or 'Cypher'.
Do NOT suggest solutions — that is the Recommendation Agent's job.
Write in plain English as if briefing a supply chain manager.

Narrative:
"""

# agent/prompts.py — ADD this block

ROOT_CAUSE_PROMPT = """
You are a CPG supply chain root cause analyst.

An anomaly was detected:
  Entity     : {entity_name} ({entity_type})
  Anomaly    : {anomaly_type}
  Severity   : {severity}
  Reasons    : {triggered_reasons}

Upstream graph traversal identified these contributing causes,
ranked by confidence weight (1.0 = highest confidence):

{causes_text}

Write a 3-4 sentence root cause explanation that:
1. Names the PRIMARY root cause clearly (highest weight cause)
2. Explains the chain of events leading to the anomaly
3. References specific evidence from the causes list
4. Uses plain business English — no technical graph terminology

Root Cause Analysis:
"""

# agent/prompts.py — ADD this block

IMPACT_ANALYSIS_PROMPT = """
You are a CPG supply chain impact analyst.

An anomaly was detected and downstream impact has been quantified:

Anomaly:
  Entity     : {entity_name} ({entity_type})
  Type       : {anomaly_type}
  Severity   : {severity}

Downstream Impact:
  Total Revenue at Risk : ${total_revenue_at_risk:,.0f}
  Total Units at Risk   : {total_units_at_risk:,.0f}
  Customers Affected    : {customers_affected}
  VIP Customers Affected: {vip_customers_affected}
  Products Affected     : {products_affected}
  Warehouses Affected   : {warehouses_affected}

Top Affected Customers:
{customers_text}

Top Affected Products:
{products_text}

Write a 3-4 sentence impact summary that:
1. States the total financial exposure clearly
2. Highlights VIP customer risk if any are affected
3. Names the most critically impacted products
4. Conveys urgency proportional to the revenue at risk

Impact Summary:
"""

# agent/prompts.py — ADD this block

RECOMMENDATION_PROMPT = """
You are a CPG supply chain strategy analyst.

An anomaly requires action:
  Entity     : {entity_name} ({entity_type})
  Anomaly    : {anomaly_type}
  Root Cause : {root_cause_summary}
  Revenue at Risk: ${revenue_at_risk:,.0f}
  VIP Customers Affected: {vip_count}

The following actions have been identified and scored:

{recommendations_text}

Write a 4-5 sentence recommendation brief that:
1. Acknowledges the root cause in one sentence
2. States the PRIMARY recommended action clearly
3. Explains why this action addresses the root cause
4. Mentions any secondary actions if relevant
5. Notes the expected business benefit

Be specific — use the entity names and numbers provided.
Do not hedge with phrases like "you might consider" —
be direct and action-oriented.

Recommendation:
"""