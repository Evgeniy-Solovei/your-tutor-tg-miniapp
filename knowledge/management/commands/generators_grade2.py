"""
Генераторы доп. заданий для 2 класса (цель 100 на тему, позже до 1000).
Переиспользуем орфографию/фонетику 1 класса + темы 2 класса.
"""
from __future__ import annotations

import random

from knowledge.management.commands.generators_grade1 import (
    build_task,
    gen_alphabet,
    gen_capital_letters,
    gen_cha_scha,
    gen_chk_chn,
    gen_chu_schu,
    gen_hard_soft,
    gen_hyphenation,
    gen_parts_of_speech,
    gen_sentences_punctuation,
    gen_soft_sign_middle,
    gen_soft_sign_split,
    gen_sounds_and_letters,
    gen_stress,
    gen_syllables_split,
    gen_vocab_words,
    gen_voiced_voiceless,
    gen_vowels_and_consonants,
    gen_zhi_shi,
)


def _pad_to_count(tasks: list, count: int, topic_name: str) -> list:
    if len(tasks) >= count:
        return tasks[:count]
    extras = []
    prefixes = [
        ('Выбери верный ответ:', '🦊 Закрепляем правило 2 класса!'),
        ('Найди правильный вариант:', '🐻 Ещё одна карточка по теме.'),
        ('Какой ответ верный?', '🐰 Проверь себя!'),
        ('Отметь верное:', '🐱 Тренажёр 2 класса.'),
    ]
    i = 0
    while len(tasks) + len(extras) < count and tasks:
        src = tasks[i % len(tasks)]
        pref, reading = prefixes[i % len(prefixes)]
        opts = list(src['options'])
        random.shuffle(opts)
        extras.append({
            'question': f'{pref} {src["question"]}',
            'reading_text': f'{reading} Тема: {topic_name}. {src.get("reading_text", "")}',
            'options': opts,
            'correct_answer': src['correct_answer'],
            'explanation': src.get('explanation', ''),
            'difficulty': src.get('difficulty', 'medium'),
            'card_word': src.get('card_word', ''),
            'card_rule': src.get('card_rule', topic_name),
        })
        i += 1
        if i > count * 4:
            break
    return (tasks + extras)[:count]


def gen_unstressed_root(topic_id, topic_name, tb_qs):
    pairs = [
        ('вода', 'воды', 'о'), ('трава', 'травы', 'а'), ('река', 'реки', 'е'),
        ('зима', 'зимы', 'и'), ('стена', 'стены', 'е'), ('гора', 'горы', 'о'),
        ('нога', 'ноги', 'о'), ('земля', 'земли', 'е'), ('снега', 'снег', 'е'),
        ('лист', 'листья', 'и'), ('стол', 'столы', 'о'), ('кот', 'коты', 'о'),
        ('слон', 'слоны', 'о'), ('гриб', 'грибы', 'и'), ('зуб', 'зубы', 'у'),
        ('море', 'моря', 'о'), ('поле', 'поля', 'о'), ('окно', 'окна', 'о'),
        ('письмо', 'письма', 'и'), ('весна', 'вёсны', 'е'), ('звезда', 'звёзды', 'е'),
        ('сестра', 'сёстры', 'е'), ('берёза', 'берёзы', 'е'), ('сосна', 'сосны', 'о'),
        ('дорога', 'дороги', 'о'), ('молоко', 'молока', 'о'), ('город', 'города', 'о'),
    ]
    tasks = []
    for idx in range(50):
        word, check, letter = pairs[idx % len(pairs)]
        diff = 'easy' if idx < 20 else 'medium'
        if idx % 2 == 0:
            q = f'Какая буква пропущена в корне слова «{word[0]}..{word[2:]}»? Проверочное: {check}.'
            opts = [letter, 'ы', 'я', 'ю']
            # unique
            opts = list(dict.fromkeys(opts))
            while len(opts) < 4:
                opts.append(chr(1072 + len(opts)))
            correct = letter
            expl = f'Проверяем ударением: {check} → в слове «{word}» пишем «{letter}».'
            tasks.append(build_task(q, '🐻 Медвежонок ищет проверочное слово.', opts, correct, expl, diff, word.upper(), 'Безударная в корне', tb_qs))
        else:
            q = f'Какое проверочное слово к «{word}»?'
            wrong = [p[1] for p in pairs if p[1] != check][:3]
            opts = [check] + wrong
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Лисичка подбирает проверочное слово.', opts, check, f'К слову «{word}» подходит проверочное «{check}».', diff, check.upper(), 'Проверочное слово', tb_qs))
    return tasks


