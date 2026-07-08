import os
import gc
import json
import re
import sys
import psutil
from html import unescape
from huggingface_hub import hf_hub_download

def download_model() -> str:
    repo_id = "Qwen/Qwen2.5-1.5B-Instruct-GGUF"
    filename = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
    local_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models"))
    os.makedirs(local_dir, exist_ok=True)
    
    # hf_hub_download will return the local file path
    model_path = hf_hub_download(
        repo_id=repo_id,
        filename=filename,
        local_dir=local_dir
    )
    return model_path


# ── Pre-processing utilities ──────────────────────────────────────────

def clean_html_to_text(html_str: str) -> str:
    """Strip HTML tags, decode entities, and normalize whitespace."""
    if not html_str:
        return ""
    text = unescape(html_str)
    # Remove style/script/table blocks entirely
    text = re.sub(r'<(table|span|style|script)[^>]*>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
    # Convert <br>, <br/>, </p>, </li> to newlines for readability
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:p|li|div)>', '\n', text, flags=re.IGNORECASE)
    # Remove all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Normalize whitespace but keep newlines
    lines = [line.strip() for line in text.splitlines()]
    text = '\n'.join(line for line in lines if line)
    return text.strip()


def strip_greetings(text: str) -> str:
    """Remove common greeting prefixes from the start of text."""
    text = re.sub(
        r'^(?:Hi|Hello|Dear|Hi all|Hello team|Dear Team|Good morning|Good afternoon)(?:[\s\w]{1,25})?[,.]?\s*',
        '', text, flags=re.IGNORECASE
    ).strip()
    return text.lstrip(",.?!:; \t\n")


def extract_client_title(raw_title: str) -> tuple:
    """
    Deterministically extract client and clean title from raw Jira title.
    E.g. "LOLC|Unable to Dial Options" → ("LOLC", "Unable to Dial Options")
    Returns (client, clean_title).
    """
    # Strip Jira key prefix like [DST-6667]
    cleaned = re.sub(r'^\[[a-zA-Z0-9]+-\d+\]\s*', '', raw_title).strip()

    # Find earliest delimiter: |, :, or " - "
    delimiters = [
        (cleaned.find('|'), 1),
        (cleaned.find(':'), 1),
        (cleaned.find(' - '), 3)
    ]
    valid = [(idx, dlen) for idx, dlen in delimiters if idx != -1]

    if valid:
        valid.sort(key=lambda x: x[0])
        split_idx, delim_len = valid[0]
        client = cleaned[:split_idx].strip()
        title = cleaned[split_idx + delim_len:].strip()
        return client, title

    return "", cleaned


# ── Resolution & comment analysis ─────────────────────────────────────

# Keywords that signal a resolution/fix comment
_RESOLUTION_KEYWORDS = re.compile(
    r'(?:issue\s+resolved|resolved|fixed|root\s*cause|solution|workaround|'
    r'issue\s+was|problem\s+was|this\s+(?:is|was)\s+(?:a|the)\s+(?:fix|solution|cause)|'
    r'please\s+(?:use|try)|works?\s+(?:now|fine)|'
    r'as\s+informed)',
    re.IGNORECASE
)

# Keywords that signal a ticket is being closed (not useful as resolution)
_CLOSING_KEYWORDS = re.compile(
    r'(?:closing\s+(?:the\s+)?ticket|ticket\s+closed|sent\s+an?\s+email\.?\s*closing|'
    r'enclosed?\s+the\s+ticket)',
    re.IGNORECASE
)

# Keywords indicating the comment is just a delegation/status request, not resolution
_DELEGATION_KEYWORDS = re.compile(
    r'(?:pls\s+attend|please\s+attend|please\s+prioritize|can\s+you\s+please\s+attend|'
    r'what.?s\s+the\s+update|waiting\s+for\s+(?:the\s+)?(?:update|response)|'
    r'customer\s+is\s+asking|couldn.?t\s+attend|why\s+didn.?t\s+you)',
    re.IGNORECASE
)


