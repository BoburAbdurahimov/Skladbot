from bot.parser import parse_input
text = """
7 Ta 4.70
7 Ta 4,70
7 Ta 4 70
7 Ta 4.7
11 Ta 4
11 Ta 4.00
"""
res = parse_input(text)
print("Items:", len(res.items), res.items)
print("Errors:", res.errors)
