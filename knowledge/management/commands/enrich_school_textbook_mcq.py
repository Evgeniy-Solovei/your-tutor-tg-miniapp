"""
Учебник → проверяемые MCQ (русский язык, программа РБ).

Полный текст упражнения в reading_text. Вопрос с верным ответом.
Варианты перемешиваются. Контекст: Беларусь (Минск, Неман, Республика Беларусь).

  ./venv/bin/python manage.py enrich_school_textbook_mcq --grade 3
  ./venv/bin/python manage.py enrich_school_textbook_mcq --grade 2 --dry-run
"""
from __future__ import annotations

import random
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import Task, TaskOption, TaskSolution
from knowledge.textbook_tasks import filter_school_textbook_tasks

GAP_BANK: dict[str, str] = {
    'д..нёк': 'денёк', 'в..терок': 'ветерок', 'в..сёлые': 'весёлые',
    'разв..селились': 'развеселились', 'ч..сы': 'часы', 'просл..зились': 'прослезились',
    'н..сы': 'носы', 'св..стят': 'свистят', 'скв..рцы': 'скворцы', 'цв..ты': 'цветы',
    'ж..вут': 'живут', 'нав..сают': 'нависают', 'д..ревья': 'деревья', 'б..реза': 'берёза',
    'б..рёза': 'берёза', 'сн..жинка': 'снежинка', 'маш..на': 'машина', 'пуш..стый': 'пушистый',
    'л..са': 'лиса', 'р..ка': 'река', 'з..ма': 'зима', 'в..сна': 'весна', 'ош..бка': 'ошибка',
    'ш..шка': 'шишка', 'ж..раф': 'жираф', 'ч..шка': 'чашка', 'ч..йка': 'чайка', 'щ..ка': 'щука',
    'ч..до': 'чудо', 'д..чка': 'дочка', 'р..чка': 'речка', 'ноч..ка': 'ночка', 'с..мья': 'семья',
    'г..род': 'город', 'ул..ца': 'улица', 'шк..ла': 'школа', 'уч..ник': 'ученик',
    'уч..тель': 'учитель', 'к..рова': 'корова', 'м..локо': 'молоко', 'с..бака': 'собака',
    'к..шка': 'кошка', 'м..дведь': 'медведь', 'з..яц': 'заяц', 'б..лка': 'белка',
    'л..сица': 'лисица', 'в..рона': 'ворона', 'с..рока': 'сорока', 'п..тух': 'петух',
    'тр..ва': 'трава', 'з..мля': 'земля', 'н..бо': 'небо', 'с..лнце': 'солнце', 'л..с': 'лес',
    'п..ле': 'поле', 'м..ре': 'море', 'р..бина': 'рябина', 'ябл..ко': 'яблоко', 'яг..да': 'ягода',
    'м..лина': 'малина', 'к..пуста': 'капуста', 'м..рковь': 'морковь', 'к..ртофель': 'картофель',
    'п..мидор': 'помидор', 'огур..ц': 'огурец', 'ч..ловек': 'человек', 'д..вочка': 'девочка',
    'мал..чик': 'мальчик', 'р..бота': 'работа', 'д..рога': 'дорога', 'к..ньки': 'коньки',
    'л..жи': 'лыжи', 'сап..ги': 'сапоги', 'б..тинки': 'ботинки', 'т..традь': 'тетрадь',
    'руч..ка': 'ручка', 'каранд..ш': 'карандаш', 'алфав..т': 'алфавит',
    'предлож..ние': 'предложение', 'подлеж..щее': 'подлежащее', 'сказу..мое': 'сказуемое',
    'М..нск': 'Минск', 'м..нск': 'Минск', 'Бел..русь': 'Беларусь', 'бел..русь': 'Беларусь',
    'Н..ман': 'Неман', 'н..ман': 'Неман', 'В..лия': 'Вилия', 'в..лия': 'Вилия',
    'с..лнце': 'солнце', 'праз..ник': 'праздник', 'мес..ный': 'местный', 'лес..ной': 'лестной',
    'чу..ство': 'чувство', 'сер..це': 'сердце', 'со..нце': 'солнце', 'здра..ствуй': 'здравствуй',
    'извес..ный': 'известный', 'опас..ный': 'опасный', 'вкус..ный': 'вкусный',
    'клас..ный': 'классный', 'рус..кий': 'русский', 'белорус..кий': 'белорусский',
    '(в)ходить': 'входить', '(в)здание': 'в здание', '(на)писать': 'написать',
    '(по)дороге': 'по дороге', '(с)делать': 'сделать', '(без)шумный': 'бесшумный',
}

