import asyncio
from bot.parser import parse_input

text = """
7    Ta 4.70
7    Ta 4.30
11  Ta 4.00
1    Ta 5.20
4    Ta 4.40
11  Ta 4.30
11  Ta 2.40
7    Ta 4.30
"""

def test():
    res = parse_input(text)
    print("ITEMS:", res.items)
    print("ERRORS:", res.errors)

if __name__ == "__main__":
    test()
