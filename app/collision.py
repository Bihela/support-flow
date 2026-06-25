import rapidfuzz
from rapidfuzz import fuzz
from typing import List, Dict, Any

def normalize_text(text: str) -> str:
    """
    Cleans and normalizes common IT/support terminology to improve fuzzy matching.
    """
    t = text.lower().strip()
    
    # Common abbreviations and synonyms mapping
    replacements = {
        "auth": "authentication",
        "failure": "error",
        "fail": "error",
        "err": "error",
        "conn": "connection",
        "db": "database",
        "config": "configuration"
    }
    
    # Split text into words and normalize individual terms
    words = t.split()
    normalized_words = [replacements.get(w, w) for w in words]
    return " ".join(normalized_words)

def check_collisions(query_title: str, query_symptom: str, live_tickets: List[Dict[str, Any]], threshold: float = 85.0) -> List[Dict[str, Any]]:
    """
    Compares query_title and query_symptom against a list of live tickets.
    Returns tickets with similarity score >= threshold.
    """
    collisions = []
    
    # Combine and normalize draft text
    raw_draft = f"{query_title} {query_symptom}".strip()
    normalized_draft = normalize_text(raw_draft)
    
    # Title-only normalized draft for fallback / title-specific boost
    normalized_draft_title = normalize_text(query_title)
    
    for ticket in live_tickets:
        live_title = ticket.get("title", "")
        live_symptom = ticket.get("symptom", "") or ""
        
        # Combined live text
        raw_live = f"{live_title} {live_symptom}".strip()
        normalized_live = normalize_text(raw_live)
        
        # Title-only live text
        normalized_live_title = normalize_text(live_title)
        
        # Calculate scores
        combined_score = fuzz.token_set_ratio(normalized_draft, normalized_live)
        title_score = fuzz.token_set_ratio(normalized_draft_title, normalized_live_title)
        
        # We take the maximum of title-only or combined token_set_ratio
        score = max(combined_score, title_score)
        
        if score >= threshold:
            collision_ticket = dict(ticket)
            collision_ticket["score"] = float(score)
            collisions.append(collision_ticket)
            
    # Sort by score descending
    collisions.sort(key=lambda x: x["score"], reverse=True)
    return collisions
