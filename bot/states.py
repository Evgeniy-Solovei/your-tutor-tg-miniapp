"""FSM-состояния регистрации и сценариев бота."""

from aiogram.fsm.state import State, StatesGroup


class Registration(StatesGroup):
    display_name = State()
    grade = State()
    goal = State()
    subject = State()
    exam_track = State()
    city = State()
    city_pick = State()
    school = State()
    school_pick = State()
    exam_year = State()


class DailyPractice(StatesGroup):
    waiting_answer = State()
    multi_select = State()


class TopicPractice(StatesGroup):
    choose_topic = State()


class ParentFlow(StatesGroup):
    enter_code = State()
