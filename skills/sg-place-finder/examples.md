# Examples

## Example 1

User:
Where is Maxwell Food Centre?

Expected behavior:
- Call `resolve_sg_location("Maxwell Food Centre")`
- Return the canonical address and coordinates
- Do not guess missing fields

## Example 2

User:
Find postal code 069184.

Expected behavior:
- Call `resolve_sg_location("069184")`
- Return the resolved Singapore location

## Example 3

User:
Where is XYZABCNOTAPLACE123?

Expected behavior:
- Call `resolve_sg_location("XYZABCNOTAPLACE123")`
- If status is `no_results`, say the location could not be resolved
