from django.db import models


class Subject(models.Model):
    """Предмет (русский язык, математика и т.д.)."""

    name = models.CharField(max_length=100, verbose_name='Название предмета')
    slug = models.SlugField(unique=True, verbose_name='Slug')
    description = models.TextField(blank=True, verbose_name='Описание')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Предмет'
        verbose_name_plural = 'Предметы'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class ExamTrack(models.Model):
    """Трек подготовки: ЦТ после 11, аттестат после 9 и т.д."""

    class TrackType(models.TextChoices):
        CT_11 = 'ct_11', 'ЦТ после 11 класса'
        CE_11 = 'ce_11', 'ЦЭ после 11 класса'
        ATTESTAT_9 = 'attestat_9', 'Аттестат после 9 класса'
        GENERAL = 'general', 'Общая подготовка'

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='exam_tracks',
        verbose_name='Предмет',
    )
    name = models.CharField(max_length=150, verbose_name='Название трека')
    track_type = models.CharField(
        max_length=20,
        choices=TrackType.choices,
        verbose_name='Тип экзамена',
    )
    grade_from = models.PositiveSmallIntegerField(default=1, verbose_name='Класс от')
    grade_to = models.PositiveSmallIntegerField(default=11, verbose_name='Класс до')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Экзаменационный трек'
        verbose_name_plural = 'Экзаменационные треки'
        ordering = ['subject', 'grade_from']

    def __str__(self):
        return f'{self.subject.name} — {self.name}'


class ContentVersion(models.Model):
    """Версия учебной программы / спецификации РИКЗ."""

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='content_versions',
        verbose_name='Предмет',
    )
    year = models.PositiveSmallIntegerField(verbose_name='Год')
    title = models.CharField(max_length=255, verbose_name='Название версии')
    source_url = models.URLField(blank=True, verbose_name='Ссылка на источник')
    is_current = models.BooleanField(default=False, verbose_name='Текущая версия')
    notes = models.TextField(blank=True, verbose_name='Примечания')

    class Meta:
        verbose_name = 'Версия контента'
        verbose_name_plural = 'Версии контента'
        ordering = ['-year', 'subject']

    def __str__(self):
        return f'{self.subject.name} {self.year}: {self.title}'


class Section(models.Model):
    """Раздел программы (например, «Синтаксис», «Алгебра»)."""

    exam_track = models.ForeignKey(
        ExamTrack,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name='Экзаменационный трек',
    )
    content_version = models.ForeignKey(
        ContentVersion,
        on_delete=models.CASCADE,
        related_name='sections',
        verbose_name='Версия контента',
    )
    name = models.CharField(max_length=200, verbose_name='Название раздела')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Раздел'
        verbose_name_plural = 'Разделы'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Topic(models.Model):
    """Тема внутри раздела."""

    section = models.ForeignKey(
        Section,
        on_delete=models.CASCADE,
        related_name='topics',
        verbose_name='Раздел',
    )
    name = models.CharField(max_length=200, verbose_name='Название темы')
    grade_level = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Класс',
        help_text='К какому классу относится тема.',
    )
    exam_weight = models.FloatField(
        default=1.0,
        verbose_name='Вес на экзамене',
        help_text='Чем выше — тем чаще попадает в подборку.',
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')
    is_active = models.BooleanField(default=True, verbose_name='Активна')

    class Meta:
        verbose_name = 'Тема'
        verbose_name_plural = 'Темы'
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class TopicSummary(models.Model):
    """Краткий конспект темы — контекст для ИИ при разборе ошибок."""

    topic = models.OneToOneField(
        Topic,
        on_delete=models.CASCADE,
        related_name='summary',
        verbose_name='Тема',
    )
    title = models.CharField(max_length=255, verbose_name='Заголовок')
    content = models.TextField(verbose_name='Конспект')
    key_points = models.TextField(blank=True, verbose_name='Ключевые правила')
    source_note = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Источник',
        help_text='Учебник, программа, спецификация РИКЗ.',
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Конспект темы'
        verbose_name_plural = 'Конспекты тем'

    def __str__(self):
        return self.title


class Textbook(models.Model):
    """Учебник для базы знаний."""

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='textbooks',
        verbose_name='Предмет',
    )
    title = models.CharField(max_length=255, verbose_name='Название')
    authors = models.CharField(max_length=255, blank=True, verbose_name='Авторы')
    publisher = models.CharField(max_length=150, blank=True, verbose_name='Издательство')
    grade_level = models.PositiveSmallIntegerField(verbose_name='Класс')
    content_version = models.ForeignKey(
        ContentVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='textbooks',
        verbose_name='Версия контента',
    )
    file = models.FileField(
        upload_to='textbooks/',
        blank=True,
        null=True,
        verbose_name='Файл учебника (PDF)',
    )
    external_url = models.URLField(blank=True, verbose_name='Ссылка на учебник')
    is_official = models.BooleanField(default=True, verbose_name='Официальный источник')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Учебник'
        verbose_name_plural = 'Учебники'
        ordering = ['subject', 'grade_level', 'title']

    def __str__(self):
        return f'{self.title} ({self.grade_level} класс)'


