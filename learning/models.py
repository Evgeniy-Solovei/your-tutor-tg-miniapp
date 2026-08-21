from django.db import models
from django.db.models import Q

from knowledge.models import ExamVariant, Task, Topic
from students.models import Student


class DailySession(models.Model):
    """Учебная сессия (ежедневка / тренировка / полный вариант)."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Не начата'
        IN_PROGRESS = 'in_progress', 'В процессе'
        COMPLETED = 'completed', 'Завершена'

    class Kind(models.TextChoices):
        DAILY = 'daily', 'Ежедневная'
        TRAIN = 'train', 'Тренировка'
        VARIANT = 'variant', 'Вариант из сборника'
        EXAM = 'exam', 'Симулятор ЦТ/ЦЭ'
        MISTAKES = 'mistakes', 'Ошибки'

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='daily_sessions',
        verbose_name='Ученик',
    )
    session_date = models.DateField(verbose_name='Дата сессии')
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.DAILY,
        verbose_name='Тип сессии',
        db_index=True,
    )
    exam_variant = models.ForeignKey(
        ExamVariant,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='sessions',
        verbose_name='Вариант сборника',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус',
    )
    tasks_total = models.PositiveSmallIntegerField(default=0, verbose_name='Всего заданий')
    tasks_completed = models.PositiveSmallIntegerField(default=0, verbose_name='Выполнено')
    xp_earned = models.PositiveIntegerField(default=0, verbose_name='XP за сессию')
    primary_score = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Первичный балл',
        help_text='Сумма первичных баллов за сессию (логика РИКЗ)',
    )
    max_primary = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Макс. первичный (за сессию)',
    )
    test_score = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Тестовый балл (оценка)',
        help_text='Перевод по шкале РИКЗ; для полной сессии ближе к ЦТ',
    )
    time_limit_seconds = models.PositiveIntegerField(
        default=10800,
        verbose_name='Лимит времени (сек)',
        help_text='180 минут для ЦТ/ЦЭ',
    )
    time_spent_seconds = models.PositiveIntegerField(
        default=0,
        verbose_name='Затраченное время (сек)',
    )
    completed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время сдачи бланка',
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создана')

    class Meta:
        verbose_name = 'Учебная сессия'
        verbose_name_plural = 'Учебные сессии'
        ordering = ['-session_date', '-created_at']
        constraints = [
            models.UniqueConstraint(
                fields=['student', 'session_date'],
                condition=Q(kind='daily'),
                name='uniq_daily_session_per_student_date',
            )
        ]

    def __str__(self):
        return f'{self.student.display_name} — {self.session_date} ({self.kind})'


class StudentVariantProgress(models.Model):
    """Прогресс ученика по полному варианту из сборника."""

    class Status(models.TextChoices):
        NOT_STARTED = 'not_started', 'Не начат'
        IN_PROGRESS = 'in_progress', 'В процессе'
        COMPLETED = 'completed', 'Пройден'

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='variant_progress',
        verbose_name='Ученик',
    )
    variant = models.ForeignKey(
        ExamVariant,
        on_delete=models.CASCADE,
        related_name='student_progress',
        verbose_name='Вариант',
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NOT_STARTED,
        verbose_name='Статус',
    )
    correct_count = models.PositiveSmallIntegerField(default=0, verbose_name='Верно')
    wrong_count = models.PositiveSmallIntegerField(default=0, verbose_name='Ошибки')
    score_percent = models.FloatField(default=0.0, verbose_name='% верных')
    started_at = models.DateTimeField(null=True, blank=True, verbose_name='Начат')
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name='Завершён')
    last_session = models.ForeignKey(
        DailySession,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='variant_progress_links',
        verbose_name='Последняя сессия',
    )

    class Meta:
        verbose_name = 'Прогресс по варианту'
        verbose_name_plural = 'Прогресс по вариантам'
        unique_together = [('student', 'variant')]
        ordering = ['variant__collection', 'variant__number']

    def __str__(self):
        return f'{self.student_id} / variant {self.variant_id}: {self.status}'


class SessionTask(models.Model):
    """Задание внутри ежедневной сессии."""

    class Purpose(models.TextChoices):
        WEAK_TOPIC = 'weak_topic', 'Слабая тема'
        REVIEW = 'review', 'Повторение'
        NEW = 'new', 'Новая тема'

    session = models.ForeignKey(
        DailySession,
        on_delete=models.CASCADE,
        related_name='session_tasks',
        verbose_name='Сессия',
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='session_tasks',
        verbose_name='Задание',
    )
    purpose = models.CharField(
        max_length=20,
        choices=Purpose.choices,
        default=Purpose.NEW,
        verbose_name='Назначение',
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    is_answered = models.BooleanField(default=False, verbose_name='Отвечено')

    class Meta:
        verbose_name = 'Задание сессии'
        verbose_name_plural = 'Задания сессии'
        ordering = ['order']
        unique_together = [('session', 'task')]

    def __str__(self):
        return f'Сессия {self.session_id}: задание {self.task_id}'


class TaskAttempt(models.Model):
    """Попытка ответа ученика."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Ученик',
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='attempts',
        verbose_name='Задание',
    )
    session_task = models.ForeignKey(
        SessionTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='attempts',
        verbose_name='Задание сессии',
    )
    answer_text = models.TextField(verbose_name='Ответ ученика')
    is_correct = models.BooleanField(verbose_name='Правильно')
    points_earned = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Первичные баллы',
    )
    max_points = models.PositiveSmallIntegerField(
        default=1,
        verbose_name='Макс. первичные за задание',
    )
    time_spent_seconds = models.PositiveIntegerField(default=0, verbose_name='Время (сек)')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата попытки')

    class Meta:
        verbose_name = 'Попытка ответа'
        verbose_name_plural = 'Попытки ответов'
        ordering = ['-created_at']

    def __str__(self):
        status = '✓' if self.is_correct else '✗'
        return f'{status} {self.student.display_name} — задание {self.task_id}'


