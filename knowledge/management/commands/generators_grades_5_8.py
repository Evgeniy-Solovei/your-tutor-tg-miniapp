"""
Генераторы доп. заданий 5–8 классов — русский язык, программа РБ.
Без картинок. Ё и Е — разные буквы. Немного фактов о Беларуси в миксе.
"""
from __future__ import annotations

import random

from knowledge.management.commands.generators_grade1 import build_task
from knowledge.management.commands.generators_grade2 import _pad_to_count
from knowledge.management.commands.generators_grade3 import gen_belarus_culture


def _yo_ye_tasks(tb_qs):
    """В программе РБ буквы Е и Ё различают."""
    pairs = [
        ('ёлка', 'елка'), ('ёж', 'еж'), ('пчела', 'пчёла'), ('береза', 'берёза'),
        ('ежик', 'ёжик'), ('елка', 'ёлка'), ('слезы', 'слёзы'), ('звезда', 'звёзды'),
    ]
    tasks = []
    for idx in range(20):
        a, b = pairs[idx % len(pairs)]
        # correct is the one with proper ё where needed
        correct = a if 'ё' in a or a in ('ёлка', 'ёж', 'ёжик', 'берёза', 'пчёла', 'слёзы', 'звёзды') else b
        # normalize known
        correct_map = {
            'елка': 'ёлка', 'еж': 'ёж', 'ежик': 'ёжик', 'береза': 'берёза',
            'пчела': 'пчела', 'пчёла': 'пчела', 'слезы': 'слёзы', 'звезда': 'звезда',
            'звёзды': 'звёзды', 'слёзы': 'слёзы', 'берёза': 'берёза', 'ёлка': 'ёлка',
            'ёж': 'ёж', 'ёжик': 'ёжик',
        }
        # pick word that should have ё
        word_yo = ['ёлка', 'ёж', 'ёжик', 'берёза', 'слёзы', 'звёзды'][idx % 6]
        wrong = word_yo.replace('ё', 'е')
        q = 'В программе РБ буквы Е и Ё разные. Как правильно?'
        opts = [word_yo, wrong, wrong + 'ь', word_yo.replace('ё', 'йо')]
        random.shuffle(opts)
        tasks.append(build_task(
            q, '📗 Орфография РБ: Е и Ё — разные буквы.', opts, word_yo,
            f'Верно: «{word_yo}». В белорусской школе Е и Ё не смешивают.',
            'easy', word_yo.upper(), 'Е и Ё', tb_qs,
        ))
    return tasks


def _ortho(tb_qs):
    items = [
        ('вОды → водА', 'безударная гласная', ['воды', 'водитель', 'водить', 'водный'], 'воды'),
        ('дубЫ → дуб', 'парная согласная', ['дубы', 'дупло', 'дубина', 'дубок'], 'дубы'),
        ('солнце ← солнечный', 'непроизносимая', ['солнце', 'стол', 'кот', 'дом'], 'солнце'),
        ('класс', 'двойные согласные', ['класс', 'клас', 'клаасс', 'клясс'], 'класс'),
    ]
    tasks = []
    for idx in range(40):
        tip, rule, opts, correct = items[idx % len(items)]
        o = list(opts)
        random.shuffle(o)
        tasks.append(build_task(
            f'Тема «{rule}». Верный вариант ({tip})?',
            '🐻 Орфография (программа РБ).', o, correct,
            f'Правило: {rule}. Верно: {correct}.', 'easy', rule.upper()[:20], rule, tb_qs,
        ))
    return tasks + _yo_ye_tasks(tb_qs)