TOPIC_MCQ = [
    (
        ('жи', 'ши'),
        'В каком слове верно правило «ЖИ — ШИ пиши с И» (программа РБ)?',
        ['лыжи', 'лыжы', 'лыже', 'лыжя'],
        'лыжи',
        'ЖИ и ШИ всегда пишутся с буквой И.',
    ),
    (
        ('ча', 'ща'),
        'В каком слове верно «ЧА — ЩА пиши с А»?',
        ['чашка', 'чяшка', 'чёшка', 'чишка'],
        'чашка',
        'ЧА и ЩА пишутся с буквой А.',
    ),
    (
        ('чу', 'щу'),
        'В каком слове верно «ЧУ — ЩУ пиши с У»?',
        ['щука', 'щюка', 'щёка', 'щика'],
        'щука',
        'ЧУ и ЩУ пишутся с буквой У.',
    ),
    (
        ('безудар',),
        'Какое проверочное слово подходит к «вода»?',
        ['воды', 'водитель', 'водить', 'водолаз'],
        'воды',
        'Безударная гласная проверяется ударением: вОды → водА.',
    ),
    (
        ('парн', 'звонк', 'глух'),
        'Какое проверочное к слову «дуб»?',
        ['дубы', 'дупло', 'дубина', 'дубок'],
        'дубы',
        'Парную согласную проверяют формой с гласной после неё.',
    ),
    (
        ('непроизнос',),
        'В каком слове есть непроизносимая согласная?',
        ['солнце', 'стол', 'кот', 'дом'],
        'солнце',
        'В слове «солнце» звук [л] не произносится, но буква Л пишется.',
    ),
    (
        ('двойн',),
        'В каком слове пишутся двойные согласные?',
        ['класс', 'классный', 'класик', 'класний'],
        'класс',
        'В слове «класс» — две буквы С (программа начальной школы РБ).',
    ),
    (
        ('пристав',),
        'Где приставка, а не предлог?',
        ['входить', 'в дом', 'на столе', 'с другом'],
        'входить',
        'Приставка пишется слитно со словом: входить. Предлог — отдельно: в дом.',
    ),
    (
        ('корень', 'морфем', 'состав', 'суффикс', 'окончан', 'основ'),
        'Общий корень в словах «лес», «лесной», «лесник»?',
        ['лес', 'ной', 'ник', 'ле'],
        'лес',
        'Родственные слова имеют общий корень «лес».',
    ),
    (
        ('чередован', 'бегл'),
        'В каком ряду есть чередование звуков в корне?',
        ['друг — друзья', 'дом — домик', 'сад — садик', 'стол — столик'],
        'друг — друзья',
        'В корне друг/друж чередуются согласные г — ж.',
    ),
    (
        ('существ', 'падеж', 'род им'),
        'Какого рода слово «тетрадь»?',
        ['женский', 'мужской', 'средний', 'общего рода'],
        'женский',
        'Тетрадь — женский род (она, моя тетрадь).',
    ),
    (
        ('шипящ', 'ь после'),
        'Где нужен мягкий знак после шипящих?',
        ['ночь', 'врач', 'мяч', 'ключ'],
        'ночь',
        'У сущ. ж.р. 3 скл. после шипящих пишется Ь: ночь, рожь. У м.р. — нет: врач, мяч.',
    ),
    (
        ('прилаг',),
        'Какое слово — имя прилагательное?',
        ['белорусский', 'Беларусь', 'Минск', 'учиться'],
        'белорусский',
        'Прилагательное обозначает признак: белорусский (какой?) язык.',
    ),
    (
        ('местоимен',),
        'Какое слово — личное местоимение?',
        ['мы', 'Минск', 'школа', 'быстро'],
        'мы',
        'Личные местоимения: я, ты, он, она, оно, мы, вы, они.',
    ),
    (
        ('глагол', 'времен', 'частица не'),
        'В каком времени глагол «читали»?',
        ['прошедшее', 'настоящее', 'будущее', 'неопределённое'],
        'прошедшее',
        'Читали — прошедшее время (что делали?).',
    ),
    (
        ('подлежащ', 'сказуем', 'член', 'синтакс', 'однородн', 'второстепен'),
        'В предложении «Минск стоит на Свислочи» подлежащее — это…',
        ['Минск', 'стоит', 'на Свислочи', 'нет подлежащего'],
        'Минск',
        'Подлежащее отвечает на кто?/что? — Минск (столица Беларуси).',
    ),
    (
        ('текст', 'тип'),
        'Текст-повествование отвечает на вопрос…',
        ['что произошло?', 'какой предмет?', 'почему?', 'сколько?'],
        'что произошло?',
        'Повествование рассказывает о событиях (что произошло?).',
    ),
    (
        ('синоним', 'антоним', 'лексик'),
        'Антоним к слову «весёлый»?',
        ['грустный', 'радостный', 'смешной', 'громкий'],
        'грустный',
        'Антонимы — слова с противоположным значением.',
    ),
    (
        ('беларус', 'родин', 'минск', 'географ'),
        'Столица Республики Беларусь — это…',
        ['Минск', 'Гродно', 'Брест', 'Витебск'],
        'Минск',
        'Столица Беларуси — город Минск.',
    ),
    (
        ('причасти',),
        'Причастие совмещает признаки…',
        ['глагола и прилагательного', 'только глагола', 'существительного', 'наречия'],
        'глагола и прилагательного',
        'Причастие — признаки глагола и прилагательного.',
    ),
    (
        ('деепричасти',),
        'Деепричастие обозначает…',
        ['добавочное действие', 'признак предмета', 'количество', 'лицо'],
        'добавочное действие',
        'Деепричастие обозначает добавочное действие.',
    ),
    (
        ('числительн',),
        'Какое слово — количественное числительное?',
        ['семь', 'седьмой', 'семёрка', 'семьёй'],
        'семь',
        '«Семь» — количественное числительное.',
    ),
    (
        ('нареч',),
        'Наречие чаще отвечает на вопрос…',
        ['как? где? когда?', 'кто? что?', 'какой?', 'чей?'],
        'как? где? когда?',
        'Наречие: как? где? когда?',
    ),
    (
        ('словосочетан', 'виды связи'),
        'Виды связи в словосочетании — это…',
        ['согласование, управление, примыкание', 'только союз', 'только интонация', 'нет связи'],
        'согласование, управление, примыкание',
        'Согласование, управление, примыкание.',
    ),
    (
        ('вводн',),
        'Вводные слова на письме…',
        ['выделяются запятыми', 'не выделяются', 'всегда в кавычках', 'пишутся слитно'],
        'выделяются запятыми',
        'Вводные слова выделяются запятыми.',
    ),
]


