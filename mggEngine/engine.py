import asyncio
import cv2
import numpy as np
import os
import sys
import pyautogui

import logging
logger = logging.getLogger('mggEngine')

from .states import *

class MGGEngine():
    def __init__(self, action_callback, window_title):
        logger.info("Initalizing MGGEngine")

        self._state_to_coroutine = {
            GameStates.MAIN_MENU: self._handle_main_menu,
            GameStates.GO_FISH_SPLASH: self._handle_go_fish_splash,
            GameStates.NAME_ENTRY: self._handle_name_entry,
            GameStates.WAIT_FOR_TEXT: self._handle_wait_for_text,
            GameStates.CARD_SELECTION: self._handle_card_selection,
            GameStates.GET_NEW_CARD: self._handle_get_new_card,
            GameStates.GAME_OVER: self._handle_game_over,
        }

        self._action_callback = action_callback
        self._window_title = window_title
        self._window_id = None
        self._game_state = GameStates.INIT
        self._xdo = None

        # Get path of the mggEngine module's installation
        # so we can read the templates from.
        import inspect
        self._base_template_path = inspect.getfile(GameStates)[:-9] + 'templates/'

        if sys.platform == "linux":
            from xdo import Xdo
            self._xdo = Xdo()

        if sys.platform == "linux":
            self._window_id = self._xdo.search_windows(window_title.encode())[0]
            logger.debug(f'Got Window {self._window_id}')
        else:
            raise NotImplementedError(f"Need to fetch window ID in {sys.platform}")

    def __capture_window(self):
        '''
        Takes a temporary screenshot of the Game's window.
        '''
        if sys.platform == "linux":
            win_location = self._xdo.get_window_location(self._window_id)
            win_size = self._xdo.get_window_size(self._window_id)
        else:
            raise NotImplementedError(f"__capture_window not implemented for {sys.platform}")
        return np.array(pyautogui.screenshot(region=(win_location[0], win_location[1] - 23, win_size[0], win_size[1])))

    def __match_template(self, template_path, img=None, threshold=0.70):
        '''
        Find a match inside an image using a template and returns
        its coordinations if True.
        '''
        template = cv2.imread(self._base_template_path + template_path, 0)
        w, h = template.shape[:: -1]

        if img is None:
            img = self.__capture_window()

        img_gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        res = cv2.matchTemplate(img_gray, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where( res >= threshold)
        for pt in zip(*loc[::-1]):
            return (True, int(pt[0] + w/2), int(pt[1] + h/2))
        return (False, 0, 0)

    def start(self):
        '''
        Starts the engine.  This creates a main task within the current
        asyncio loop.
        '''
        logger.info('Starting MGGEngine')
        self._game_state = GameStates.MAIN_MENU
        loop = asyncio.get_event_loop()
        loop.create_task(self._main_task())

    async def _main_task(self):
        while True:
            coro = self._state_to_coroutine.get(self._game_state)
            if not coro:
                logger.critical(f"Don't know how to handle state {self._game_state}!")

            dont_sleep = await coro()

            if not dont_sleep:
                await asyncio.sleep(1)

    async def _handle_main_menu(self):
        logger.debug('_handle_main_menu')
        if self.__match_template('gui/logo.png')[0] == True:
            logger.debug('Found logo!  Going to Go Fish.')

            self._xdo.send_keysequence_window(self._window_id, b'G+Return')
            self._game_state = GameStates.GO_FISH_SPLASH

    async def _handle_go_fish_splash(self):
        logger.debug('_handle_go_fish_splash')
        if self.__match_template('gofish/title.png')[0] == True:
            self._xdo.send_keysequence_window(self._window_id, b'Return')
            self._game_state = GameStates.NAME_ENTRY
            return True

    async def _handle_name_entry(self):
        logger.debug('_handle_name_entry')
        timesChecked = 0
        while True:
            if self.__match_template('gui/name_entry.png')[0] == True:
                name = await self._action_callback(action=self._game_state)
                logger.debug('Entering Name.')
                pyautogui.write(name, interval=.15)
                pyautogui.press('enter')
                self._game_state = GameStates.WAIT_FOR_TEXT
                break
            else:
                timesChecked += 1
                if timesChecked < 5:
                    await asyncio.sleep(1)
                else:
                    # We must've gotten past through that already, skip on ahead.
                    self._game_state = GameStates.WAIT_FOR_TEXT
                    break

    async def _handle_wait_for_text(self):
        img = self.__capture_window()
        for temp_file in os.listdir(self._base_template_path + 'gofish/text'):
            if self.__match_template(f'gofish/text/{temp_file}', img, 0.90)[0] == True:
                if temp_file.startswith('yourturn'):
                    self._game_state = GameStates.CARD_SELECTION
                    return True
                elif temp_file.startswith('gofish'):
                    self._game_state = GameStates.GET_NEW_CARD
                    return True
                elif temp_file.startswith('gameover'):
                    self._game_state = GameStates.GAME_OVER
                    return True
        logger.debug("Waiting for Text...")

    async def _handle_card_selection(self):
        logger.info("It's our turn now!")
        img = self.__capture_window()

        available_cards = {}
        for card in os.listdir(self._base_template_path + 'gofish/cards'):
            res = self.__match_template(f'gofish/cards/{card}', img)
            if res[0] == True:
                available_cards[card[:-4]] = res
                logger.debug(f'Found {card}!')

        if not available_cards:
            logger.critical('No cards found!')
            return False

        logger.debug(f'available_cards: {available_cards.keys()}')
        selection = await self._action_callback(action=self._game_state, available_cards=list(available_cards.keys()))
        res = available_cards.get(selection)
        if res:
            win_location = self._xdo.get_window_location(self._window_id)
            pyautogui.moveTo(res[1] + win_location[0], res[2] + win_location[1] - 20)
            pyautogui.click()
            await asyncio.sleep(1)
            self._game_state = GameStates.WAIT_FOR_TEXT
        else:
            logger.info(f'{selection} not in available_cards!')

    async def _handle_get_new_card(self):
        logger.info("It's time to Go Fish!")
        res = self.__match_template(f'gofish/deck.png')
        if res[0] == True:
            win_location = self._xdo.get_window_location(self._window_id)
            pyautogui.moveTo(res[1] + win_location[0], res[2] + win_location[1] - 20)
            pyautogui.click()
            await asyncio.sleep(1)
        else:
            logger.warning("Couldn't find the deck of cards!")
        self._game_state = GameStates.WAIT_FOR_TEXT

    async def _handle_game_over(self):
        logger.info("Game over!")
        play_again = await self._action_callback(action=self._game_state)
        if play_again:
            pyautogui.press('y')
            self._game_state = GameStates.WAIT_FOR_TEXT
        else:
            pyautogui.press('n')
            self._game_state = GameStates.MAIN_MENU