def _phonetics(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            q = 'Сколько гласных звуков в русском языке (школьный курс РБ)?'
            opts = ['6', '10', '5', '33']
            correct = '6'
            expl = 'Основные гласные звуки: [а], [о], [у], [ы], [и], [э] — 6.'
        else:
            q = 'Буквы Ь и Ъ обозначают звук?'
            opts = ['Нет, звуков не обозначают', 'Да, обозначают', 'Только Ь', 'Только Ъ']
            correct = 'Нет, звуков не обозначают'
            expl = 'Ь и Ъ сами по себе звуков не обозначают.'
        random.shuffle(opts)
        tasks.append(build_task(q, '🦊 Фонетика.', opts, correct, expl, 'easy', 'ФОНЕТИКА', 'Фонетика', tb_qs))
    return tasks


def _lexis(tb_qs):
    tasks = []
    ants = [('весёлый', 'грустный'), ('древний', 'новый'), ('родной', 'чужой')]
    phras = [
        ('бить баклуши', 'бездельничать'),
        ('водить за нос', 'обманывать'),
        ('как с гуся вода', 'ничего не действует'),
    ]
    for idx in range(50):
        if idx % 3 == 0:
            a, b = ants[idx // 3 % len(ants)]
            opts = [b, a, 'быстрый', 'Минск']
            random.shuffle(opts)
            tasks.append(build_task(
                f'Антоним к «{a}»?', '📗 Лексика.', opts, b, f'«{a}» — «{b}».', 'easy', a.upper(), 'Лексика', tb_qs,
            ))
        elif idx % 3 == 1:
            p, m = phras[idx // 3 % len(phras)]
            wrong = [x[1] for x in phras if x[1] != m][:2] + ['название города']
            opts = [m] + wrong
            random.shuffle(opts)
            tasks.append(build_task(
                f'Значение фразеологизма «{p}»?', '🦉 Фразеология.', opts, m, f'«{p}» = {m}.', 'medium', p.upper()[:20], 'Фразеология', tb_qs,
            ))
        else:
            q = 'Какое слово исконно русское (не заимствование)?'
            opts = ['хлеб', 'компьютер', 'шоссе', 'метро']
            random.shuffle(opts)
            tasks.append(build_task(q, '🐱 Лексика.', opts, 'хлеб', '«Хлеб» — исконное слово.', 'easy', 'ХЛЕБ', 'Лексика', tb_qs))
    return tasks


def _morphemics(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            q = 'Общий корень в «лес — лесной — лесник»?'
            opts = ['лес', 'ной', 'ник', 'ле']
            correct = 'лес'
        else:
            q = 'Где приставка?'
            opts = ['входить', 'в дом', 'на столе', 'с другом']
            correct = 'входить'
        random.shuffle(opts)
        tasks.append(build_task(q, '🐻 Морфемика.', opts, correct, f'Верно: {correct}.', 'easy', 'МОРФЕМИКА', 'Морфемика', tb_qs))
    return tasks


def _noun_adj(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            q = 'Какого рода «Беларусь»?'
            opts = ['женский', 'мужской', 'средний', 'общего']
            correct = 'женский'
        else:
            q = 'Какое слово — прилагательное?'
            opts = ['белорусский', 'Беларусь', 'Минск', 'учиться']
            correct = 'белорусский'
        random.shuffle(opts)
        tasks.append(build_task(q, '📗 Морфология.', opts, correct, f'Верно: {correct}.', 'easy', correct.upper()[:15], 'Морфология', tb_qs))
    return tasks


def _verb(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 3 == 0:
            q = 'Время глагола «читал»?'
            opts = ['прошедшее', 'настоящее', 'будущее', 'инфинитив']
            c = 'прошедшее'
        elif idx % 3 == 1:
            q = 'Как пишется НЕ с глаголами?'
            opts = ['не читал (раздельно)', 'нечитал', 'не-читал', 'нё читал']
            c = 'не читал (раздельно)'
        else:
            q = 'Инфинитив к «читает»?'
            opts = ['читать', 'читает', 'читал', 'читающий']
            c = 'читать'
        random.shuffle(opts)
        tasks.append(build_task(q, '🦊 Глагол.', opts, c, f'Верно: {c}.', 'easy', 'ГЛАГОЛ', 'Глагол', tb_qs))
    return tasks


def _numeral(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            q = 'Какое слово — имя числительное?'
            opts = ['пять', 'пятый класс', 'пятерка', 'пятак']
            # both пять and пятый are numerals - quantitative vs ordinal
            c = 'пять'
            expl = '«Пять» — количественное числительное.'
        else:
            q = '«Пятый» — это числительное…'
            opts = ['порядковое', 'количественное', 'собирательное', 'дробное']
            c = 'порядковое'
            expl = '«Пятый» — порядковое числительное.'
        random.shuffle(opts)
        tasks.append(build_task(q, '🦉 Числительное.', opts, c, expl, 'medium', c.upper()[:15], 'Числительное', tb_qs))
    return tasks


def _pronoun_adv(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            q = 'Личное местоимение?'
            opts = ['мы', 'Минск', 'быстро', 'пять']
            c = 'мы'
        else:
            q = 'Наречие отвечает на вопрос…'
            opts = ['как? где? когда?', 'кто? что?', 'какой?', 'что делать?']
            c = 'как? где? когда?'
        random.shuffle(opts)
        tasks.append(build_task(q, '🐱 Местоимение / наречие.', opts, c, f'Верно: {c}.', 'easy', 'МОРФОЛОГИЯ', 'Морфология', tb_qs))
    return tasks


def _participle(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 3 == 0:
            q = 'Причастие совмещает признаки…'
            opts = ['глагола и прилагательного', 'только глагола', 'существительного и наречия', 'только прилагательного']
            c = 'глагола и прилагательного'
        elif idx % 3 == 1:
            q = 'Причастный оборот на письме…'
            opts = ['выделяется запятыми (если обособляется)', 'никогда не выделяется', 'всегда в кавычках', 'через тире только']
            c = 'выделяется запятыми (если обособляется)'
        else:
            q = 'В каком слове НН в причастии?'
            opts = ['прочитанная', 'кованый', 'жёваный', 'стираный']
            c = 'прочитанная'
        random.shuffle(opts)
        tasks.append(build_task(q, '🐻 Причастие (7 кл.).', opts, c, f'Верно: {c}.', 'medium', 'ПРИЧАСТИЕ', 'Причастие', tb_qs))
    return tasks


def _adverbial(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            q = 'Деепричастие обозначает…'
            opts = ['добавочное действие', 'признак предмета', 'количество', 'имя собственное']
            c = 'добавочное действие'
        else:
            q = 'Деепричастный оборот обычно…'
            opts = ['выделяется запятыми', 'не выделяется никогда', 'пишется в скобках', 'пишется с большой буквы']
            c = 'выделяется запятыми'
        random.shuffle(opts)
        tasks.append(build_task(q, '📗 Деепричастие.', opts, c, f'Верно: {c}.', 'medium', 'ДЕЕПРИЧАСТИЕ', 'Деепричастие', tb_qs))
    return tasks


def _service_pos(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 3 == 0:
            q = 'Какое слово — предлог?'
            opts = ['из-за', 'быстрый', 'бежать', 'пять']
            c = 'из-за'
        elif idx % 3 == 1:
            q = 'Какое слово — союз?'
            opts = ['потому что', 'красивый', 'Минск', 'читает']
            c = 'потому что'
        else:
            q = 'Частица НЕ с глаголами пишется…'
            opts = ['раздельно', 'слитно всегда', 'через дефис', 'как угодно']
            c = 'раздельно'
        random.shuffle(opts)
        tasks.append(build_task(q, '🦊 Служебные части речи.', opts, c, f'Верно: {c}.', 'easy', c.upper()[:15], 'Служебные', tb_qs))
    return tasks


def _syntax(tb_qs):
    tasks = []
    for idx in range(50):
        if idx % 4 == 0:
            q = 'В «Минск стоит на Свислочи» подлежащее — …'
            opts = ['Минск', 'стоит', 'на Свислочи', 'нет']
            c = 'Минск'
        elif idx % 4 == 1:
            q = 'Словосочетание связано способом…'
            opts = ['согласования / управления / примыкания', 'только союзом', 'только интонацией', 'не связано']
            c = 'согласования / управления / примыкания'
        elif idx % 4 == 2:
            q = 'Вводные слова на письме…'
            opts = ['выделяются запятыми', 'не выделяются', 'всегда в кавычках', 'пишутся с Ё']
            c = 'выделяются запятыми'
        else:
            q = 'Обособленное определение часто…'
            opts = ['выделяется запятыми', 'не выделяется', 'пишется с тире всегда', 'пишется слитно']
            c = 'выделяется запятыми'
        random.shuffle(opts)
        tasks.append(build_task(q, '🦉 Синтаксис (программа РБ).', opts, c, f'Верно: {c}.', 'medium', 'СИНТАКСИС', 'Синтаксис', tb_qs))
    return tasks


def _text_style(tb_qs):
    tasks = []
    for idx in range(40):
        if idx % 2 == 0:
            q = 'Тип речи «что произошло?» — это…'
            opts = ['повествование', 'описание', 'рассуждение', 'диалог']
            c = 'повествование'
        else:
            q = 'Научный стиль чаще встречается в…'
            opts = ['учебнике', 'дружеской переписке', 'рекламном слогане', 'частушке']
            c = 'учебнике'
        random.shuffle(opts)
        tasks.append(build_task(q, '📗 Текст и стили.', opts, c, f'Верно: {c}.', 'easy', c.upper()[:15], 'Текст', tb_qs))
    # mix Belarus facts lightly (~20%)
    return tasks + gen_belarus_culture(0, 'Беларусь', tb_qs)[:15]


def _dispatch(topic_name: str, tb_qs):
    t = topic_name.lower()
    if 'фонетик' in t or 'звук' in t or 'орфоэп' in t or 'ударен' in t:
        return _phonetics(tb_qs)
    if 'лексик' in t or 'фразеолог' in t or 'заимств' in t or 'устарев' in t or 'синоним' in t:
        return _lexis(tb_qs)
    if 'морфем' in t or 'словообраз' in t or 'корень' in t or 'состав' in t:
        return _morphemics(tb_qs)
    if 'числительн' in t:
        return _numeral(tb_qs)
    if 'нареч' in t or 'местоимен' in t:
        return _pronoun_adv(tb_qs)
    if 'причасти' in t or 'н и нн' in t or 'н/нн' in t:
        return _participle(tb_qs)
    if 'деепричасти' in t:
        return _adverbial(tb_qs)
    if 'предлог' in t or 'союз' in t or 'частиц' in t or 'служебн' in t:
        return _service_pos(tb_qs)
    if 'словосочетан' in t or 'синтакс' in t or 'член' in t or 'обособл' in t or 'вводн' in t or 'обращен' in t or 'тире' in t or 'запят' in t or 'пунктуац' in t or 'предложен' in t:
        return _syntax(tb_qs)
    if 'текст' in t or 'стил' in t or 'реч' in t:
        return _text_style(tb_qs)
    if 'глагол' in t:
        return _verb(tb_qs)
    if 'существ' in t or 'прилаг' in t:
        return _noun_adj(tb_qs)
    if 'орфограф' in t or 'безудар' in t or 'парн' in t or 'непроизнос' in t or 'не с' in t:
        return _ortho(tb_qs)
    if 'повторен' in t:
        return _ortho(tb_qs)[:30] + _syntax(tb_qs)[:20] + gen_belarus_culture(0, topic_name, tb_qs)[:20]
    return _ortho(tb_qs)[:40] + gen_belarus_culture(0, topic_name, tb_qs)[:20]


def generate_tasks_for_topic(topic_id, topic_name, tb_qs, count=100):
    base = _dispatch(topic_name, tb_qs)
    return _pad_to_count(base, count, topic_name)
