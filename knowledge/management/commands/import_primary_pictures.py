"""
Картинные задания для 1–4 класса.

  python manage.py import_primary_pictures
  python manage.py import_primary_pictures --clear
"""
from __future__ import annotations

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from knowledge import primary_art as art
from knowledge.models import (
    ExamTrack,
    Subject,
    Task,
    TaskOption,
    TaskSolution,
    Topic,
)

SOURCE = 'Картинки 1–4 класс'


def _topic(grade: int, *hints: str) -> Topic | None:
    qs = Topic.objects.filter(grade_level=grade, is_active=True)
    for hint in hints:
        t = qs.filter(name__icontains=hint).first()
        if t:
            return t
    return qs.first()


def _attach(task: Task, path) -> None:
    with open(path, 'rb') as fh:
        task.image.save(path.name, File(fh), save=True)


def _attach_opt(opt: TaskOption, path) -> None:
    with open(path, 'rb') as fh:
        opt.image.save(path.name, File(fh), save=True)


def _image_missing(field_file) -> bool:
    if not field_file or not field_file.name:
        return True
    try:
        return not field_file.storage.exists(field_file.name)
    except OSError:
        return True


def _mc(topic: Topic, question: str, options: list[str], explanation: str, image_path=None, option_images=None):
    existing = (
        Task.objects.filter(topic=topic, source=SOURCE, question=question)
        .prefetch_related('options')
        .first()
    )
    if existing:
        if image_path and _image_missing(existing.image):
            _attach(existing, image_path)
        if option_images:
            for opt, option_path in zip(existing.options.all(), option_images):
                if option_path and _image_missing(opt.image):
                    _attach_opt(opt, option_path)
        return False
    task = Task.objects.create(
        topic=topic,
        question=question,
        answer_format=Task.AnswerFormat.SINGLE_CHOICE,
        scoring_scheme=Task.ScoringScheme.BINARY_1,
        difficulty=Task.Difficulty.EASY,
        source=SOURCE,
        is_active=True,
    )
    if image_path:
        _attach(task, image_path)
    for i, text in enumerate(options, start=1):
        opt = TaskOption.objects.create(task=task, text=text, is_correct=(i == 1), order=i)
        if option_images and i - 1 < len(option_images) and option_images[i - 1]:
            _attach_opt(opt, option_images[i - 1])
    TaskSolution.objects.create(task=task, correct_answer='1', explanation=explanation)
    return True


