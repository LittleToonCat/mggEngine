from enum import IntEnum

class GameStates(IntEnum):
    INIT        = 0
    MAIN_MENU   = 1
    GO_FISH_SPLASH = 2
    NAME_ENTRY     = 3
    WAIT_FOR_TEXT = 4
    CARD_SELECTION = 5
    GET_NEW_CARD   = 6
    GAME_OVER      = 7
    NEW_GAME       = 8
