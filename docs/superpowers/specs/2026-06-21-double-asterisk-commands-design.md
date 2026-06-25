# Design: Double Asterisk Command Extraction in Draft Editor

We want to allow users to add commands in troubleshooting steps by wrapping them in double asterisks `**...**` (e.g. `**ping 8.8.8.8**`). The backend should extract this and save it to the command field of the step.

## Proposed Changes

### Backend Update
Modify `extract_command_from_instruction` in `app/main.py` to add a regex match for double asterisks:
```python
def extract_command_from_instruction(instr: str) -> Optional[str]:
    # Pattern 1: wrapped in backticks
    match = re.search(r'`([^`]+)`', instr)
    if match:
        return match.group(1).strip()
    
    # Pattern 2: wrapped in double asterisks
    match = re.search(r'\*\*([^*]+)\*\*', instr)
    if match:
        return match.group(1).strip()

    # Pattern 3: starts with a command prompt sign like $ or # or Run: 
    match = re.search(r'(?:^|\s)(?:\$|#|Run:)\s*([a-zA-Z0-9_\-\.\/]+(?:\s+[^\n]+)?)', instr, re.IGNORECASE)
    if match:
        return match.group(1).strip()
        
    return None
```

## Verification Plan

### Manual Verification
1. Add a draft step containing `Run **ping 127.0.0.1** to test local loopback`.
2. Approve the draft.
3. Verify that the step's command is successfully saved as `ping 127.0.0.1`.
