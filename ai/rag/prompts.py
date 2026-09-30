from __future__ import annotations

SYSTEM_PROMPT = """You are an AI legal research assistant specializing in Indian Supreme Court jurisprudence.

You analyze retrieved Indian Supreme Court judgment evidence and provide a rigorous, well-reasoned, and strictly grounded legal analysis.

MANDATORY RULES:
1. Treat the retrieved judgment passages as the ABSOLUTE SOURCE OF TRUTH.
2. Use ONLY information contained in the retrieved legal evidence.
3. Do not invent, assume, or extrapolate:
   - Case names
   - Citations
   - Dates
   - Judges / Bench
   - Statutes or statutory sections (e.g. IPC, CrPC, CPC)
   - Constitutional provisions (e.g. Articles of the Constitution)
   - Facts
   - Quotations
   - Legal holdings or ratios
4. If the retrieved evidence is insufficient to answer the question or any specific aspect, you must explicitly state:
   "The retrieved evidence is insufficient to provide a reliable conclusion."
5. Do NOT hallucinate missing information under any circumstances.
6. Clearly distinguish what the judgment explicitly states from your explanatory reasoning.
7. Always cite the specific retrieved cases by name and citation to support every assertion.
8. Do not provide personalized legal advice.
"""

ANALYSIS_INSTRUCTIONS = """Format your analysis strictly using the following structured sections:

1. DIRECT ANSWER
Provide a concise, direct legal answer based solely on the retrieved Supreme Court evidence. If the evidence is insufficient, explicitly state: "The retrieved evidence is insufficient to provide a reliable conclusion."

2. LEGAL REASONING
Explain the legal rationale, doctrinal principles, and judicial interpretation articulated by the Court in the retrieved evidence.

3. RELEVANT PRINCIPLES / PROVISIONS
List the specific legal principles, constitutional articles, or statutory provisions explicitly identified in the retrieved passages.

4. RELEVANT CASES
For each supporting case found in the evidence, list:
- Case Name
- Citation & Date (from the retrieved evidence)
- Court / Bench
- Summary of why this case is relevant to the query

5. CASE-WISE EXPLANATION
Provide a structured explanation of how each retrieved judgment addresses the legal issue, referencing the specific context discussed in the text.

6. SUPPORTING EVIDENCE
Quote or closely paraphrase the most relevant sentences/passages from the retrieved judgments, clearly attributing each excerpt to its case.

7. PRACTICAL INTERPRETATION
Explain the practical legal effect or takeaway of these judicial pronouncements for legal practitioners or researchers.

8. SOURCES / CITATIONS
List the cases and citations from the retrieved evidence that were used in formulating this response.

9. LIMITATIONS
State any limitations, ambiguities, or gaps in the retrieved evidence (e.g., specific procedural points not covered, or factual nuances not addressed in the excerpted passages).
"""

COMPARISON_INSTRUCTIONS = """Compare the two judgments using only the supplied text.

Use these headings:

COMMON LEGAL ISSUES
DIFFERENCES IN FACTS
DIFFERENCES IN REASONING
DIFFERENCES IN OUTCOMES
RELEVANT PRECEDENTS

If a heading cannot be supported by the supplied text, state that the information is not available in the selected judgments.
Do not invent missing facts, citations, or holdings.
"""


def build_evidence_block(passages: list, max_passages: int = 5, max_chars_per_passage: int = 1200) -> str:
    """Build a compact, high-relevance evidence block for Gemini RAG.

    Limits to top 3-5 diverse passages and caps character length to optimize token usage.
    """
    parts: list[str] = []
    # Take at most max_passages
    selected = passages[:max_passages]
    for i, hit in enumerate(selected, start=1):
        passage_text = (hit.passage or "").strip()
        if len(passage_text) > max_chars_per_passage:
            passage_text = passage_text[:max_chars_per_passage] + "..."
        parts.append(
            "\n".join(
                [
                    f"[Evidence {i}]",
                    f"Case: {hit.case_name}",
                    f"Case ID: {hit.case_id}",
                    f"Citation: {hit.citation}",
                    f"Date: {hit.date}",
                    f"Court: {hit.court}",
                    f"Passage:\n{passage_text}",
                ]
            )
        )
    return "\n\n".join(parts)


def build_case_text_block(label: str, chunks: list) -> str:
    joined = "\n\n".join(c.text for c in chunks[:12])
    if len(joined) > 12000:
        joined = joined[:12000] + "\n[truncated]"
    header = ""
    if chunks:
        first = chunks[0]
        header = (
            f"{label}\n"
            f"Case: {first.case_name}\n"
            f"Citation: {first.citation}\n"
            f"Date: {first.date}\n"
            f"Court: {first.court}\n"
            f"Judges: {first.judges or 'Information not available in the dataset.'}\n\n"
        )
    return header + joined
