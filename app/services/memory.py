"""
Memory Service - Cipher's persistent context layer.

ALL memory is stored in the PostgreSQL database so it survives Railway deploys.
Everything discussed in conversation — learnings, playbooks, brand profiles,
user preferences, agent discoveries — persists permanently.

No more JSON files. No more in-memory dicts that wipe on restart.

RECALL QUALITY:
- Semantic scoring via TF-IDF weighted terms (not raw keyword overlap)
- N-gram phrase matching catches multi-word concepts
- Synonym/concept expansion broadens recall for related terms
- PostgreSQL ILIKE pre-filtering keeps DB queries fast
- Priority boosting surfaces critical memories
"""

import json
import math
import re
import uuid
from collections import Counter
from datetime import datetime, timezone
from difflib import SequenceMatcher

from app.core.logging import logger

# --- Importance scoring keywords ---
# Phrases that indicate high-value content worth remembering
_HIGH_IMPORTANCE_SIGNALS = [
    "remember", "always", "never", "important", "rule", "target audience",
    "brand", "strategy", "pricing", "competitor", "playbook", "framework",
    "apply to everything", "from now on", "going forward", "for all",
    "tallowroots", "tallow roots", "shopify", "seo", "ad campaign",
    "product", "customer", "revenue", "conversion",
]
_LOW_IMPORTANCE_SIGNALS = [
    "what time", "hello", "hi", "hey", "thanks", "thank you", "ok",
    "got it", "sure", "sounds good",
]

# --- Stop words — common words that carry no semantic meaning ---
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above",
    "below", "between", "out", "off", "over", "under", "again",
    "further", "then", "once", "here", "there", "when", "where", "why",
    "how", "all", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "just", "because", "but", "and", "or",
    "if", "while", "about", "up", "it", "its", "it's", "i", "me",
    "my", "we", "our", "you", "your", "he", "him", "his", "she",
    "her", "they", "them", "their", "this", "that", "these", "those",
    "what", "which", "who", "whom", "am", "i'm", "don't", "doesn't",
    "didn't", "won't", "wouldn't", "can't", "couldn't", "shouldn't",
    "let", "let's", "get", "got", "also", "like", "know", "think",
    "want", "tell", "show", "make", "see", "go", "going", "much",
    "many", "well", "really", "right", "still", "even",
})

# --- Concept expansion map — broadens recall to related terms ---
_CONCEPT_SYNONYMS = {
    "brand": ["branding", "brand identity", "brand strategy", "positioning", "brand voice"],
    "strategy": ["plan", "approach", "framework", "playbook", "roadmap"],
    "marketing": ["ads", "advertising", "campaign", "promotion", "outreach"],
    "seo": ["search engine optimization", "google ranking", "organic traffic", "keywords"],
    "shopify": ["tallowroots", "tallow roots", "e-commerce", "store", "products"],
    "tallowroots": ["tallow roots", "shopify", "store", "brand"],
    "customer": ["audience", "buyer", "consumer", "user", "target audience"],
    "pricing": ["price", "cost", "rates", "fees", "subscription"],
    "competitor": ["competition", "rival", "competing", "alternative"],
    "property": ["real estate", "house", "investment property", "rental"],
    "investment": ["investing", "portfolio", "roi", "returns", "deal"],
    "revenue": ["income", "earnings", "sales", "profit", "money"],
    "agent": ["agents", "delegate", "tool", "capability"],
    "deploy": ["deployment", "railway", "push", "release", "ship"],
    "memory": ["remember", "recall", "context", "knowledge", "learned"],
    "improve": ["improvement", "fix", "upgrade", "enhance", "optimize"],
    "trading": ["stocks", "crypto", "market", "portfolio", "ticker"],
    "ad": ["ads", "advertisement", "creative", "campaign", "ad copy"],
}

# Reverse map for quick lookup
_TERM_TO_CONCEPTS: dict[str, set[str]] = {}
for _concept, _synonyms in _CONCEPT_SYNONYMS.items():
    _TERM_TO_CONCEPTS.setdefault(_concept, set()).add(_concept)
    for _syn in _synonyms:
        for _word in _syn.lower().split():
            _TERM_TO_CONCEPTS.setdefault(_word, set()).add(_concept)


def _get_db():
    """Get a database session. Returns None if DB is unavailable."""
    try:
        from app.db.database import SessionLocal
        return SessionLocal()
    except Exception as e:
        logger.debug(f"Database unavailable for memory: {e}")
        return None


def _extract_terms(text: str) -> list[str]:
    """Extract meaningful terms from text, removing stop words."""
    words = re.findall(r'[a-z0-9]+(?:\'[a-z]+)?', text.lower())
    return [w for w in words if w not in _STOP_WORDS and len(w) > 1]