class TextbookChapter(models.Model):
    """Глава учебника."""

    textbook = models.ForeignKey(
        Textbook,
        on_delete=models.CASCADE,
        related_name='chapters',
        verbose_name='Учебник',
    )
    title = models.CharField(max_length=255, verbose_name='Название главы')
    chapter_number = models.PositiveSmallIntegerField(default=1, verbose_name='Номер главы')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Глава учебника'
        verbose_name_plural = 'Главы учебников'
        ordering = ['order', 'chapter_number']

    def __str__(self):
        return f'{self.textbook.title}: {self.title}'


class TextbookFragment(models.Model):
    """Фрагмент учебника, привязанный к теме — источник для базы знаний и ИИ."""

    chapter = models.ForeignKey(
        TextbookChapter,
        on_delete=models.CASCADE,
        related_name='fragments',
        verbose_name='Глава',
    )
    topic = models.ForeignKey(
        Topic,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='textbook_fragments',
        verbose_name='Тема',
    )
    title = models.CharField(max_length=255, verbose_name='Заголовок фрагмента')
    content = models.TextField(verbose_name='Содержание')
    page_from = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Страница от')
    page_to = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Страница до')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Фрагмент учебника'
        verbose_name_plural = 'Фрагменты учебников'
        ordering = ['order']

    def __str__(self):
        return self.title


class TaskType(models.Model):
    """Тип задания по спецификации РИКЗ."""

    exam_track = models.ForeignKey(
        ExamTrack,
        on_delete=models.CASCADE,
        related_name='task_types',
        verbose_name='Экзаменационный трек',
    )
    code = models.CharField(max_length=50, verbose_name='Код типа')
    name = models.CharField(max_length=200, verbose_name='Название типа')
    description = models.TextField(blank=True, verbose_name='Описание формата')
    max_score = models.PositiveSmallIntegerField(default=1, verbose_name='Макс. балл')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Тип задания'
        verbose_name_plural = 'Типы заданий'
        ordering = ['order']
        unique_together = [('exam_track', 'code')]

    def __str__(self):
        return f'{self.code}: {self.name}'


class Task(models.Model):
    """Задание из базы (не генерируется ИИ)."""

    class AnswerFormat(models.TextChoices):
        SINGLE_CHOICE = 'single_choice', 'Один вариант ответа'
        MULTIPLE_CHOICE = 'multiple_choice', 'Несколько вариантов'
        TEXT = 'text', 'Текстовый ответ'
        NUMBER = 'number', 'Числовой ответ'

    class Difficulty(models.TextChoices):
        EASY = 'easy', 'Лёгкое'
        MEDIUM = 'medium', 'Среднее'
        HARD = 'hard', 'Сложное'

    class ScoringScheme(models.TextChoices):
        BINARY_1 = 'bin1', '0 или 1'
        BINARY_2 = 'bin2', '0 или 2'
        PARTIAL_2 = 'part2', '0 / 1 / 2 (частично верно)'

    topic = models.ForeignKey(
        Topic,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name='Тема',
    )
    task_type = models.ForeignKey(
        TaskType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tasks',
        verbose_name='Тип задания',
    )
    question = models.TextField(verbose_name='Условие задания')
    reading_text = models.TextField(
        blank=True,
        default='',
        verbose_name='Текст к заданию / Прочитанный текст',
        help_text='Полный текст или отрывок из РИКЗ, к которому относится вопрос (например, предл. 1–25)',
    )
    image = models.ImageField(
        upload_to='tasks/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Картинка к заданию',
        help_text='Для 1–4 класса: иллюстрация в условии',
    )
    answer_format = models.CharField(
        max_length=20,
        choices=AnswerFormat.choices,
        default=AnswerFormat.SINGLE_CHOICE,
        verbose_name='Формат ответа',
    )
    scoring_scheme = models.CharField(
        max_length=10,
        choices=ScoringScheme.choices,
        default=ScoringScheme.PARTIAL_2,
        verbose_name='Схема первичных баллов',
        help_text='Как на ЦТ/ЦЭ: часть A обычно 0/1/2, часть B — 0/2 или 0/1/2',
    )
    difficulty = models.CharField(
        max_length=10,
        choices=Difficulty.choices,
        default=Difficulty.MEDIUM,
        verbose_name='Сложность',
    )
    source = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Источник',
        help_text='Сборник РИКЗ, учебник и т.д.',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активно')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')

    @property
    def max_primary_points(self) -> int:
        if self.scoring_scheme == self.ScoringScheme.BINARY_1:
            return 1
        return 2

    class Meta:
        verbose_name = 'Задание'
        verbose_name_plural = 'Задания'
        ordering = ['-created_at']

    def __str__(self):
        return self.question[:80]