def find_resolution_comment(comments: list) -> str:
    """
    Identify the comment that contains the actual technical resolution.
    Returns the cleaned text of the resolution comment, or empty string.
    
    Strategy: scan comments in reverse (most recent first), look for
    resolution keywords but skip closing/delegation comments.
    """
    candidates = []

    for i, raw_comment in enumerate(reversed(comments)):
        comment_text = clean_html_to_text(raw_comment)
        if not comment_text or len(comment_text) < 15:
            continue

        # Skip pure closing comments ("sent an email. closing the ticket")
        if _CLOSING_KEYWORDS.search(comment_text) and len(comment_text) < 80:
            continue

        # Skip delegation/status request comments
        if _DELEGATION_KEYWORDS.search(comment_text) and not _RESOLUTION_KEYWORDS.search(comment_text):
            continue

        # Check for resolution keywords
        if _RESOLUTION_KEYWORDS.search(comment_text):
            candidates.append(comment_text)

    if candidates:
        # Return the first (most recent) resolution comment found
        return candidates[0]

    return ""


def extract_resolution_steps(resolution_text: str) -> list:
    """
    Extract actionable technical steps from a resolution comment.
    Returns a list of step strings.
    """
    if not resolution_text:
        return []

    steps = []

    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', resolution_text)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue
        # Skip @mention-only sentences or pure delegation
        if _DELEGATION_KEYWORDS.search(sentence):
            continue
        if _CLOSING_KEYWORDS.search(sentence):
            continue
        # Skip sentences that are just @mentions
        if re.match(r'^[\w\s]+$', sentence) and len(sentence) < 30:
            continue
        steps.append(sentence)

    return steps


def generate_checklist_from_resolution(resolution_text: str, symptom_text: str) -> list:
    """
    Generate basic verification checklist items from the resolution text.
    These are deterministic, keyword-based — the LLM can refine them.
    """
    checklist = []

    if not resolution_text:
        return checklist

    lower_res = resolution_text.lower()

    # If resolution mentions using a different method/device
    if any(kw in lower_res for kw in ['use an external', 'use a different', 'use the', 'try using']):
        checklist.append("Verify the suggested workaround resolves the issue")

    # If resolution mentions a configuration change
    if any(kw in lower_res for kw in ['config', 'setting', 'parameter', 'enable', 'disable']):
        checklist.append("Confirm configuration change is applied")

    # If resolution mentions a restart/service action
    if any(kw in lower_res for kw in ['restart', 'reboot', 'start the service', 'stop the service']):
        checklist.append("Verify service is running after restart")

    # If the symptom mentions inability to do something, verify it works now
    if symptom_text:
        lower_sym = symptom_text.lower()
        if any(kw in lower_sym for kw in ['unable to', 'cannot', "can't", 'not working', 'not responding']):
            checklist.append("Confirm the reported issue no longer occurs")

    # Always add client communication check
    checklist.append("Client has been informed of the resolution")

    return checklist


# ── Main extraction function ──────────────────────────────────────────

