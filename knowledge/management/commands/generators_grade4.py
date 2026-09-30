"""
Генераторы доп. заданий 4 класса — русский язык, программа РБ.
Последний класс начальной школы с цветными карточками.
"""
from __future__ import annotations

import random

from knowledge.management.commands.generators_grade1 import build_task
from knowledge.management.commands.generators_grade2 import (
    gen_paired_consonants,
    gen_root_words,
    gen_sentence_members,
    gen_unstressed_root,
    _pad_to_count,
)
from knowledge.management.commands.generators_grade3 import (
    gen_adjective,
    gen_belarus_culture,
    gen_homogenous,
    gen_pronoun,
    gen_unpronounceable,
    gen_verb_tense_ne,
)


def gen_noun_declension(topic_id, topic_name, tb_qs):
    items = [
        ('школа', '1-е', 'ж.р., -а'),
        ('земля', '1-е', 'ж.р., -я'),
        ('Беларусь', '3-е', 'ж.р., ь'),
        ('ученик', '2-е', 'м.р.'),
        ('Минск', '2-е', 'м.р.'),
        ('Неман', '2-е', 'м.р.'),
        ('окно', '2-е', 'ср.р., -о'),
        ('море', '2-е', 'ср.р., -е'),
        ('тетрадь', '3-е', 'ж.р., ь'),
        ('ночь', '3-е', 'ж.р., ь'),
        ('мышь', '3-е', 'ж.р., ь'),
        ('река', '1-е', 'ж.р., -а'),
    ]
    endings = [
        ('к школе', 'Дательный', '1-е'),
        ('у ученика', 'Родительный', '2-е'),
        ('о тетради', 'Предложный', '3-е'),
        ('с Неманом', 'Творительный', '2-е'),
        ('в Минске', 'Предложный', '2-е'),
        ('без Беларуси', 'Родительный', '3-е'),
    ]
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            w, decl, tip = items[idx // 2 % len(items)]
            q = f'Какое склонение у существительного «{w}»?'
            opts = ['1-е', '2-е', '3-е', 'не склоняется']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '📗 4 класс · склонения (программа РБ).', opts, decl,
                f'«{w}» — {decl} склонение ({tip}).', 'easy', w.upper(), 'Склонения', tb_qs,
            ))
        else:
            form, case, decl = endings[idx // 2 % len(endings)]
            q = f'В словоформе «{form}» какой падеж?'
            opts = [case, 'Именительный', 'Винительный', 'нет падежа']
            # unique
            opts = list(dict.fromkeys(opts))
            while len(opts) < 4:
                opts.append(f'падеж-{len(opts)}')
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐻 Падежные окончания существительных.', opts, case,
                f'«{form}» — {case} падеж ({decl} скл.).', 'medium', case.upper(), 'Падежи', tb_qs,
            ))
    return tasks


def gen_adj_endings(topic_id, topic_name, tb_qs):
    items = [
        ('красивый дом', 'красивого', 'м.р.', 'Р.п.'),
        ('красивая школа', 'красивой', 'ж.р.', 'Д.п.'),
        ('красивое окно', 'красивому', 'ср.р.', 'Д.п.'),
        ('минский парк', 'минского', 'м.р.', 'Р.п.'),
        ('белорусский язык', 'белорусского', 'м.р.', 'Р.п.'),
        ('родная Беларусь', 'родной', 'ж.р.', 'Д.п.'),
        ('синее небо', 'синего', 'ср.р.', 'Р.п.'),
        ('высокие ели', 'высоких', 'мн.ч.', 'Р.п.'),
    ]
    tasks = []
    for idx in range(50):
        phrase, form, gender, case = items[idx % len(items)]
        if idx % 2 == 0:
            q = f'Верное окончание прилагательного в «{phrase}» (Р.п.)?'
            # extract stem roughly
            base = phrase.split()[0]
            wrong = [base[:-2] + 'ый' if len(base) > 3 else base, base[:-2] + 'ая', form + 'а']
            opts = [form] + wrong[:3]
            opts = list(dict.fromkeys(opts))[:4]
            while len(opts) < 4:
                opts.append(f'{form}ъ')
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🦊 Окончания прилагательных.', opts, form,
                f'Верно: «{form}» ({gender}, {case}).', 'medium', form.upper(), 'Прилагательные', tb_qs,
            ))
        else:
            q = f'Какого рода словосочетание «{phrase}»?'
            gmap = {'м.р.': 'мужской', 'ж.р.': 'женский', 'ср.р.': 'средний', 'мн.ч.': 'множественное число'}
            correct = gmap.get(gender, gender)
            opts = ['мужской', 'женский', 'средний', 'множественное число']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐱 Род прилагательного = род существительного.', opts, correct,
                f'«{phrase}» — {correct}.', 'easy', phrase.upper()[:20], 'Прилагательные', tb_qs,
            ))
    return tasks