def _extract_bigrams(terms: list[str]) -> list[str]:
    """Extract bigram phrases from a list of terms."""
    return [f"{terms[i]} {terms[i+1]}" for i in range(len(terms) - 1)]


def _expand_query_terms(terms: list[str]) -> set[str]:
    """Expand query terms with synonyms/related concepts."""
    expanded = set(terms)
    for term in terms:
        if term in _TERM_TO_CONCEPTS:
            for concept in _TERM_TO_CONCEPTS[term]:
                if concept in _CONCEPT_SYNONYMS:
                    for syn in _CONCEPT_SYNONYMS[concept]:
                        # Add individual words from multi-word synonyms
                        for word in syn.lower().split():
                            if word not in _STOP_WORDS and len(word) > 1:
                                expanded.add(word)
    return expanded


def _relevance_score(query: str, document: str, created_at: datetime | None = None) -> float:
    """Score how relevant a document is to a query.

    Scoring formula (weights sum to 1.0):
    - Weighted term match (35%): TF-IDF-like scoring — rare query terms matching
      in the document count more than common ones. Stop words excluded.
    - Concept match (20%): Synonym-expanded terms that match, catching semantically
      related content even when exact words differ.
    - Phrase match (15%): Bigram phrases from the query found in the document,
      rewarding multi-word concept matches like "brand strategy".
    - Recency (20%): Exponential decay over 30 days. Recent memories rank higher.
    - Priority boost: Applied after scoring (+0.15 critical, +0.08 high).
    """
    query_terms = _extract_terms(query)
    doc_lower = document.lower()
    doc_terms = _extract_terms(document)

    if not query_terms:
        return 0.0

    doc_term_set = set(doc_terms)
    doc_term_counts = Counter(doc_terms)
    total_doc_terms = len(doc_terms) or 1

    # --- Weighted term match (35%) ---
    # Terms that appear less frequently in the document are more meaningful when matched
    term_score = 0.0
    for qt in query_terms:
        if qt in doc_term_set:
            # Inverse frequency weighting: rare terms in doc → higher score per match
            freq = doc_term_counts[qt] / total_doc_terms
            weight = 1.0 / (1.0 + freq * 10)  # diminish very common terms
            term_score += weight
    term_score = min(1.0, term_score / max(len(query_terms), 1))

    # --- Concept match (20%) ---
    expanded_terms = _expand_query_terms(query_terms)
    extra_terms = expanded_terms - set(query_terms)
    concept_hits = sum(1 for t in extra_terms if t in doc_term_set)
    concept_score = min(1.0, concept_hits / max(len(extra_terms), 1)) if extra_terms else 0.0

    # --- Phrase match (15%) ---
    query_bigrams = _extract_bigrams(query_terms)
    if query_bigrams:
        bigram_hits = sum(1 for bg in query_bigrams if bg in doc_lower)
        phrase_score = min(1.0, bigram_hits / len(query_bigrams))
    else:
        phrase_score = 0.0

    # --- Recency (20%) ---
    recency = 0.5
    if created_at:
        now = datetime.now(timezone.utc)
        age_hours = max(0, (now - created_at).total_seconds() / 3600)
        recency = math.exp(-age_hours / 1000)

    # --- Sequence similarity (10%) — kept as a tiebreaker ---
    seq_score = SequenceMatcher(None, query.lower()[:200], doc_lower[:200]).ratio()

    return (
        term_score * 0.35
        + concept_score * 0.20
        + phrase_score * 0.15
        + recency * 0.20
        + seq_score * 0.10
    )


def _score_importance(text: str) -> str:
    """Auto-score the importance of a piece of content.
    Returns: 'critical', 'high', 'normal', or 'low'."""
    text_lower = text.lower()

    # Check for low-importance signals (greetings, acknowledgments)
    low_count = sum(1 for sig in _LOW_IMPORTANCE_SIGNALS if sig in text_lower)
    if low_count >= 2 and len(text) < 100:
        return "low"

    # Check for high-importance signals
    high_count = sum(1 for sig in _HIGH_IMPORTANCE_SIGNALS if sig in text_lower)
    if high_count >= 3:
        return "critical"
    if high_count >= 1:
        return "high"

    # Longer content with substance is more important
    if len(text) > 500:
        return "high"

    return "normal"


def get_collection(name: str = "cipher_memory") -> str:
    """Collections are just a filter on the collection_name column now."""
    return name


