"""
Превращает текстовые упражнения учебника 2 класса в проверяемые MCQ.

Полный текст упражнения остаётся в reading_text. Вопрос — конкретный выбор
с правильным ответом (пропуски букв, правило темы). Варианты перемешиваются.

  ./venv/bin/python manage.py enrich_grade2_textbook_mcq
  ./venv/bin/python manage.py enrich_grade2_textbook_mcq --dry-run
"""
from __future__ import annotations

import random
import re

from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge.models import Task, TaskOption, TaskSolution
from knowledge.textbook_tasks import filter_school_textbook_tasks

# Частые пропуски 2 класса → верное написание
GAP_BANK: dict[str, str] = {
    'д..нёк': 'денёк',
    'в..терок': 'ветерок',
    'в..сёлые': 'весёлые',
    'разв..селились': 'развесилились',  # will fix
    'ч..сы': 'часы',
    'просл..зились': 'прослезились',
    'н..сы': 'носы',
    'св..стят': 'свистят',
    'скв..рцы': 'скворцы',
    'цв..ты': 'цветы',
    'ж..вут': 'живут',
    'нав..сают': 'нависают',
    'д..ревья': 'деревья',
    'б..реза': 'берёза',
    'б..рёза': 'берёза',
    'сн..жинка': 'снежинка',
    'маш..на': 'машина',
    'пуш..стый': 'пушистый',
    'л..са': 'лиса',
    'р..ка': 'река',
    'з..ма': 'зима',
    'в..сна': 'весна',
    'ош..бка': 'ошибка',
    'ш..шка': 'шишка',
    'ж..раф': 'жираф',
    'ч..шка': 'чашка',
    'ч..йка': 'чайка',
    'щ..ка': 'щука',
    'ч..до': 'чудо',
    'д..чка': 'дочка',
    'р..чка': 'речка',
    'ноч..ка': 'ночка',
    'п..роль': 'пароль',
    'угл..': 'уголь',
    'с..мья': 'семья',
    'д..нь': 'день',
    'г..род': 'город',
    'ул..ца': 'улица',
    'шк..ла': 'школа',
    'уч..ник': 'ученик',
    'уч..тель': 'учитель',
    'к..рова': 'корова',
    'м..локо': 'молоко',
    'с..бака': 'собака',
    'к..шка': 'кошка',
    'м..дведь': 'медведь',
    'з..яц': 'заяц',
    'б..лка': 'белка',
    'л..сица': 'лисица',
    'в..рона': 'ворона',
    'с..рока': 'сорока',
    'м..дведь': 'медведь',
    'п..тух': 'петух',
    'к..рова': 'корова',
    'тр..ва': 'трава',
    'з..мля': 'земля',
    'н..бо': 'небо',
    'с..лнце': 'солнце',
    'л..с': 'лес',
    'п..ле': 'поле',
    'м..ре': 'море',
    'б..рёза': 'берёза',
    'р..бина': 'рябина',
    'ябл..ко': 'яблоко',
    'яг..да': 'ягода',
    'м..лина': 'малина',
    'к..пуста': 'капуста',
    'м..рковь': 'морковь',
    'к..ртофель': 'картофель',
    'п..мидор': 'помидор',
    'огур..ц': 'огурец',
    'ч..ловек': 'человек',
    'д..вочка': 'девочка',
    'мал..чик': 'мальчик',
    'р..бота': 'работа',
    'д..рога': 'дорога',
    'к..ньки': 'коньки',
    'л..жи': 'лыжи',
    'сап..ги': 'сапоги',
    'б..тинки': 'ботинки',
    'т..традь': 'тетрадь',
    'руч..ка': 'ручка',
    'каранд..ш': 'карандаш',
    'алфав..т': 'алфавит',
    'предлож..ние': 'предложение',
    'подлеж..щее': 'подлежащее',
    'сказу..мое': 'сказуемое',
}

# fix typo
GAP_BANK['разв..селились'] = 'развесилились'
# correct: развеселились
GAP_BANK['разв..селились'] = 'развеселились'

