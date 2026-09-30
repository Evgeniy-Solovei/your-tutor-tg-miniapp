"""
Генераторы доп. заданий 3 класса — русский язык по программе РБ
(Минск, Беларусь, Неман; орфография и морфология начальной школы).
"""
from __future__ import annotations

import random

from knowledge.management.commands.generators_grade1 import build_task
from knowledge.management.commands.generators_grade2 import (
    gen_paired_consonants,
    gen_root_words,
    gen_sentence_members,
    gen_synonyms_antonyms,
    gen_unstressed_root,
    _pad_to_count,
)


def gen_unpronounceable(topic_id, topic_name, tb_qs):
    words = [
        ('солнце', 'солнечный'), ('сердце', 'сердечный'), ('здравствуй', 'здравие'),
        ('чувство', 'чувствовать'), ('местный', 'место'), ('известный', 'известие'),
        ('праздник', 'праздновать'), ('счастливый', 'счастье'), ('лестница', 'лесенка'),
        ('поздно', 'опоздать'), ('честный', 'честь'), ('грустный', 'грусть'),
        ('прекрасный', 'прекрасен'), ('областной', 'область'), ('свистнуть', 'свист'),
    ]
    tasks = []
    for idx in range(50):
        w, check = words[idx % len(words)]
        diff = 'easy' if idx < 20 else 'medium'
        if idx % 2 == 0:
            q = f'В каком слове есть непроизносимая согласная?'
            wrong = ['стол', 'кот', 'дом']
            opts = [w] + wrong
            random.shuffle(opts)
            tasks.append(build_task(q, '🐻 Медвежонок учит орфографию РБ.', opts, w, f'В «{w}» есть непроизносимая; проверка: {check}.', diff, w.upper(), 'Непроизносимые', tb_qs))
        else:
            q = f'Какое проверочное к слову «{w}»?'
            wrong = [x[1] for x in words if x[1] != check][:3]
            opts = [check] + wrong
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Лисичка проверяет согласную.', opts, check, f'«{w}» ← {check}.', diff, check.upper(), 'Непроизносимые', tb_qs))
    return tasks


def gen_double_consonants(topic_id, topic_name, tb_qs):
    words = [
        'класс', 'русский', 'белорусский', 'сумма', 'группа', 'аллея', 'коллектив',
        'территория', 'пассажир', 'программа', 'металл', 'рассказ', 'рассвет',
        'суббота', 'анна', 'кирилл', 'эллина', 'масса', 'касса', 'тонна',
    ]
    tasks = []
    for idx in range(50):
        w = words[idx % len(words)]
        wrong = w.replace('сс', 'с').replace('лл', 'л').replace('мм', 'м').replace('пп', 'п').replace('рр', 'р').replace('тт', 'т')
        if wrong == w:
            wrong = w[:-1]
        q = f'Какое написание верно (программа РБ)?'
        opts = [w, wrong, w + 'а', w.replace('и', 'ы', 1) if 'и' in w else w + 'ь']
        opts = list(dict.fromkeys(opts))[:4]
        while len(opts) < 4:
            opts.append(f'{w}ъ')
        random.shuffle(opts)
        tasks.append(build_task(q, '🐰 Зайчик пишет без ошибок.', opts, w, f'Верно: «{w}» — двойные согласные.', 'easy', w.upper(), 'Двойные согласные', tb_qs))
    return tasks


def gen_prefix_vs_preposition(topic_id, topic_name, tb_qs):
    items = [
        ('входить', 'в дом', True),
        ('написать', 'на столе', True),
        ('сделать', 'с другом', True),
        ('подъехать', 'под мостом', True),
        ('в здание', 'входить', False),
        ('на окне', 'написать', False),
        ('по дороге', 'подорожник', False),
        ('без шума', 'бесшумный', False),
    ]
    tasks = []
    for idx in range(50):
        a, b, a_is_prefix = items[idx % len(items)]
        if a_is_prefix:
            q = 'Где приставка (пишется слитно), а не предлог?'
            correct = a
            opts = [a, b, 'в лесу', 'на реке']
        else:
            q = 'Где предлог (пишется отдельно)?'
            correct = a
            opts = [a, b, 'входить', 'написать']
        opts = list(dict.fromkeys(opts))[:4]
        random.shuffle(opts)
        tasks.append(build_task(q, '🦉 Совушка различает приставку и предлог.', opts, correct, 'Приставка — слитно, предлог — отдельно.', 'medium', 'ПРИСТАВКА', 'Приставка / предлог', tb_qs))
    return tasks