def gen_verb_conjugation(topic_id, topic_name, tb_qs):
    first = ['читать', 'писать', 'играть', 'думать', 'рисовать', 'гулять', 'говорить'.replace('говорить', 'слушать')]
    first = ['читать', 'писать', 'играть', 'думать', 'рисовать', 'гулять', 'слушать', 'работать']
    second = ['любить', 'видеть', 'слышать', 'смотреть', 'держать', 'дышать', 'терпеть', 'гнать']
    # 11 exceptions II conjugation often taught
    exceptions = ['гнать', 'держать', 'терпеть', 'обидеть', 'видеть', 'слышать', 'ненавидеть', 'зависеть', 'вертеть', 'смотреть', 'дышать']
    tasks = []
    for idx in range(50):
        if idx % 3 == 0:
            w = first[idx // 3 % len(first)]
            q = f'К какому спряжению относится глагол «{w}»?'
            opts = ['I спряжение', 'II спряжение', 'разноспрягаемый', 'не спрягается']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🦉 Спряжения глаголов (4 кл., РБ).', opts, 'I спряжение',
                f'«{w}» — I спряжение (инфинитив не на -ить).', 'easy', w.upper(), 'Спряжение', tb_qs,
            ))
        elif idx % 3 == 1:
            w = second[idx // 3 % len(second)]
            q = f'К какому спряжению относится «{w}»?'
            opts = ['II спряжение', 'I спряжение', 'разноспрягаемый', 'не глагол']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐻 II спряжение: -ить и исключения.', opts, 'II спряжение',
                f'«{w}» — II спряжение.', 'medium', w.upper(), 'Спряжение', tb_qs,
            ))
        else:
            w = exceptions[idx // 3 % len(exceptions)]
            q = f'Глагол-исключение II спряжения — это…'
            wrong = [first[i % len(first)] for i in range(3)]
            opts = [w] + wrong
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐰 11 глаголов-исключений.', opts, w,
                f'«{w}» входит в список исключений II спряжения.', 'medium', w.upper(), 'Исключения', tb_qs,
            ))
    return tasks


def gen_tsya_tsya(topic_id, topic_name, tb_qs):
    with_soft = ['учиться', 'трудиться', 'стараться', 'надеяться', 'улыбаться', 'заниматься']
    without = ['учится', 'трудится', 'старается', 'надеется', 'улыбается', 'занимается']
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            w = with_soft[idx // 2 % len(with_soft)]
            wrong = w.replace('ться', 'тся')
            q = f'Как правильно? (вопрос что делать?)'
            opts = [w, wrong, w.replace('ь', ''), wrong + 'ь']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🦊 -ТЬСЯ в инфинитиве.', opts, w,
                f'«{w}» — неопределённая форма (что делать?), пишем Ь.', 'easy', w.upper(), '-ться/-тся', tb_qs,
            ))
        else:
            w = without[idx // 2 % len(without)]
            wrong = w.replace('тся', 'ться')
            q = f'Как правильно? (он … — что делает?)'
            opts = [w, wrong, w + 'ь', wrong.replace('ь', '')]
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐱 -ТСЯ в 3 лице.', opts, w,
                f'«{w}» — 3 лицо (что делает?), без Ь.', 'easy', w.upper(), '-ться/-тся', tb_qs,
            ))
    return tasks