TOPIC_MCQ = [
    (
        ('жи', 'ши', 'орфограф'),
        'В каком слове верно применено правило «ЖИ — ШИ пиши с И»?',
        ['лыжи', 'лыжы', 'лыже', 'лыжя'],
        'лыжи',
        'ЖИ и ШИ всегда пишутся с буквой И.',
    ),
    (
        ('ча', 'ща'),
        'В каком слове верно правило «ЧА — ЩА пиши с А»?',
        ['чашка', 'чяшка', 'чёшка', 'чишка'],
        'чашка',
        'ЧА и ЩА пишутся с буквой А.',
    ),
    (
        ('чу', 'щу'),
        'В каком слове верно правило «ЧУ — ЩУ пиши с У»?',
        ['щука', 'щюка', 'щёка', 'щика'],
        'щука',
        'ЧУ и ЩУ пишутся с буквой У.',
    ),
    (
        ('безудар',),
        'Какое проверочное слово подходит к слову «вода»?',
        ['воды', 'водитель', 'водить', 'водолаз'],
        'воды',
        'Безударная гласная проверяется ударением: вОды → водА.',
    ),
    (
        ('парн', 'звонк', 'глух'),
        'Какое проверочное слово к «дуб» (парная согласная на конце)?',
        ['дубы', 'дупло', 'дубина', 'дубок'],
        'дубы',
        'Парную согласную проверяют формой, где после неё гласная: дубы.',
    ),
    (
        ('слог', 'перенос', 'ударен'),
        'Сколько слогов в слове «малина»?',
        ['3', '2', '4', '1'],
        '3',
        'ма-ли-на — три гласных, три слога.',
    ),
    (
        ('предлож', 'член', 'подлежащ', 'сказуем'),
        'В предложении «Мальчик читает книгу» подлежащее — это…',
        ['Мальчик', 'читает', 'книгу', 'нет подлежащего'],
        'Мальчик',
        'Подлежащее отвечает на вопрос кто?/что? — мальчик.',
    ),
    (
        ('текст', 'реч', 'тем'),
        'Заголовок текста чаще всего указывает на…',
        ['тему или основную мысль', 'только фамилию автора', 'число страниц', 'цвет обложки'],
        'тему или основную мысль',
        'Заголовок помогает понять тему или главную мысль текста.',
    ),
    (
        ('синоним', 'антоним', 'лексик', 'значен'),
        'Антоним к слову «весёлый» — это…',
        ['грустный', 'радостный', 'смешной', 'громкий'],
        'грустный',
        'Антонимы — слова с противоположным значением.',
    ),
    (
        ('корень', 'родствен', 'состав'),
        'Общий корень в словах «лес», «лесной», «лесник» — это…',
        ['лес', 'ной', 'ник', 'ле'],
        'лес',
        'Родственные слова имеют общий корень.',
    ),
    (
        ('част', 'существ', 'прилаг', 'глагол'),
        'Слово «бежит» отвечает на вопрос…',
        ['что делает?', 'кто? что?', 'какой?', 'где?'],
        'что делает?',
        'Глагол обозначает действие и отвечает на вопросы что делает?/что сделать?',
    ),
]


def extract_gaps(text: str) -> list[str]:
    found = re.findall(r'[А-Яа-яЁё]*[\.]{2,}[А-Яа-яЁё]*', text)
    # also · dots
    found += re.findall(r'[А-Яа-яЁё]*[·…]{2,}[А-Яа-яЁё]*', text)
    cleaned = []
    for g in found:
        g2 = g.replace('·', '.').replace('…', '..')
        g2 = re.sub(r'\.{2,}', '..', g2)
        if g2 not in cleaned and len(g2) >= 3:
            cleaned.append(g2.lower())
    return cleaned