def extract_gaps(text: str) -> list[str]:
    found = re.findall(r'[А-Яа-яЁё()]*[\.]{2,}[А-Яа-яЁё]*', text)
    found += re.findall(r'[А-Яа-яЁё()]*[·…]{2,}[А-Яа-яЁё]*', text)
    found += re.findall(r'\([а-яё]+\)[а-яё]+', text.lower())
    cleaned = []
    for g in found:
        g2 = g.replace('·', '.').replace('…', '..')
        g2 = re.sub(r'\.{2,}', '..', g2)
        if g2 not in cleaned and len(g2) >= 3:
            cleaned.append(g2.lower() if not g2.startswith('(') else g2)
    return cleaned


def resolve_gap(gap: str) -> str | None:
    g = gap.strip()
    gl = g.lower()
    if g in GAP_BANK:
        return GAP_BANK[g]
    if gl in GAP_BANK:
        return GAP_BANK[gl]
    for k, v in GAP_BANK.items():
        if k.replace('ё', 'е') == gl.replace('ё', 'е'):
            return v
    m = re.match(r'^([жш])\.\.(.+)$', gl)
    if m:
        return m.group(1) + 'и' + m.group(2)
    m = re.match(r'^(.+)([жш])\.\.(.*)$', gl)
    if m:
        return m.group(1) + m.group(2) + 'и' + m.group(3)
    m = re.match(r'^([чщ])\.\.(.+)$', gl)
    if m:
        rest = m.group(2)
        vowel = 'у' if rest.startswith(('к', 'в', 'ж', 'т', 'д')) and len(rest) <= 3 else 'а'
        if rest.startswith(('й', 'ш', 'с')):
            vowel = 'а'
        if rest in ('ка',) or rest.startswith('к') and 'у' in 'щука':
            vowel = 'у' if m.group(1) == 'щ' and rest.startswith('к') else vowel
        return m.group(1) + vowel + rest
    return None