def store_memory(
    content: str,
    metadata: dict | None = None,
    collection_name: str = "cipher_memory",
    memory_id: str | None = None,
) -> str:
    """Store a memory entry in the database. Persists across deploys."""
    mem_id = memory_id or str(uuid.uuid4())
    meta = metadata or {}
    meta["source"] = meta.get("source", "conversation")

    db = _get_db()
    if not db:
        logger.warning(f"Memory store failed — no DB connection. Memory {mem_id[:8]} lost.")
        return mem_id

    try:
        from app.db.models import MemoryEntry

        # Check for existing entry with same ID (idempotent for seeds)
        existing = db.query(MemoryEntry).filter(MemoryEntry.id == mem_id).first()
        if existing:
            # Update content or metadata if anything changed
            new_meta_json = json.dumps(meta, default=str)
            changed = False
            if existing.content != content:
                existing.content = content
                changed = True
            if existing.metadata_json != new_meta_json:
                existing.metadata_json = new_meta_json
                changed = True
            if existing.priority != meta.get("priority", "normal"):
                existing.priority = meta.get("priority", "normal")
                changed = True
            if changed:
                db.commit()
                logger.debug(f"Updated existing memory {mem_id[:8]}...")
            db.close()
            return mem_id

        entry = MemoryEntry(
            id=mem_id,
            collection_name=collection_name,
            content=content,
            metadata_json=json.dumps(meta, default=str),
            source=meta.get("source", "conversation"),
            memory_type=meta.get("type", "general"),
            priority=meta.get("priority", "normal"),
        )
        db.add(entry)
        db.commit()
        logger.debug(f"Stored memory {mem_id[:8]}... in {collection_name} [DB]")
    except Exception as e:
        logger.warning(f"Memory store DB write failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        try:
            db.close()
        except Exception:
            pass

    return mem_id


def recall_memories(
    query: str,
    n_results: int = 5,
    collection_name: str = "cipher_memory",
    where: dict | None = None,
) -> list[dict]:
    """Recall memories from database, ranked by semantic relevance to the query.

    Two-phase retrieval:
    1. DB pre-filter: Use ILIKE to pull only rows containing at least one
       meaningful query term (or expanded synonym). This keeps the working
       set small even as memory grows to thousands of entries.
    2. Python scoring: Apply weighted TF-IDF + concept + phrase + recency
       scoring on the pre-filtered set and return the top N.
    """
    db = _get_db()
    if not db:
        return []

    try:
        from sqlalchemy import or_
        from app.db.models import MemoryEntry

        # Build base query
        q = db.query(MemoryEntry).filter(MemoryEntry.collection_name == collection_name)

        # Apply metadata filters
        if where:
            for key, value in where.items():
                if key == "source":
                    q = q.filter(MemoryEntry.source == value)
                elif key == "type":
                    q = q.filter(MemoryEntry.memory_type == value)
                elif key == "priority":
                    q = q.filter(MemoryEntry.priority == value)

        # --- Phase 1: DB-level pre-filter with ILIKE ---
        # Extract meaningful terms and expand with synonyms for broader recall
        query_terms = _extract_terms(query)
        expanded = _expand_query_terms(query_terms)

        # Pick the most specific terms for DB filtering (max 12 to keep query sane)
        # Prefer original query terms over expanded synonyms
        filter_terms = list(query_terms)[:8]
        extra = [t for t in expanded if t not in set(query_terms)][:4]
        filter_terms.extend(extra)

        if filter_terms:
            ilike_filters = [MemoryEntry.content.ilike(f"%{term}%") for term in filter_terms]
            q = q.filter(or_(*ilike_filters))

        # Also always include critical/high priority memories (they may be relevant
        # even without keyword match — e.g., operating principles)
        from sqlalchemy import union_all

        priority_q = db.query(MemoryEntry).filter(
            MemoryEntry.collection_name == collection_name,
            MemoryEntry.priority.in_(["critical", "high"]),
        )

        # Combine: keyword-matched + high-priority, deduplicate in Python
        keyword_entries = q.order_by(MemoryEntry.created_at.desc()).limit(200).all()
        priority_entries = priority_q.order_by(MemoryEntry.created_at.desc()).limit(50).all()

        # Deduplicate by ID
        seen_ids = set()
        entries = []
        for entry in keyword_entries + priority_entries:
            if entry.id not in seen_ids:
                seen_ids.add(entry.id)
                entries.append(entry)

        if not entries:
            db.close()
            return []

        # --- Phase 2: Score and rank ---
        scored = []
        for entry in entries:
            score = _relevance_score(query, entry.content, entry.created_at)
            meta = {}
            if entry.metadata_json:
                try:
                    meta = json.loads(entry.metadata_json)
                except Exception:
                    pass

            # Boost priority memories
            if entry.priority == "critical":
                score = min(1.0, score + 0.15)
            elif entry.priority == "high":
                score = min(1.0, score + 0.08)

            scored.append({
                "id": entry.id,
                "content": entry.content,
                "metadata": meta,
                "distance": 1.0 - score,
                "relevance": score,
            })

        scored.sort(key=lambda x: x["relevance"], reverse=True)
        memories = scored[:n_results]

        # Log what we found for debugging recall quality
        if memories:
            top_score = memories[0]["relevance"]
            logger.info(
                f"Memory recall: {len(entries)} candidates → top {len(memories)} "
                f"(best={top_score:.3f}) for: {query[:60]}..."
            )
        else:
            logger.debug(f"Memory recall: 0 results for: {query[:60]}...")

        return memories

    except Exception as e:
        logger.warning(f"Memory recall failed: {e}")
        return []
    finally:
        try:
            db.close()
        except Exception:
            pass


def store_conversation_context(
    conversation_id: str,
    user_message: str,
    assistant_response: str,
) -> str:
    """Store a conversation exchange as a memory entry.
    This is called after every chat exchange so Cipher remembers ALL context.
    Auto-scores importance based on content."""
    # Truncate to avoid storing massive responses but keep enough context
    user_msg = user_message[:2000] if user_message else ""
    asst_resp = assistant_response[:3000] if assistant_response else ""

    content = f"User: {user_msg}\nAssistant: {asst_resp}"

    # Auto-score importance based on user message content
    importance = _score_importance(user_msg)

    return store_memory(
        content=content,
        metadata={
            "source": "conversation",
            "conversation_id": conversation_id,
            "type": "exchange",
            "priority": importance,
        },
    )


def store_agent_result(
    agent_name: str,
    task_description: str,
    result_summary: str,
    success: bool = True,
    user_query: str = "",
) -> str:
    """Store an agent execution result as a memory entry.
    Called when agents complete work so Cipher remembers what it did and learned."""
    content = (
        f"Agent: {agent_name}\n"
        f"Task: {task_description}\n"
        f"Result: {result_summary[:2000]}\n"
        f"Success: {success}"
    )
    importance = "high" if success else "normal"
    # Boost importance if the user query was important
    if user_query:
        query_importance = _score_importance(user_query)
        if query_importance in ("critical", "high"):
            importance = query_importance

    return store_memory(
        content=content,
        metadata={
            "source": "agent",
            "type": "agent_result",
            "agent_name": agent_name,
            "success": str(success),
            "priority": importance,
        },
    )


def store_learning(
    content: str,
    category: str = "general",
    priority: str = "high",
    source: str = "self_improvement",
) -> str:
    """Store a learned insight or operational knowledge.
    Use this when Cipher discovers something it should remember permanently."""
    return store_memory(
        content=content,
        metadata={
            "source": source,
            "type": "learning",
            "category": category,
            "priority": priority,
        },
    )


def get_memory_stats(collection_name: str = "cipher_memory") -> dict:
    """Get stats about the memory database."""
    db = _get_db()
    if not db:
        return {"collection": collection_name, "total_memories": 0, "storage": "unavailable"}

    try:
        from sqlalchemy import func
        from app.db.models import MemoryEntry

        total = db.query(func.count(MemoryEntry.id)).filter(
            MemoryEntry.collection_name == collection_name
        ).scalar() or 0

        by_type = db.query(
            MemoryEntry.memory_type,
            func.count(MemoryEntry.id),
        ).filter(
            MemoryEntry.collection_name == collection_name
        ).group_by(MemoryEntry.memory_type).all()

        by_source = db.query(
            MemoryEntry.source,
            func.count(MemoryEntry.id),
        ).filter(
            MemoryEntry.collection_name == collection_name
        ).group_by(MemoryEntry.source).all()

        return {
            "collection": collection_name,
            "total_memories": total,
            "storage": "postgresql",
            "by_type": {t: c for t, c in by_type if t},
            "by_source": {s: c for s, c in by_source if s},
        }
    except Exception as e:
        logger.warning(f"Memory stats failed: {e}")
        return {"collection": collection_name, "total_memories": 0, "error": str(e)}
    finally:
        try:
            db.close()
        except Exception:
            pass


def initialize_memory():
    """No-op — memory is now backed by PostgreSQL, initialized via init_db().
    Kept for backward compatibility with self_diagnostic.py."""
    logger.debug("Memory system is database-backed — no initialization needed")


def delete_memory(memory_id: str, collection_name: str = "cipher_memory") -> bool:
    """Delete a specific memory entry."""
    db = _get_db()
    if not db:
        return False

    try:
        from app.db.models import MemoryEntry

        deleted = db.query(MemoryEntry).filter(
            MemoryEntry.id == memory_id,
            MemoryEntry.collection_name == collection_name,
        ).delete()
        db.commit()
        return deleted > 0
    except Exception as e:
        logger.error(f"Failed to delete memory {memory_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        return False
    finally:
        try:
            db.close()
        except Exception:
            pass