def extract_ticket_data(title: str, description: str, comments: list,
                        pre_client: str = "", pre_title: str = "") -> dict:
    """
    Extract structured ticket data from a Jira XML dump using the local LLM.
    
    The approach: do as much deterministic work as possible in Python, then
    ask the small 1.5B model to only summarize/refine what's left.
    
    Args:
        title: Raw title from XML
        description: Raw HTML description from XML
        comments: List of raw HTML comment strings
        pre_client: Pre-extracted client name (from title delimiter parsing)
        pre_title: Pre-extracted clean title (from title delimiter parsing)
    """
    model_path = download_model()
    llm = None
    try:
        # ── Step 1: Clean the description ──
        clean_desc = clean_html_to_text(description)
        clean_desc = strip_greetings(clean_desc)

        # ── Step 2: Find the resolution comment ──
        resolution = find_resolution_comment(comments)

        # ── Step 3: Extract deterministic steps from resolution ──
        resolution_steps = extract_resolution_steps(resolution)

        # ── Step 4: Generate deterministic checklist ──
        checklist = generate_checklist_from_resolution(resolution, clean_desc)

        # ── Step 5: Build a simplified, pre-structured prompt for the model ──
        # Give the model pre-cleaned data so it only needs to summarize/refine
        user_parts = []
        user_parts.append(f"TITLE: {pre_title or title}")
        if pre_client:
            user_parts.append(f"CLIENT: {pre_client}")
        user_parts.append("")
        user_parts.append("[PROBLEM DESCRIPTION]")
        # Truncate description to avoid blowing context window
        desc_truncated = clean_desc[:800] if len(clean_desc) > 800 else clean_desc
        user_parts.append(desc_truncated)

        if resolution:
            user_parts.append("")
            user_parts.append("[RESOLUTION FOUND]")
            res_truncated = resolution[:600] if len(resolution) > 600 else resolution
            user_parts.append(res_truncated)

        user_message = "\n".join(user_parts)

        # Adjust process priority
        try:
            if sys.platform == "win32":
                p = psutil.Process(os.getpid())
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            else:
                os.nice(10)
        except Exception:
            pass

        # ── Improved system prompt with few-shot example ──
        system_prompt = (
            "You are a support ticket parser. Given pre-extracted ticket data, output valid JSON.\n\n"
            "Rules:\n"
            "- symptom: Summarize the technical problem in 1-2 sentences from the PROBLEM DESCRIPTION. No greetings, no names.\n"
            "- steps: Extract the technical resolution steps from RESOLUTION FOUND. Each step should be an actionable instruction. "
            "Do NOT include communication actions like 'sent email' or 'informed client'. If no resolution, return [].\n"
            "- checklist: 1-3 short verification items to confirm the fix works. If no resolution, return [].\n\n"
            "Example input:\n"
            "TITLE: Agent Console Login Failure\n"
            "CLIENT: Acme Corp\n\n"
            "[PROBLEM DESCRIPTION]\n"
            "Agents unable to log into the console. Getting 403 forbidden error.\n\n"
            "[RESOLUTION FOUND]\n"
            "Issue resolved. The agent's IP was not whitelisted in the firewall. Added the IP to the allowed list and restarted the service.\n\n"
            "Example output:\n"
            '{"symptom":"Agents unable to log into the console, receiving 403 forbidden error.",'
            '"steps":["Add the agent IP to the firewall whitelist","Restart the service after applying the firewall change"],'
            '"checklist":["Agent can log into the console successfully","No 403 errors in browser console"]}\n\n'
            'Output ONLY valid JSON: {"symptom":"...","steps":["..."],"checklist":["..."]}'
        )

        content = None
        try:
            from llama_cpp import Llama
            llm = Llama(model_path=model_path, n_ctx=2048, n_threads=2, verbose=False)
            
            response = llm.create_chat_completion(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ],
                temperature=0.1
            )
            content = response["choices"][0]["message"]["content"]
        except Exception as e:
            # Fall back to pure-Python transformers if installed
            try:
                import torch
                from transformers import AutoTokenizer, AutoModelForCausalLM
                
                # Limit threads for torch to prevent CPU strain
                torch.set_num_threads(2)
                
                model_name = "Qwen/Qwen2.5-0.5B-Instruct"
                tokenizer = AutoTokenizer.from_pretrained(model_name)
                model = AutoModelForCausalLM.from_pretrained(
                    model_name,
                    torch_dtype=torch.float32,
                    device_map="cpu"
                )
                
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message}
                ]
                text = tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True
                )
                model_inputs = tokenizer([text], return_tensors="pt")
                
                generated_ids = model.generate(
                    **model_inputs,
                    max_new_tokens=512,
                    temperature=0.1,
                    do_sample=False
                )
                generated_ids = [
                    output_ids[len(input_ids):] for input_ids, output_ids in zip(model_inputs.input_ids, generated_ids)
                ]
                
                content = tokenizer.batch_decode(generated_ids, skip_special_tokens=True)[0]
                
                # Clean up model and free RAM
                del model
                del tokenizer
                gc.collect()
            except Exception:
                raise e
        
        content = content.strip()
        
        # Clean up code blocks if model wrapped JSON in them
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            content = "\n".join(lines).strip()
            
        start = content.find("{")
        end = content.rfind("}")
        if start != -1 and end != -1:
            content = content[start:end+1]

        llm_result = json.loads(content)

        # ── Merge LLM result with deterministic pre-processing ──
        result = {
            "client": pre_client or llm_result.get("client", ""),
            "title": pre_title or llm_result.get("title", title),
            "symptom": llm_result.get("symptom", ""),
            "steps": llm_result.get("steps", []) or resolution_steps,
            "checklist": llm_result.get("checklist", []) or checklist
        }

        # If LLM returned empty steps but we have resolution-derived ones, use those
        if not result["steps"] and resolution_steps:
            result["steps"] = resolution_steps

        # If LLM returned empty checklist but we have deterministic ones, use those
        if not result["checklist"] and checklist:
            result["checklist"] = checklist

        return result

    except (json.JSONDecodeError, Exception):
        # If LLM fails entirely, return deterministic results
        return {
            "client": pre_client,
            "title": pre_title or title,
            "symptom": clean_desc[:200] if clean_desc else "",
            "steps": resolution_steps,
            "checklist": checklist
        }
    finally:
        if llm is not None:
            del llm
        gc.collect()