def distractors_for_word(correct: str) -> list[str]:
    wrong = set()
    for a, b in [('и', 'ы'), ('а', 'я'), ('у', 'ю'), ('е', 'и'), ('о', 'а'), ('ё', 'е'), ('сс', 'с'), ('с', 'сс')]:
        if a in correct:
            wrong.add(correct.replace(a, b, 1))
        if b in correct:
            wrong.add(correct.replace(b, a, 1))
    wrong.discard(correct)
    pool = list(wrong) + [correct + 'а', 'неверно', correct.replace('ь', '') if 'ь' in correct else correct + 'ь']
    out = []
    for w in pool:
        if w and w != correct and w not in out:
            out.append(w)
        if len(out) >= 3:
            break
    while len(out) < 3:
        out.append(f'вариант-{len(out)+1}')
    return out[:3]


def topic_mcq(topic_name: str, body: str) -> dict:
    t = (topic_name or '').lower()
    for keys, q, opts, correct, expl in TOPIC_MCQ:
        if any(k in t for k in keys):
            options = list(opts)
            random.shuffle(options)
            return {
                'question_suffix': q,
                'options': options,
                'correct': correct,
                'explanation': expl,
            }
    if re.search(r'(?i)беларус|минск|неман|родин', body):
        opts = ['Минск', 'Москва', 'Киев', 'Варшава']
        random.shuffle(opts)
        return {
            'question_suffix': 'Столица Республики Беларусь?',
            'options': opts,
            'correct': 'Минск',
            'explanation': 'Столица Беларуси — Минск (учебник РБ).',
        }
    if re.search(r'(?i)жи|ши', body):
        opts = ['живут', 'жывут', 'жевут', 'жявут']
        random.shuffle(opts)
        return {
            'question_suffix': 'Как правильно: «ж..вут»?',
            'options': opts,
            'correct': 'живут',
            'explanation': 'ЖИ пиши с И: живут.',
        }
    opts = ['тема текста', 'только автор', 'номер страницы', 'цвет картинки']
    random.shuffle(opts)
    return {
        'question_suffix': 'Что помогает понять заголовок или начало текста?',
        'options': opts,
        'correct': 'тема текста',
        'explanation': 'Тема — о чём говорится в тексте (программа рус. яз. РБ).',
    }