def gen_soft_sign_2p(topic_id, topic_name, tb_qs):
    forms = ['читаешь', 'пишешь', 'играешь', 'любишь', 'смотришь', 'держишь', 'идёшь', 'несёшь']
    tasks = []
    for idx in range(50):
        w = forms[idx % len(forms)]
        wrong = w.replace('шь', 'ш')
        if idx % 2 == 0:
            q = f'Верное написание во 2 лице ед.ч.?'
            opts = [w, wrong, w.replace('е', 'и', 1), wrong + 'ьь']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🦉 Ь во 2 лице ед. числа.', opts, w,
                f'Во 2 лице ед.ч. пишется Ь: {w}.', 'easy', w.upper(), 'Ь во 2 лице', tb_qs,
            ))
        else:
            q = f'Нужен ли Ь в форме «{w}»?'
            opts = ['Да, нужен', 'Нет', 'Только в прошедшем', 'По желанию']
            tasks.append(build_task(
                q, '🐻 Правило Ь во 2 л. ед.ч.', opts, 'Да, нужен',
                f'Да: «{w}» — 2 лицо ед.ч.', 'easy', 'Ь', 'Ь во 2 лице', tb_qs,
            ))
    return tasks


def gen_simple_complex(topic_id, topic_name, tb_qs):
    items = [
        ('Минск стоит на Свислочи.', 'простое', 1),
        ('Неман течёт по Беларуси.', 'простое', 1),
        ('Солнце светит, и птицы поют.', 'сложное', 2),
        ('Ученик читает книгу.', 'простое', 1),
        ('Ветер шумит, дождь стучит.', 'сложное', 2),
        ('Мама готовит ужин, а папа читает газету.', 'сложное', 2),
    ]
    tasks = []
    for idx in range(50):
        sent, kind, stems = items[idx % len(items)]
        if idx % 2 == 0:
            q = f'Предложение «{sent}» — это…'
            opts = ['простое', 'сложное', 'восклицательное', 'безличное']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '📗 Простые и сложные предложения.', opts, kind,
                f'Это {kind} предложение (грамматических основ: {stems}).', 'medium', kind.upper(), 'Синтаксис', tb_qs,
            ))
        else:
            q = 'Сложное предложение содержит…'
            opts = ['две и более грамматические основы', 'только одно подлежащее', 'только обращение', 'только однородные']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🦊 Признак сложного предложения.', opts,
                'две и более грамматические основы',
                'В сложном — две и более основы.', 'easy', 'СЛОЖНОЕ', 'Синтаксис', tb_qs,
            ))
    return tasks


def gen_appeal(topic_id, topic_name, tb_qs):
    items = [
        ('Ребята, откройте учебники!', 'Ребята'),
        ('Миша, подойди к доске.', 'Миша'),
        ('Дорогая Беларусь, мы любим тебя!', 'Дорогая Беларусь'),
        ('Ученики, слушайте внимательно.', 'Ученики'),
    ]
    tasks = []
    for idx in range(50):
        sent, appeal = items[idx % len(items)]
        if idx % 2 == 0:
            q = f'Найди обращение: «{sent}»'
            words = [w.strip('.,!') for w in sent.replace('!', '').split()]
            wrong = [w for w in words if w not in appeal and len(w) > 2][:3]
            opts = [appeal] + wrong
            while len(opts) < 4:
                opts.append('нет обращения')
            opts = list(dict.fromkeys(opts))[:4]
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐱 Обращение на письме.', opts, appeal,
                f'Обращение: «{appeal}» (выделяется запятыми).', 'medium', appeal.upper()[:20], 'Обращение', tb_qs,
            ))
        else:
            q = 'Как выделяется обращение на письме?'
            opts = ['Запятыми', 'Только точкой', 'Кавычками', 'Не выделяется']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🦉 Знаки при обращении.', opts, 'Запятыми',
                'Обращение выделяется запятыми.', 'easy', 'ЗАПЯТАЯ', 'Обращение', tb_qs,
            ))
    return tasks