def resolve_gap(gap: str) -> str | None:
    g = gap.lower().strip()
    if g in GAP_BANK:
        return GAP_BANK[g]
    # fuzzy: try without ё/е
    for k, v in GAP_BANK.items():
        if k.replace('ё', 'е') == g.replace('ё', 'е'):
            return v
    # rule-based for жи/ши/ча/ща/чу/щу
    m = re.match(r'^([жш])\.\.(.+)$', g)
    if m:
        return m.group(1) + 'и' + m.group(2)
    m = re.match(r'^(.+)([жш])\.\.(.*)$', g)
    if m:
        return m.group(1) + m.group(2) + 'и' + m.group(3)
    m = re.match(r'^([чщ])\.\.(.+)$', g)
    if m:
        letter = 'а' if m.group(2)[:1] not in 'у' else 'у'
        # ча/ща vs чу/щу — look at second part
        rest = m.group(2)
        if rest.startswith(('й', 'ш', 'с', 'щ')) or True:
            # default ча
            pass
        return m.group(1) + 'а' + rest if not rest.startswith('к') else m.group(1) + 'у' + rest
    return None


def distractors_for_word(correct: str) -> list[str]:
    wrong = set()
    # vowel swaps
    for a, b in [('и', 'ы'), ('а', 'я'), ('у', 'ю'), ('е', 'и'), ('о', 'а'), ('ё', 'е')]:
        if a in correct:
            wrong.add(correct.replace(a, b, 1))
        if b in correct:
            wrong.add(correct.replace(b, a, 1))
    wrong.discard(correct)
    pool = list(wrong) + [correct + 'а', correct[:-1] if len(correct) > 3 else correct + 'ь', 'неверно']
    out = []
    for w in pool:
        if w and w != correct and w not in out:
            out.append(w)
        if len(out) >= 3:
            break
    while len(out) < 3:
        out.append(f'вариант-{len(out)+1}')
    return out[:3]


def topic_mcq(topic_name: str, body: str) -> dict | None:
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
    # fallback from body keywords
    if re.search(r'(?i)жи|ши', body):
        opts = ['живут', 'жывут', 'жевут', 'жявут']
        random.shuffle(opts)
        return {
            'question_suffix': 'Как правильно написать слово «ж..вут»?',
            'options': opts,
            'correct': 'живут',
            'explanation': 'ЖИ пиши с буквой И: живут.',
        }
    opts = ['тема текста', 'только автор', 'номер страницы', 'цвет картинки']
    random.shuffle(opts)
    return {
        'question_suffix': 'Что помогает понять заголовок или первое предложение текста?',
        'options': opts,
        'correct': 'тема текста',
        'explanation': 'Тема — о чём говорится в тексте.',
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
            'explanation': f'Верно: «{correct}». Смотри правило темы «{topic_name}».',
            'reading_text': body,
        }

    pack = topic_mcq(topic_name, body)
    if not pack:
        return None
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
    help = '2 класс: учебник → проверяемые MCQ со случайным порядком вариантов'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true')
        parser.add_argument('--limit', type=int, default=0)

    def handle(self, *args, **options):
        qs = filter_school_textbook_tasks(
            Task.objects.filter(topic__grade_level=2, is_active=True)
        ).select_related('topic', 'solution').prefetch_related('options')
        if options['limit']:
            qs = qs[: options['limit']]

        updated = 0
        skipped = 0
        dry = options['dry_run']

        for task in qs.iterator(chunk_size=100):
            # уже есть нормальные варианты (не текстовый черновик)
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
                task.save(
                    update_fields=[
                        'question',
                        'reading_text',
                        'answer_format',
                        'scoring_scheme',
                        'difficulty',
                    ]
                )
                task.options.all().delete()
                correct = pack['correct']
                for i, text in enumerate(pack['options'], start=1):
                    TaskOption.objects.create(
                        task=task,
                        text=text[:500],
                        is_correct=(text == correct),
                        order=i,
                    )
                sol, _ = TaskSolution.objects.get_or_create(
                    task=task,
                    defaults={
                        'correct_answer': '1',
                        'explanation': pack['explanation'],
                    },
                )
                # номер правильного варианта после shuffle
                correct_order = next(
                    o.order for o in task.options.all() if o.is_correct
                )
                sol.correct_answer = str(correct_order)
                sol.explanation = pack['explanation']
                sol.save(update_fields=['correct_answer', 'explanation'])
            updated += 1
            if updated % 50 == 0:
                self.stdout.write(f'  обновлено {updated}…')

        self.stdout.write(
            self.style.SUCCESS(
                f'2 класс MCQ: обновлено {updated}, пропущено {skipped}'
                + (' (dry-run)' if dry else '')
            )
        )