def gen_noun_gender_case(topic_id, topic_name, tb_qs):
    items = [
        ('тетрадь', 'женский', 'она'),
        ('Минск', 'мужской', 'он'),
        ('море', 'средний', 'оно'),
        ('Неман', 'мужской', 'он'),
        ('Беларусь', 'женский', 'она'),
        ('школа', 'женский', 'она'),
        ('ученик', 'мужской', 'он'),
        ('окно', 'средний', 'оно'),
        ('Свислочь', 'женский', 'она'),
        ('город', 'мужской', 'он'),
        ('река', 'женский', 'она'),
    ]
    items = [x for x in items if x[1]]
    cases = [
        ('Именительный', 'кто? что?', 'ученик'),
        ('Родительный', 'кого? чего?', 'ученика'),
        ('Дательный', 'кому? чему?', 'ученику'),
        ('Винительный', 'кого? что?', 'ученика'),
        ('Творительный', 'кем? чем?', 'учеником'),
        ('Предложный', 'о ком? о чём?', 'об ученике'),
    ]
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            w, gender, _ = items[idx // 2 % len(items)]
            opts = ['женский', 'мужской', 'средний', 'общего рода']
            random.shuffle(opts)
            q = f'Какого рода существительное «{w}»?'
            tasks.append(build_task(q, '🐱 Котёнок определяет род (программа РБ).', opts, gender, f'«{w}» — {gender} род.', 'easy', w.upper(), 'Род существительных', tb_qs))
        else:
            name, quest, form = cases[idx // 2 % len(cases)]
            q = f'Падеж с вопросами «{quest}» — это…'
            opts = [name] + [c[0] for c in cases if c[0] != name][:3]
            random.shuffle(opts)
            tasks.append(build_task(q, '🐻 Учим падежи.', opts, name, f'{name} падеж: {quest}. Пример: {form}.', 'medium', name.upper(), 'Падежи', tb_qs))
    return tasks


def gen_soft_sign_hissing(topic_id, topic_name, tb_qs):
    with_soft = ['ночь', 'рожь', 'мыш', 'помощь', 'вещь', 'печь', 'дочь', 'речь', 'тишь', 'глушь']
    # fix мыш -> мышь
    with_soft = ['ночь', 'рожь', 'мышь', 'помощь', 'вещь', 'печь', 'дочь', 'речь', 'тишь', 'глушь']
    without = ['врач', 'мяч', 'ключ', 'плащ', 'карандаш', 'товарищ', 'этаж', 'нож', 'шарж', 'малыш']
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            w = with_soft[idx // 2 % len(with_soft)]
            wrong = w.replace('ь', '')
            q = f'Как правильно написать (ж.р., ь после шипящих)?'
            opts = [w, wrong, w + 'а', wrong + 'ьь']
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Ь после шипящих у сущ. ж.р.', opts, w, f'«{w}» — женский род, пишем Ь.', 'easy', w.upper(), 'Ь после шипящих', tb_qs))
        else:
            w = without[idx // 2 % len(without)]
            q = f'Нужен ли Ь в слове «{w}»?'
            opts = ['Нет, не нужен', 'Да, нужен', 'Только в конце предложения', 'По желанию']
            tasks.append(build_task(q, '🐰 У сущ. м.р. после шипящих Ь не пишется.', opts, 'Нет, не нужен', f'«{w}» — мужской род, без Ь.', 'easy', w.upper(), 'Ь после шипящих', tb_qs))
    return tasks


def gen_adjective(topic_id, topic_name, tb_qs):
    items = [
        ('белорусский', 'язык', 'какой?'),
        ('минский', 'парк', 'какой?'),
        ('весёлая', 'песня', 'какая?'),
        ('синее', 'небо', 'какое?'),
        ('добрые', 'дети', 'какие?'),
        ('высокий', 'Неман', 'какой?'),
        ('родная', 'Беларусь', 'какая?'),
        ('школьный', 'двор', 'какой?'),
    ]
    tasks = []
    for idx in range(50):
        adj, noun, quest = items[idx % len(items)]
        if idx % 2 == 0:
            q = f'Какое слово — имя прилагательное?'
            opts = [adj, noun, 'быстро', 'Минск' if noun != 'Минск' else 'Беларусь']
            random.shuffle(opts)
            tasks.append(build_task(q, '🦉 Прилагательное обозначает признак.', opts, adj, f'«{adj}» отвечает на «{quest}».', 'easy', adj.upper(), 'Имя прилагательное', tb_qs))
        else:
            q = f'На какой вопрос отвечает «{adj}» в словосочетании «{adj} {noun}»?'
            opts = [quest, 'кто? что?', 'что делать?', 'где?']
            random.shuffle(opts)
            tasks.append(build_task(q, '🐱 Вопросы к прилагательному.', opts, quest, f'«{adj}» — {quest}.', 'easy', quest.upper(), 'Имя прилагательное', tb_qs))
    return tasks


def gen_pronoun(topic_id, topic_name, tb_qs):
    persons = [
        ('я', '1 лицо, ед.ч.'), ('ты', '2 лицо, ед.ч.'), ('он', '3 лицо, ед.ч.'),
        ('она', '3 лицо, ед.ч.'), ('оно', '3 лицо, ед.ч.'), ('мы', '1 лицо, мн.ч.'),
        ('вы', '2 лицо, мн.ч.'), ('они', '3 лицо, мн.ч.'),
    ]
    tasks = []
    for idx in range(50):
        word, desc = persons[idx % len(persons)]
        if idx % 2 == 0:
            q = f'Какое слово — личное местоимение?'
            opts = [word, 'Минск', 'школа', 'бежать']
            random.shuffle(opts)
            tasks.append(build_task(q, '🐻 Местоимения вместо имён.', opts, word, f'«{word}» — {desc}.', 'easy', word.upper(), 'Местоимения', tb_qs))
        else:
            q = f'Местоимение «{word}» — это…'
            opts = [desc] + [p[1] for p in persons if p[1] != desc][:3]
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Лицо и число местоимения.', opts, desc, f'«{word}»: {desc}.', 'medium', word.upper(), 'Местоимения', tb_qs))
    return tasks


def gen_verb_tense_ne(topic_id, topic_name, tb_qs):
    items = [
        ('читаю', 'настоящее'), ('читал', 'прошедшее'), ('буду читать', 'будущее'),
        ('пишем', 'настоящее'), ('писали', 'прошедшее'), ('напишем', 'будущее'),
        ('идёт', 'настоящее'), ('шёл', 'прошедшее'), ('пойдёт', 'будущее'),
    ]
    tasks = []
    for idx in range(50):
        if idx % 3 == 0:
            form, tense = items[idx // 3 % len(items)]
            q = f'В каком времени глагол «{form}»?'
            opts = ['прошедшее', 'настоящее', 'будущее', 'неопределённое']
            random.shuffle(opts)
            tasks.append(build_task(q, '🐰 Времена глагола.', opts, tense, f'«{form}» — {tense} время.', 'easy', form.upper(), 'Времена глагола', tb_qs))
        elif idx % 3 == 1:
            q = 'Как пишется частица НЕ с глаголами?'
            opts = ['Раздельно: не читал', 'Слитно всегда', 'Через дефис', 'Как угодно']
            tasks.append(build_task(q, '🐱 НЕ с глаголами.', opts, 'Раздельно: не читал', 'Частица НЕ с глаголами пишется раздельно: не читал, не писал.', 'easy', 'НЕ', 'НЕ с глаголами', tb_qs))
        else:
            q = 'Где НЕ с глаголом написано верно?'
            opts = ['не хотел', 'нехотел', 'не-хотел', 'нё хотел']
            random.shuffle(opts)
            tasks.append(build_task(q, '🦉 Проверь НЕ.', opts, 'не хотел', 'Верно: не хотел (раздельно).', 'easy', 'НЕ ХОТЕЛ', 'НЕ с глаголами', tb_qs))
    return tasks


def gen_homogenous(topic_id, topic_name, tb_qs):
    items = [
        ('В лесу растут берёзы, ели, сосны.', 'берёзы, ели, сосны'),
        ('Минск, Гродно, Брест — города Беларуси.', 'Минск, Гродно, Брест'),
        ('Дети читают, пишут, рисуют.', 'читают, пишут, рисуют'),
        ('Неман широкий, быстрый, глубокий.', 'широкий, быстрый, глубокий'),
    ]
    tasks = []
    for idx in range(50):
        sent, members = items[idx % len(items)]
        if idx % 2 == 0:
            q = f'Найди однородные члены: «{sent}»'
            opts = [members, 'только первое слово', 'нет однородных', 'все слова подряд']
            random.shuffle(opts)
            tasks.append(build_task(q, '🐻 Однородные члены.', opts, members, f'Однородные: {members}.', 'medium', 'ОДНОРОДНЫЕ', 'Однородные члены', tb_qs))
        else:
            q = 'Чем разделяются однородные члены на письме?'
            opts = ['Запятой', 'Точкой', 'Восклицательным знаком', 'Ничем']
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Знаки при однородных.', opts, 'Запятой', 'Однородные члены обычно разделяются запятой.', 'easy', 'ЗАПЯТАЯ', 'Однородные члены', tb_qs))
    return tasks


def gen_belarus_culture(topic_id, topic_name, tb_qs):
    """Родина, география Беларуси — для тем про текст/повторение."""
    facts = [
        ('Столица Республики Беларусь?', 'Минск', ['Гродно', 'Брест', 'Гомель']),
        ('Как называется наша страна?', 'Республика Беларусь', ['Россия', 'Украина', 'Польша']),
        ('Крупная река Беларуси?', 'Неман', ['Волга', 'Днепр-только-РФ', 'Дунай']),
        ('Государственный язык обучения в русскоязычной школе РБ включает…', 'русский язык', ['только английский', 'только китайский', 'латынь']),
    ]
    # fix weird distractor
    facts[2] = ('Крупная река Беларуси?', 'Неман', ['Волга', 'Дунай', 'Темза'])
    tasks = []
    for idx in range(50):
        q, correct, wrong = facts[idx % len(facts)]
        opts = [correct] + wrong
        random.shuffle(opts)
        tasks.append(build_task(q, '📗 Учебник русского языка для школ Беларуси.', opts, correct, f'Верно: {correct}.', 'easy', correct.upper()[:20], 'Беларусь', tb_qs))
    return tasks


def _generate_base(topic_id, topic_name, tb_qs):
    t = topic_name.lower()
    if 'непроизнос' in t:
        return gen_unpronounceable(topic_id, topic_name, tb_qs)
    if 'двойн' in t:
        return gen_double_consonants(topic_id, topic_name, tb_qs)
    if 'пристав' in t and 'предлог' not in t:
        return gen_prefix_vs_preposition(topic_id, topic_name, tb_qs)
    if 'пристав' in t or ('предлог' in t and 'пристав' in t):
        return gen_prefix_vs_preposition(topic_id, topic_name, tb_qs)
    if 'ь после' in t or 'шипящ' in t:
        return gen_soft_sign_hissing(topic_id, topic_name, tb_qs)
    if 'падеж' in t or 'род' in t and 'существ' in t:
        return gen_noun_gender_case(topic_id, topic_name, tb_qs)
    if 'существ' in t:
        return gen_noun_gender_case(topic_id, topic_name, tb_qs)
    if 'прилаг' in t:
        return gen_adjective(topic_id, topic_name, tb_qs)
    if 'местоимен' in t:
        return gen_pronoun(topic_id, topic_name, tb_qs)
    if 'глагол' in t or 'времен' in t or 'частица не' in t or 'не с глагол' in t:
        return gen_verb_tense_ne(topic_id, topic_name, tb_qs)
    if 'однородн' in t:
        return gen_homogenous(topic_id, topic_name, tb_qs)
    if 'безудар' in t:
        return gen_unstressed_root(topic_id, topic_name, tb_qs)
    if 'парн' in t or 'звонк' in t:
        return gen_paired_consonants(topic_id, topic_name, tb_qs)
    if 'корень' in t or 'суффикс' in t or 'окончан' in t or 'состав' in t or 'морфем' in t or 'чередован' in t or 'бегл' in t or 'основ' in t:
        return gen_root_words(topic_id, topic_name, tb_qs)
    if 'подлежащ' in t or 'сказуем' in t or 'член' in t or 'синтакс' in t or 'второстепен' in t:
        return gen_sentence_members(topic_id, topic_name, tb_qs)
    if 'синоним' in t or 'антоним' in t:
        return gen_synonyms_antonyms(topic_id, topic_name, tb_qs)
    if 'текст' in t or 'повторен' in t or 'беларус' in t or 'родин' in t:
        return gen_belarus_culture(topic_id, topic_name, tb_qs)
    return gen_belarus_culture(topic_id, topic_name, tb_qs)


def generate_tasks_for_topic(topic_id, topic_name, tb_qs, count=100):
    base = _generate_base(topic_id, topic_name, tb_qs)
    return _pad_to_count(base, count, topic_name)