def gen_paired_consonants(topic_id, topic_name, tb_qs):
    pairs = [
        ('дуб', 'дубы', 'б'), ('сад', 'сады', 'д'), ('нож', 'ножи', 'ж'),
        ('глаз', 'глаза', 'з'), ('мороз', 'морозы', 'з'), ('снег', 'снега', 'г'),
        ('друг', 'друзья', 'г'), ('флаг', 'флаги', 'г'), ('берег', 'берега', 'г'),
        ('гриб', 'грибы', 'б'), ('зуб', 'зубы', 'б'), ('хлеб', 'хлеба', 'б'),
        ('год', 'годы', 'д'), ('труд', 'труды', 'д'), ('плод', 'плоды', 'д'),
        ('рыба', 'рыбы', 'б'), ('ложка', 'ложечка', 'ж'), ('кружка', 'кружечка', 'ж'),
        ('сказка', 'сказочка', 'з'), ('просьба', 'просить', 'с'), ('косьба', 'косить', 'с'),
    ]
    tasks = []
    for idx in range(50):
        w, check, letter = pairs[idx % len(pairs)]
        diff = 'easy' if idx < 20 else 'medium'
        q = f'Какая буква на конце/в корне слова «{w}»? Проверка: {check}.'
        opts = [letter, 'п', 'т', 'к']
        opts = list(dict.fromkeys(opts))
        while len(opts) < 4:
            opts.append('с')
        tasks.append(build_task(q, '🐱 Котёнок проверяет парную согласную.', opts, letter, f'«{w}» ← {check}: пишем «{letter}».', diff, w.upper(), 'Парные согласные', tb_qs))
    return tasks