def gen_infinitive(topic_id, topic_name, tb_qs):
    pairs = [
        ('читать', 'читает'), ('писать', 'пишет'), ('играть', 'играет'),
        ('любить', 'любит'), ('смотреть', 'смотрит'), ('учиться', 'учится'),
    ]
    tasks = []
    for idx in range(50):
        inf, pers = pairs[idx % len(pairs)]
        if idx % 2 == 0:
            q = f'Неопределённая форма к слову «{pers}»?'
            wrong = [pers, inf + 'ся' if not inf.endswith('ся') else inf[:-2], pers + 'ь']
            opts = [inf] + wrong
            opts = list(dict.fromkeys(opts))[:4]
            while len(opts) < 4:
                opts.append(f'{inf}ть')
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐻 Инфинитив (что делать?).', opts, inf,
                f'Неопределённая форма: «{inf}».', 'easy', inf.upper(), 'Инфинитив', tb_qs,
            ))
        else:
            q = f'На какой вопрос отвечает «{inf}»?'
            opts = ['что делать?', 'что делает?', 'какой?', 'кто?']
            random.shuffle(opts)
            tasks.append(build_task(
                q, '🐰 Вопрос к инфинитиву.', opts, 'что делать?',
                f'«{inf}» — что делать?', 'easy', 'ЧТО ДЕЛАТЬ?', 'Инфинитив', tb_qs,
            ))
    return tasks


def _generate_base(topic_id, topic_name, tb_qs):
    t = topic_name.lower()
    if 'склонен' in t or '1-е' in t or '2-е' in t or '3-е' in t or ('падеж' in t and 'существ' in t):
        return gen_noun_declension(topic_id, topic_name, tb_qs)
    if 'существ' in t:
        return gen_noun_declension(topic_id, topic_name, tb_qs)
    if 'прилаг' in t or 'окончан' in t and 'прилаг' in t:
        return gen_adj_endings(topic_id, topic_name, tb_qs)
    if 'спряжен' in t or 'исключен' in t:
        return gen_verb_conjugation(topic_id, topic_name, tb_qs)
    if 'тся' in t or 'ться' in t:
        return gen_tsya_tsya(topic_id, topic_name, tb_qs)
    if '2 лице' in t or '2-м лице' in t or 'ь во 2' in t:
        return gen_soft_sign_2p(topic_id, topic_name, tb_qs)
    if 'инфинитив' in t or 'неопределённ' in t or 'неопределенн' in t:
        return gen_infinitive(topic_id, topic_name, tb_qs)
    if 'обращен' in t:
        return gen_appeal(topic_id, topic_name, tb_qs)
    if 'сложн' in t or 'прост' in t and 'предлож' in t:
        return gen_simple_complex(topic_id, topic_name, tb_qs)
    if 'однородн' in t:
        return gen_homogenous(topic_id, topic_name, tb_qs)
    if 'местоимен' in t:
        return gen_pronoun(topic_id, topic_name, tb_qs)
    if 'глагол' in t or 'времен' in t:
        if 'спряжен' in t:
            return gen_verb_conjugation(topic_id, topic_name, tb_qs)
        return gen_verb_tense_ne(topic_id, topic_name, tb_qs)
    if 'непроизнос' in t:
        return gen_unpronounceable(topic_id, topic_name, tb_qs)
    if 'безудар' in t:
        return gen_unstressed_root(topic_id, topic_name, tb_qs)
    if 'парн' in t:
        return gen_paired_consonants(topic_id, topic_name, tb_qs)
    if 'корень' in t or 'состав' in t or 'морфем' in t:
        return gen_root_words(topic_id, topic_name, tb_qs)
    if 'член' in t or 'подлежащ' in t:
        return gen_sentence_members(topic_id, topic_name, tb_qs)
    if 'текст' in t or 'повторен' in t or 'комплексн' in t:
        return gen_belarus_culture(topic_id, topic_name, tb_qs)
    return gen_belarus_culture(topic_id, topic_name, tb_qs)


def generate_tasks_for_topic(topic_id, topic_name, tb_qs, count=100):
    base = _generate_base(topic_id, topic_name, tb_qs)
    return _pad_to_count(base, count, topic_name)
