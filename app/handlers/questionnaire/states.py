from aiogram.fsm.state import State, StatesGroup


class QuestionnaireStates(StatesGroup):
    waiting_name_confirm = State()
    waiting_custom_name = State()
    waiting_phone = State()
    waiting_city = State()
    waiting_church_choice = State()
    waiting_custom_church = State()
