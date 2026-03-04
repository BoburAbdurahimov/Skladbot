import asyncio
from bot.states import get_state, reset_state, start_operation, OperationMode, ConversationStep, set_eni, set_items
from bot.parser import parse_input
from bot.db import apply_bulk_operation

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

async def test_bot_flow():
    chat_id = 12345
    # Sim user pressing Prixod
    state = start_operation(chat_id, OperationMode.IN)
    # Sim picking sklad
    state.sklad_id = 1
    state.step = ConversationStep.WAITING_ENI
    # Sim picking ENI
    state = set_eni(chat_id, 120)
    print("Step after eni:", state.step)
    
    # Sim sending text
    result = parse_input(text)
    print("Result items:", len(result.items))
    print("Result errors:", len(result.errors))
    
    state = set_items(chat_id, result.items)
    print("Step after set_items:", state.step)

if __name__ == "__main__":
    asyncio.run(test_bot_flow())
