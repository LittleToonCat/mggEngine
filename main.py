import asyncio
import logging
import sys
import os
import random

from mggEngine import MGGEngine, GameStates

logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
logging.getLogger('PIL').setLevel(logging.INFO)

logger = logging.getLogger('main')

async def action_callback(**kwargs):
    action = kwargs['action']
    if action == GameStates.NAME_ENTRY:
        return "MGGEngine"
    elif action == GameStates.CARD_SELECTION:
        available_cards = kwargs['available_cards']
        card = random.choice(available_cards)
        logger.info(f'Selecting {card}')
        return card
    elif action == GameStates.GAME_OVER:
        # Play again.
        logger.info("We playin' again, bois!")
        return True

engine = MGGEngine(action_callback, 'Basilisk II')

engine.start()

loop = asyncio.get_event_loop()
try:
    loop.run_forever()
finally:
    loop.run_until_complete(loop.shutdown_asyncgens())
    loop.close()
