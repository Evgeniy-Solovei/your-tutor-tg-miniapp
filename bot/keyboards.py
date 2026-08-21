"""Клавиатуры Telegram-бота."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

from core.webapp_url import get_web_app_url


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text='🔥 Тренировка'), KeyboardButton(text='📚 На сегодня')],
        [KeyboardButton(text='🎟 Варианты'), KeyboardButton(text='🎯 Мои ошибки')],
        [KeyboardButton(text='📖 По теме')],
        [KeyboardButton(text='📊 Статистика'), KeyboardButton(text='📜 История')],
        [KeyboardButton(text='🏆 Рейтинг'), KeyboardButton(text='⚙️ Профиль')],
        [KeyboardButton(text='👨‍👩‍👧 Родителям'), KeyboardButton(text='👨‍👩‍👧 Я родитель')],
    ]
    web_app_url = get_web_app_url()
    if web_app_url:
        rows.insert(
            0,
            [KeyboardButton(text='📱 Мини-приложение', web_app=WebAppInfo(url=f'{web_app_url}/app/'))],
        )
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def miniapp_inline_keyboard() -> InlineKeyboardMarkup | None:
    web_app_url = get_web_app_url()
    if not web_app_url:
        return None
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text='Открыть мини-приложение',
                    web_app=WebAppInfo(url=f'{web_app_url}/app/'),
                )
            ]
        ]
    )


def cancel_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text='❌ Отмена')]],
        resize_keyboard=True,
    )


def parent_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='📊 Отчёт по ребёнку')],
            [KeyboardButton(text='🔗 Привязать по коду')],
            [KeyboardButton(text='⬅️ В обычное меню')],
        ],
        resize_keyboard=True,
    )


def children_pick_keyboard(children: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name[:60], callback_data=f'parent_child:{sid}')]
        for sid, name in children
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def name_suggest_keyboard(suggested: str) -> ReplyKeyboardMarkup:
    rows = []
    if suggested:
        rows.append([KeyboardButton(text=suggested[:64])])
    rows.append([KeyboardButton(text='❌ Отмена')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def grade_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text='9'),
                KeyboardButton(text='10'),
                KeyboardButton(text='11'),
            ],
            [KeyboardButton(text='❌ Отмена')],
        ],
        resize_keyboard=True,
    )


def goal_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='ЦТ после 11 класса')],
            [KeyboardButton(text='ЦЭ после 11 класса')],
            [KeyboardButton(text='Аттестат после 9 класса')],
            [KeyboardButton(text='Просто подтянуть предмет')],
            [KeyboardButton(text='❌ Отмена')],
        ],
        resize_keyboard=True,
    )


def city_skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='⏭ Пропустить')],
            [KeyboardButton(text='❌ Отмена')],
        ],
        resize_keyboard=True,
    )


def school_skip_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='⏭ Пропустить')],
            [KeyboardButton(text='❌ Отмена')],
        ],
        resize_keyboard=True,
    )


def pick_list_keyboard(prefix: str, items: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=label[:60], callback_data=f'{prefix}:{item_id}')]
        for item_id, label in items
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def rating_scope_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='Страна', callback_data='rating:country'),
                InlineKeyboardButton(text='Неделя', callback_data='rating:week'),
            ],
            [
                InlineKeyboardButton(text='Город', callback_data='rating:city'),
                InlineKeyboardButton(text='Школа', callback_data='rating:school'),
            ],
        ]
    )


def after_answer_keyboard(session_task_id: int, can_ai: bool) -> InlineKeyboardMarkup:
    buttons = []
    if can_ai:
        buttons.append(
            [InlineKeyboardButton(text='🤖 Разбор ошибки', callback_data=f'ai:{session_task_id}')]
        )
    buttons.append([InlineKeyboardButton(text='➡️ Дальше', callback_data='next_task')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def multi_choice_keyboard(
    session_task_id: int,
    options: list[tuple[int, str, bool]],
) -> InlineKeyboardMarkup:
    rows = []
    for opt_id, label, selected in options:
        mark = '✅' if selected else '⬜'
        short = label[:48]
        rows.append(
            [
                InlineKeyboardButton(
                    text=f'{mark} {short}',
                    callback_data=f'toggle:{session_task_id}:{opt_id}',
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text='✔️ Ответить',
                callback_data=f'submit:{session_task_id}',
            )
        ]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def topics_keyboard(topics: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text=name[:60], callback_data=f'topic:{topic_id}')]
        for topic_id, name in topics
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
