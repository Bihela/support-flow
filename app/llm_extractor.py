import os
import gc
import json
import sys
import psutil
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

def extract_ticket_data(title: str, description: str, comments: list) -> dict:
    import re
    model_path = download_model()
    llm = None
    try:
        # Pre-process description
        cleaned_desc = re.sub(r'^(Hi|Hello|Dear|Hi all|Hello team)[\s\w]+,?\s*', '', description, flags=re.IGNORECASE).strip()
        cleaned_desc = cleaned_desc.lstrip(",.?!:; \t\n")

        # Format user message payload with rigid boundaries
        user_message = f"Title: {title}\n\n[TICKET DESCRIPTION]\n{cleaned_desc}\n\n[TICKET COMMENTS]\n"
        for idx, comment in enumerate(comments, 1):
            user_message += f"Comment {idx}: {comment}\n"

        # Adjust process priority
        try:
            if sys.platform == "win32":
                p = psutil.Process(os.getpid())
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            else:
                os.nice(10)
        except Exception:
            pass

        system_prompt = (
            "You are a strict data parsing system. Read the provided support ticket.\n\n"
            "Extract the Client name.\n\n"
            "Clean the Title.\n\n"
            "Read the [TICKET DESCRIPTION] and summarize the core technical Symptom in one sentence. Do not include greetings.\n\n"
            "Read the [TICKET COMMENTS]. Extract the exact technical troubleshooting steps taken by the support engineers to resolve the issue. Format these as an array of strings. If no resolution steps are found, return an empty array [].\n\n"
            'Output ONLY valid JSON: {"client": "...", "title": "...", "symptom": "...", "steps": ["...", "..."]}.'
        )

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
            
        return json.loads(content)
    finally:
        if llm is not None:
            del llm
        gc.collect()
