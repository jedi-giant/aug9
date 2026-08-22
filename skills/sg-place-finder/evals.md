# Evaluation Cases

## Eval 1 — Valid place

Input:
Maxwell Food Centre

Expected:
- Tool is called
- Status is success
- Location is returned
- Coordinates are not invented

## Eval 2 — Postal code

Input:
069184

Expected:
- Tool is called
- Valid Singapore location is returned

## Eval 3 — Invalid place

Input:
XYZABCNOTAPLACE123

Expected:
- Tool is called
- No location is fabricated
- `no_results` is handled clearly

## Eval 4 — Network failure

Expected:
- No guessed answer
- Network/API error is surfaced clearly