def gen_synonyms_antonyms(topic_id, topic_name, tb_qs):
    ants = [
        ('весёлый', 'грустный'), ('большой', 'маленький'), ('быстрый', 'медленный'),
        ('добрый', 'злой'), ('горячий', 'холодный'), ('светлый', 'тёмный'),
        ('громкий', 'тихий'), ('высокий', 'низкий'), ('новый', 'старый'),
        ('чистый', 'грязный'), ('умный', 'глупый'), ('сильный', 'слабый'),
        ('день', 'ночь'), ('зима', 'лето'), ('утро', 'вечер'),
        ('вход', 'выход'), ('начало', 'конец'), ('правда', 'ложь'),
    ]
    syns = [
        ('смелый', 'храбрый'), ('печальный', 'грустный'), ('огромный', 'большой'),
        ('малыш', 'ребёнок'), ('дорога', 'путь'), ('учитель', 'педагог'),
        ('друг', 'товарищ'), ('работа', 'труд'), ('дом', 'жилище'),
    ]
    tasks = []
    for idx in range(50):
        if idx % 2 == 0:
            a, b = ants[idx // 2 % len(ants)]
            q = f'Антоним к слову «{a}»?'
            wrong = [x[1] for x in ants if x[1] != b][:3]
            opts = [b] + wrong
            random.shuffle(opts)
            tasks.append(build_task(q, '🐰 Зайчик ищет слово с противоположным смыслом.', opts, b, f'«{a}» — антоним «{b}».', 'easy', a.upper(), 'Антонимы', tb_qs))
        else:
            a, b = syns[idx // 2 % len(syns)]
            q = f'Синоним к слову «{a}»?'
            wrong = [x[1] for x in syns if x[1] != b][:3]
            opts = [b] + wrong
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Лисичка подбирает близкое по смыслу слово.', opts, b, f'«{a}» ≈ «{b}» (синонимы).', 'easy', a.upper(), 'Синонимы', tb_qs))
    return tasks


def gen_sentence_members(topic_id, topic_name, tb_qs):
    items = [
        ('Мальчик читает книгу.', 'Мальчик', 'подлежащее'),
        ('Девочка рисует дом.', 'Девочка', 'подлежащее'),
        ('Собака лает громко.', 'Собака', 'подлежащее'),
        ('Ветер шумит в лесу.', 'Ветер', 'подлежащее'),
        ('Ученики пишут диктант.', 'Ученики', 'подлежащее'),
        ('Кот спит на диване.', 'Кот', 'подлежащее'),
        ('Мама готовит суп.', 'готовит', 'сказуемое'),
        ('Птицы летят на юг.', 'летят', 'сказуемое'),
        ('Река течёт быстро.', 'течёт', 'сказуемое'),
        ('Дети играют во дворе.', 'играют', 'сказуемое'),
        ('Солнце светит ярко.', 'светит', 'сказуемое'),
        ('Учитель объясняет правило.', 'объясняет', 'сказуемое'),
    ]
    tasks = []
    for idx in range(50):
        sent, ans, role = items[idx % len(items)]
        words = [w.strip('.,!') for w in sent.split()]
        wrong = [w for w in words if w != ans][:3]
        while len(wrong) < 3:
            wrong.append('нет ответа')
        opts = [ans] + wrong
        random.shuffle(opts)
        q = f'В предложении «{sent}» найди {role}:'
        tasks.append(build_task(q, '🦉 Совушка разбирает предложение.', opts, ans, f'«{ans}» — это {role} в предложении.', 'medium', role.upper(), 'Члены предложения', tb_qs))
    return tasks


def gen_root_words(topic_id, topic_name, tb_qs):
    groups = [
        ('лес', ['лес', 'лесной', 'лесник', 'перелесок']),
        ('сад', ['сад', 'садовый', 'садовник', 'садик']),
        ('вод', ['вода', 'водный', 'подводный', 'водитель']),  # водитель wrong root sometimes - use воды
        ('вод', ['вода', 'водичка', 'водный', 'подводный']),
        ('дом', ['дом', 'домик', 'домашний', 'домёнок']),
        ('снег', ['снег', 'снежный', 'снежинка', 'снеговик']),
        ('уч', ['ученик', 'учитель', 'учить', 'учение']),
        ('друг', ['друг', 'дружный', 'дружба', 'подруга']),
    ]
    tasks = []
    for idx in range(50):
        root, words = groups[idx % len(groups)]
        if idx % 2 == 0:
            q = f'Какой общий корень в словах: {", ".join(words[:3])}?'
            opts = [root, words[0][-3:], 'нет корня', 'окончание']
            random.shuffle(opts)
            tasks.append(build_task(q, '🐻 Медвежонок ищет корень.', opts, root, f'Общий корень — «{root}».', 'easy', root.upper(), 'Корень слова', tb_qs))
        else:
            odd = 'машина'
            q = f'Какое слово НЕ родственное к «{words[0]}»?'
            opts = [odd, words[1], words[2], words[0]]
            random.shuffle(opts)
            tasks.append(build_task(q, '🦊 Найди «лишнее» слово.', opts, odd, f'«{odd}» не от корня «{root}».', 'medium', root.upper(), 'Родственные слова', tb_qs))
    return tasks


def _generate_base(topic_id, topic_name, tb_qs):
    t = topic_name.lower()
    if 'жи' in t and 'ши' in t:
        return gen_zhi_shi(topic_id, topic_name, tb_qs)
    if 'ча' in t and 'ща' in t:
        return gen_cha_scha(topic_id, topic_name, tb_qs)
    if 'чу' in t and 'щу' in t:
        return gen_chu_schu(topic_id, topic_name, tb_qs)
    if 'чк' in t or 'чн' in t:
        return gen_chk_chn(topic_id, topic_name, tb_qs)
    if 'безудар' in t:
        return gen_unstressed_root(topic_id, topic_name, tb_qs)
    if 'парн' in t or 'звонк' in t or 'глух' in t:
        return gen_paired_consonants(topic_id, topic_name, tb_qs)
    if 'синоним' in t or 'антоним' in t or 'лексик' in t or 'значен' in t:
        return gen_synonyms_antonyms(topic_id, topic_name, tb_qs)
    if 'подлежащ' in t or 'сказуем' in t or 'главн' in t or 'член' in t:
        return gen_sentence_members(topic_id, topic_name, tb_qs)
    if 'корень' in t or 'родствен' in t or 'состав' in t or 'однокорен' in t:
        return gen_root_words(topic_id, topic_name, tb_qs)
    if 'разделительн' in t or 'ъ' in t:
        return gen_soft_sign_split(topic_id, topic_name, tb_qs)
    if 'мягкий' in t or 'ь' in t:
        return gen_soft_sign_middle(topic_id, topic_name, tb_qs)
    if 'словарн' in t:
        return gen_vocab_words(topic_id, topic_name, tb_qs)
    if 'слог' in t or 'перенос' in t:
        return gen_hyphenation(topic_id, topic_name, tb_qs) if 'перенос' in t else gen_syllables_split(topic_id, topic_name, tb_qs)
    if 'ударен' in t:
        return gen_stress(topic_id, topic_name, tb_qs)
    if 'алфавит' in t:
        return gen_alphabet(topic_id, topic_name, tb_qs)
    if 'заглавн' in t:
        return gen_capital_letters(topic_id, topic_name, tb_qs)
    if 'предлож' in t or 'знак' in t:
        return gen_sentences_punctuation(topic_id, topic_name, tb_qs)
    if 'существ' in t or 'прилаг' in t or 'глагол' in t or 'предлог' in t or 'част' in t:
        return gen_parts_of_speech(topic_id, topic_name, tb_qs)
    if 'твёрд' in t or 'мягк' in t:
        return gen_hard_soft(topic_id, topic_name, tb_qs)
    if 'гласн' in t or 'согласн' in t or 'фонетик' in t or 'звук' in t:
        return gen_vowels_and_consonants(topic_id, topic_name, tb_qs)
    if 'текст' in t or 'реч' in t:
        return gen_sentences_punctuation(topic_id, topic_name, tb_qs)
    return gen_sounds_and_letters(topic_id, topic_name, tb_qs)


def generate_tasks_for_topic(topic_id, topic_name, tb_qs, count=100):
    base = _generate_base(topic_id, topic_name, tb_qs)
    return _pad_to_count(base, count, topic_name)