class TaskOption(models.Model):
    """Вариант ответа для тестового задания."""

    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='options',
        verbose_name='Задание',
    )
    text = models.CharField(max_length=500, verbose_name='Текст варианта')
    image = models.ImageField(
        upload_to='task_options/%Y/%m/',
        blank=True,
        null=True,
        verbose_name='Картинка варианта',
    )
    is_correct = models.BooleanField(default=False, verbose_name='Правильный ответ')
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Порядок')

    class Meta:
        verbose_name = 'Вариант ответа'
        verbose_name_plural = 'Варианты ответов'
        ordering = ['order']

    def __str__(self):
        return self.text[:60]


class TaskSolution(models.Model):
    """Эталонное решение и разбор (без ИИ)."""

    task = models.OneToOneField(
        Task,
        on_delete=models.CASCADE,
        related_name='solution',
        verbose_name='Задание',
    )
    correct_answer = models.TextField(verbose_name='Правильный ответ')
    explanation = models.TextField(verbose_name='Разбор решения')
    common_mistakes = models.TextField(blank=True, verbose_name='Типичные ошибки')

    class Meta:
        verbose_name = 'Решение задания'
        verbose_name_plural = 'Решения заданий'

    def __str__(self):
        return f'Решение #{self.task_id}'


class ScoreScale(models.Model):
    """Таблица соответствия первичных и тестовых баллов (РИКЗ)."""

    exam_track = models.ForeignKey(
        ExamTrack,
        on_delete=models.CASCADE,
        related_name='score_scales',
        verbose_name='Экзаменационный трек',
    )
    year = models.PositiveSmallIntegerField(verbose_name='Год шкалы')
    title = models.CharField(max_length=255, verbose_name='Название')
    max_primary = models.PositiveSmallIntegerField(
        default=80,
        verbose_name='Макс. первичный балл',
    )
    source_url = models.URLField(blank=True, verbose_name='Источник')
    is_current = models.BooleanField(default=True, verbose_name='Текущая')

    class Meta:
        verbose_name = 'Шкала баллов'
        verbose_name_plural = 'Шкалы баллов'
        ordering = ['-year', 'exam_track']
        unique_together = [('exam_track', 'year')]

    def __str__(self):
        return f'{self.title} ({self.year})'


class ScoreScaleRow(models.Model):
    """Строка шкалы: первичный → тестовый."""

    scale = models.ForeignKey(
        ScoreScale,
        on_delete=models.CASCADE,
        related_name='rows',
        verbose_name='Шкала',
    )
    primary_score = models.PositiveSmallIntegerField(verbose_name='Первичный балл')
    test_score = models.PositiveSmallIntegerField(verbose_name='Тестовый балл')

    class Meta:
        verbose_name = 'Строка шкалы'
        verbose_name_plural = 'Строки шкалы'
        ordering = ['primary_score']
        unique_together = [('scale', 'primary_score')]

    def __str__(self):
        return f'{self.primary_score} → {self.test_score}'


class ExamCollection(models.Model):
    """Официальный сборник (книга) с полными вариантами."""

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='exam_collections',
        verbose_name='Предмет',
    )
    title = models.CharField(max_length=255, verbose_name='Название')
    publisher = models.CharField(max_length=150, blank=True, verbose_name='Издательство')
    year = models.PositiveSmallIntegerField(null=True, blank=True, verbose_name='Год издания')
    isbn = models.CharField(max_length=32, blank=True, verbose_name='ISBN')
    source_file = models.CharField(max_length=255, blank=True, verbose_name='Файл в materials/')
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Сборник вариантов'
        verbose_name_plural = 'Сборники вариантов'
        ordering = ['-year', 'title']

    def __str__(self):
        return self.title


class ExamVariant(models.Model):
    """Полный вариант (билет) из сборника."""

    collection = models.ForeignKey(
        ExamCollection,
        on_delete=models.CASCADE,
        related_name='variants',
        verbose_name='Сборник',
    )
    number = models.PositiveSmallIntegerField(verbose_name='Номер варианта')
    title = models.CharField(max_length=100, blank=True, verbose_name='Подпись')
    year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Год экзамена',
        help_text='Год ЦТ/ЦЭ, если известен',
    )
    is_active = models.BooleanField(default=True, verbose_name='Активен')

    class Meta:
        verbose_name = 'Вариант экзамена'
        verbose_name_plural = 'Варианты экзамена'
        ordering = ['collection', 'number']
        unique_together = [('collection', 'number')]

    def __str__(self):
        label = self.title or f'Вариант {self.number}'
        return f'{self.collection.title}: {label}'


class VariantTask(models.Model):
    """Задание внутри варианта (порядок в билете)."""

    variant = models.ForeignKey(
        ExamVariant,
        on_delete=models.CASCADE,
        related_name='variant_tasks',
        verbose_name='Вариант',
    )
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='variant_links',
        verbose_name='Задание',
    )
    order = models.PositiveSmallIntegerField(default=0, verbose_name='Номер в варианте')

    class Meta:
        verbose_name = 'Задание варианта'
        verbose_name_plural = 'Задания вариантов'
        ordering = ['order']
        unique_together = [('variant', 'order'), ('variant', 'task')]

    def __str__(self):
        return f'{self.variant_id} #{self.order}'