def build_mcq_for_task(task: Task) -> dict | None:
    body = task.reading_text or task.question or ''
    topic_name = task.topic.name if task.topic_id else ''
    gaps = extract_gaps(body)
    for gap in gaps:
        correct = resolve_gap(gap)
        if not correct:
            continue
        opts = [correct] + distractors_for_word(correct)
        random.shuffle(opts)
        display_gap = gap.replace('..', '…')
        return {
            'question': (
                f'{task.question.split(chr(10))[0]}\n\n'
                f'Текст упражнения:\n{body[:500]}{"…" if len(body) > 500 else ""}\n\n'
                f'❓ Как правильно написать «{display_gap}»?'
            ),
            'options': opts,
            'correct': correct,
            'explanation': f'Верно: «{correct}». Тема «{topic_name}» (русский язык, РБ).',
            'reading_text': body,
        }

    pack = topic_mcq(topic_name, body)
    return {
        'question': (
            f'{task.question.split(chr(10))[0]}\n\n'
            f'Текст упражнения:\n{body[:500]}{"…" if len(body) > 500 else ""}\n\n'
            f'❓ {pack["question_suffix"]}'
        ),
        'options': pack['options'],
        'correct': pack['correct'],
        'explanation': pack['explanation'],
        'reading_text': body,
    }


class Command(BaseCommand):
    help = 'Учебник класса → проверяемые MCQ (программа РБ), варианты в случайном порядке'

    def add_arguments(self, parser):
        parser.add_argument('--grade', type=int, required=True)
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, **options):
        grade = options['grade']
        qs = filter_school_textbook_tasks(
            Task.objects.filter(topic__grade_level=grade, is_active=True)
        ).select_related('topic', 'solution').prefetch_related('options')
        if options['limit']:
            qs = qs[: options['limit']]

        updated = skipped = 0
        dry = options['dry_run']
        self.stdout.write(self.style.NOTICE(f'{grade} класс: обогащение учебника → MCQ (РБ)'))

        for task in qs.iterator(chunk_size=100):
            existing = list(task.options.all())
            if (
                task.answer_format == Task.AnswerFormat.SINGLE_CHOICE
                and len(existing) >= 2
                and any(o.is_correct for o in existing)
                and not any(o.text.startswith('Задание выполнено') for o in existing)
            ):
                skipped += 1
                continue

            pack = build_mcq_for_task(task)
            if not pack:
                skipped += 1
                continue
            if dry:
                updated += 1
                continue

            with transaction.atomic():
                task.question = pack['question']
                task.reading_text = pack['reading_text']
                task.answer_format = Task.AnswerFormat.SINGLE_CHOICE
                task.scoring_scheme = Task.ScoringScheme.BINARY_1
                task.difficulty = Task.Difficulty.MEDIUM
                task.save(update_fields=[
                    'question', 'reading_text', 'answer_format', 'scoring_scheme', 'difficulty',
                ])
                task.options.all().delete()
                correct = pack['correct']
                for i, text in enumerate(pack['options'], start=1):
                    TaskOption.objects.create(
                        task=task, text=text[:500], is_correct=(text == correct), order=i,
                    )
                sol, _ = TaskSolution.objects.get_or_create(
                    task=task,
                    defaults={'correct_answer': '1', 'explanation': pack['explanation']},
                )
                correct_order = next(o.order for o in task.options.all() if o.is_correct)
                sol.correct_answer = str(correct_order)
                sol.explanation = pack['explanation']
                sol.save(update_fields=['correct_answer', 'explanation'])
            updated += 1
            if updated % 50 == 0:
                self.stdout.write(f'  обновлено {updated}…')

        self.stdout.write(self.style.SUCCESS(
            f'{grade} класс MCQ: обновлено {updated}, пропущено {skipped}'
            + (' (dry-run)' if dry else '')
        ))