class Command(BaseCommand):
    help = 'Импорт картинных заданий для 1–4 класса'

    def add_arguments(self, parser):
        parser.add_argument('--clear', action='store_true')

    def handle(self, *args, **options):
        # темы должны уже быть от import_school_grades
        if not Topic.objects.filter(grade_level__lte=4).exists():
            self.stderr.write('Сначала: python manage.py import_school_grades')
            return

        subject = Subject.objects.filter(slug='russian').first()
        if subject:
            ExamTrack.objects.filter(
                subject=subject, track_type=ExamTrack.TrackType.GENERAL
            ).update(grade_from=1, grade_to=11)

        with transaction.atomic():
            if options['clear']:
                n, _ = Task.objects.filter(source=SOURCE).delete()
                self.stdout.write(f'Удалено: {n}')

            self.stdout.write('Рисую картинки…')
            letter_a = art.letter_card('А', 'гласный звук')
            letter_o = art.letter_card('О', 'гласный звук')
            letter_m = art.letter_card('М', 'согласный')
            mama = art.syllables_mama()
            balls2 = art.count_objects('ball', 2)
            balls3 = art.count_objects('ball', 3)
            fish2 = art.count_objects('fish', 2)
            apples3 = art.count_objects('apple', 3)
            cat = art.animal('cat')
            dog = art.animal('dog')
            fish = art.animal('fish')
            house = art.animal('house')
            scheme_mama = art.word_scheme('мама', 'ма-ма')
            soft = art.soft_sign_pair()
            root = art.root_words()
            caps = art.sentence_capitals()

            created = 0
            specs = [
                # --- 1 класс ---
                (1, ['Гласные'], 'Какая буква на картинке?', ['А', 'О', 'У', 'Ы'], 'Это буква А.', letter_a, None),
                (1, ['Гласные'], 'Это гласный звук?', ['Да, О — гласный', 'Нет, согласный', 'Это цифра', 'Это слог'], 'О — гласный.', letter_o, None),
                (1, ['Слоги'], 'Сколько слогов в слове «мама»?', ['2', '1', '3', '4'], 'ма-ма — два слога.', mama, None),
                (1, ['Слоги'], 'Посмотри на мячики. Сколько их?', ['2', '1', '3', '4'], 'На картинке 2 мяча.', balls2, None),
                (1, ['Заглавная'], 'Как правильно написать?', ['Маша читает книгу.', 'маша читает книгу', 'маша Читает книгу', 'Маша читает книгу'], 'Имя с заглавной, в конце точка.', caps, None),
                (1, ['Точка'], 'Сколько рыбок на картинке?', ['2', '1', '3', '5'], 'Две рыбки.', fish2, None),
                # --- 2 класс ---
                (2, ['Алфавит', 'Согласные'], 'Какая буква на карточке?', ['М', 'А', 'О', 'У'], 'Это согласная М.', letter_m, None),
                (2, ['Корень'], 'Общий корень в словах на картинке?', ['лес', 'ной', 'ок', 'ле'], 'Корень — лес.', root, None),
                (2, ['Слоги', 'Корень'], 'Как делится слово «мама»?', ['ма-ма', 'м-ама', 'мам-а', 'мама'], 'ма-ма.', scheme_mama, None),
                (2, ['Главные'], 'Кто нарисован?', ['кот', 'пёс', 'рыба', 'дом'], 'Это кот.', cat, None),
                (2, ['Ь'], 'Где есть мягкий знак?', ['уголь', 'угол', 'оба одинаковы', 'нигде'], 'В слове «уголь» есть ь.', soft, None),
                (2, ['Предложение'], 'Сколько яблок?', ['3', '2', '1', '4'], 'Три яблока.', apples3, None),
                # --- 3 класс ---
                (3, ['Приставка', 'Корень'], 'Слова лес / лесной / лесок — это…', ['однокоренные', 'синонимы', 'антонимы', 'омонимы'], 'Общий корень лес.', root, None),
                (3, ['существительное'], 'Что обозначает картинка? (кто? что?)', ['дом', 'бежать', 'красный', 'быстро'], 'Дом — существительное.', house, None),
                (3, ['Подлежащее'], 'Кто на картинке может быть подлежащим в предложении «… плывёт»?', ['рыба', 'дом', 'мяч', 'лес'], 'Рыба плывёт.', fish, None),
                (3, ['Глагол', 'Части'], 'Сколько мячей?', ['3', '2', '1', '4'], 'Три мяча.', balls3, None),
                # --- 4 класс ---
                (4, ['Безударные'], 'Кто нарисован? Подбери проверочное к слову «котёнок»…', ['ко́тик', 'кататься', 'который', 'котлета'], 'ко́тик проверяет о.', cat, None),
                (4, ['Однородные'], 'Кого можно перечислить через запятую?', ['кот и пёс', 'только дом', 'только букву А', 'схему'], 'Однородные: кот, пёс…', dog, None),
                (4, ['Парные'], 'Сколько предметов на картинке?', ['3', '1', '2', '5'], 'Три яблока.', apples3, None),
                (4, ['Местоимение'], 'Замени существительное: «Кот спит» → «… спит»', ['Он', 'Она', 'Оно', 'Они'], 'Кот → он.', cat, None),
            ]

            # задание с картинками в вариантах
            t1 = _topic(1, 'Слово', 'предложен')
            picture_options = [
                ('кот', cat, True),
                ('пёс', dog, False),
                ('рыба', fish, False),
                ('дом', house, False),
            ]
            picture_task = (
                Task.objects.filter(
                    topic=t1,
                    source=SOURCE,
                    question__startswith='Выбери картинку',
                )
                .prefetch_related('options')
                .first()
                if t1
                else None
            )
            if t1 and not picture_task:
                picture_task = Task.objects.create(
                    topic=t1,
                    question='Выбери картинку, где нарисован кот',
                    answer_format=Task.AnswerFormat.SINGLE_CHOICE,
                    scoring_scheme=Task.ScoringScheme.BINARY_1,
                    difficulty=Task.Difficulty.EASY,
                    source=SOURCE,
                    is_active=True,
                )
                for i, (label, path, ok) in enumerate(picture_options, start=1):
                    opt = TaskOption.objects.create(
                        task=picture_task,
                        text=label,
                        is_correct=ok,
                        order=i,
                    )
                    _attach_opt(opt, path)
                TaskSolution.objects.create(
                    task=picture_task,
                    correct_answer='1',
                    explanation='На первой картинке кот.',
                )
                created += 1
            elif picture_task:
                options_by_order = {o.order: o for o in picture_task.options.all()}
                for order, (_, path, _) in enumerate(picture_options, start=1):
                    opt = options_by_order.get(order)
                    if opt and _image_missing(opt.image):
                        _attach_opt(opt, path)

            for grade, hints, q, opts, expl, img, _ in specs:
                topic = _topic(grade, *hints)
                if not topic:
                    continue
                if _mc(topic, q, opts, expl, image_path=img):
                    created += 1

        total = Task.objects.filter(source=SOURCE).count()
        self.stdout.write(self.style.SUCCESS(
            f'Готово: новых {created}, всего картинных заданий: {total}'
        ))