class TopicMastery(models.Model):
    """Статистика освоения темы учеником."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='topic_masteries',
        verbose_name='Ученик',
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='masteries',
        verbose_name='Тема',
    )
    correct_count = models.PositiveIntegerField(default=0, verbose_name='Правильных')
    wrong_count = models.PositiveIntegerField(default=0, verbose_name='Неправильных')
    mastery_score = models.FloatField(default=0.0, verbose_name='Уровень освоения (0–1)')
    last_attempt_at = models.DateTimeField(null=True, blank=True, verbose_name='Последняя попытка')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Освоение темы'
        verbose_name_plural = 'Освоение тем'
        unique_together = [('student', 'topic')]

    def __str__(self):
        return f'{self.student.display_name} — {self.topic.name}: {self.mastery_score:.0%}'

    def recalculate_score(self):
        total = self.correct_count + self.wrong_count
        self.mastery_score = self.correct_count / total if total else 0.0


class AIExplanationLog(models.Model):
    """Лог запросов ИИ-разбора ошибок."""

    attempt = models.ForeignKey(
        TaskAttempt,
        on_delete=models.CASCADE,
        related_name='ai_explanations',
        verbose_name='Попытка',
    )
    prompt_context = models.TextField(verbose_name='Контекст для ИИ')
    ai_response = models.TextField(verbose_name='Ответ ИИ')
    model_name = models.CharField(max_length=100, blank=True, verbose_name='Модель ИИ')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    class Meta:
        verbose_name = 'ИИ-разбор ошибки'
        verbose_name_plural = 'ИИ-разборы ошибок'
        ordering = ['-created_at']

    def __str__(self):
        return f'ИИ-разбор попытки #{self.attempt_id}'


class WeeklyLeague(models.Model):
    """Недельная / Месячная лига для рейтингов и турниров с призами."""

    class PeriodType(models.TextChoices):
        WEEK = 'week', 'Недельная лига'
        MONTH = 'month', 'Месячный турнир'

    title = models.CharField(
        max_length=200,
        default='Турнир',
        verbose_name='Название акции/турнира',
    )
    period_type = models.CharField(
        max_length=20,
        choices=PeriodType.choices,
        default=PeriodType.WEEK,
        verbose_name='Тип периода',
    )
    week_start = models.DateField(verbose_name='Начало периода')
    week_end = models.DateField(verbose_name='Конец периода')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    prize_first_place = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Приз за 1 место',
    )
    prize_second_place = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Приз за 2 место',
    )
    prize_third_place = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Приз за 3 место',
    )
    prizes_text = models.TextField(
        blank=True,
        verbose_name='Дополнительное описание призов',
    )

    class Meta:
        verbose_name = 'Лига / Турнир'
        verbose_name_plural = 'Лиги и Турниры'
        ordering = ['-week_start']

    def __str__(self):
        return f'{self.title} ({self.week_start} — {self.week_end})'


class LeagueEntry(models.Model):
    """Участник недельной / месячной лиги."""

    league = models.ForeignKey(
        WeeklyLeague,
        on_delete=models.CASCADE,
        related_name='entries',
        verbose_name='Лига',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='league_entries',
        verbose_name='Ученик',
    )
    weekly_xp = models.PositiveIntegerField(default=0, verbose_name='XP за период')
    test_score = models.PositiveIntegerField(default=0, verbose_name='Тестовый балл')
    primary_score = models.PositiveIntegerField(default=0, verbose_name='Первичный балл')
    rank = models.PositiveIntegerField(null=True, blank=True, verbose_name='Место')

    class Meta:
        verbose_name = 'Участник лиги'
        verbose_name_plural = 'Участники лиги'
        unique_together = [('league', 'student')]
        ordering = ['rank', '-test_score', '-primary_score', '-weekly_xp']

    def __str__(self):
        return f'{self.student.display_name} — {self.league.title} (балл: {self.test_score}, xp: {self.weekly_xp})'
