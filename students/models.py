from django.db import models
from django.utils import timezone

from core.models import City, School
from knowledge.models import ExamTrack, Subject


class Student(models.Model):
    """Ученик — пользователь Telegram-бота."""

    class Goal(models.TextChoices):
        CT = 'ct', 'Подготовка к ЦТ'
        CE = 'ce', 'Подготовка к ЦЭ'
        ATTESTAT = 'attestat', 'Аттестат после 9 класса'
        IMPROVE = 'improve', 'Подтянуть предмет'

    tg_id = models.PositiveBigIntegerField(unique=True, db_index=True, verbose_name='Telegram ID')
    username = models.CharField(max_length=100, blank=True, verbose_name='Username Telegram')
    display_name = models.CharField(max_length=100, verbose_name='Имя в рейтинге')
    grade = models.PositiveSmallIntegerField(verbose_name='Класс')
    goal = models.CharField(max_length=20, choices=Goal.choices, verbose_name='Цель обучения')
    subject = models.ForeignKey(
        Subject,
        on_delete=models.PROTECT,
        related_name='students',
        verbose_name='Предмет',
    )
    exam_track = models.ForeignKey(
        ExamTrack,
        on_delete=models.PROTECT,
        related_name='students',
        verbose_name='Экзаменационный трек',
    )
    city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name='Город',
    )
    school = models.ForeignKey(
        School,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students',
        verbose_name='Школа',
    )
    exam_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        verbose_name='Год сдачи экзамена',
    )
    timezone_name = models.CharField(
        max_length=64,
        default='Europe/Minsk',
        verbose_name='Часовой пояс',
    )
    is_pro = models.BooleanField(default=False, verbose_name='Pro-подписка')
    pro_until = models.DateTimeField(null=True, blank=True, verbose_name='Pro до')
    xp = models.PositiveIntegerField(default=0, verbose_name='Опыт (XP)')
    streak_days = models.PositiveSmallIntegerField(default=0, verbose_name='Серия дней')
    last_activity_date = models.DateField(null=True, blank=True, verbose_name='Последняя активность')
    daily_tasks_completed = models.PositiveSmallIntegerField(
        default=0,
        verbose_name='Заданий выполнено сегодня',
    )
    registration_completed = models.BooleanField(default=False, verbose_name='Регистрация завершена')
    notifications_enabled = models.BooleanField(default=True, verbose_name='Ежедневные уведомления')
    tg_blocked = models.BooleanField(default=False, verbose_name='Бот заблокирован')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата регистрации')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Ученик'
        verbose_name_plural = 'Ученики'
        indexes = [
            models.Index(fields=['-xp', 'created_at']),
            models.Index(fields=['city', '-xp']),
            models.Index(fields=['school', '-xp']),
        ]

    def __str__(self):
        return f'{self.display_name} (tg:{self.tg_id})'

    @property
    def has_active_pro(self) -> bool:
        if not self.is_pro:
            return False
        if self.pro_until and self.pro_until < timezone.now():
            return False
        return True

    async def update_activity_streak(self):
        today = timezone.localdate()
        if self.last_activity_date == today:
            return

        if self.last_activity_date and (today - self.last_activity_date).days == 1:
            self.streak_days += 1
        else:
            self.streak_days = 1

        self.last_activity_date = today
        self.daily_tasks_completed = 0
        await self.asave(
            update_fields=[
                'streak_days',
                'last_activity_date',
                'daily_tasks_completed',
                'updated_at',
            ]
        )


class Parent(models.Model):
    """Родитель в Telegram (может не быть учеником)."""

    tg_id = models.PositiveBigIntegerField(unique=True, db_index=True, verbose_name='Telegram ID')
    username = models.CharField(max_length=100, blank=True, verbose_name='Username')
    display_name = models.CharField(max_length=100, blank=True, verbose_name='Имя')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Родитель'
        verbose_name_plural = 'Родители'

    def __str__(self):
        return self.display_name or f'parent:{self.tg_id}'


class ParentInvite(models.Model):
    """Код привязки, который ребёнок показывает родителю."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='parent_invites',
        verbose_name='Ученик',
    )
    code = models.CharField(max_length=8, unique=True, db_index=True, verbose_name='Код')
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    expires_at = models.DateTimeField(verbose_name='Действует до')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Код для родителя'
        verbose_name_plural = 'Коды для родителей'
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.code} → {self.student_id}'


class ParentChildLink(models.Model):
    """Связь родитель ↔ ребёнок."""

    parent = models.ForeignKey(
        Parent,
        on_delete=models.CASCADE,
        related_name='children',
        verbose_name='Родитель',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='parent_links',
        verbose_name='Ученик',
    )
    linked_at = models.DateTimeField(auto_now_add=True, verbose_name='Привязан')
    notify_weekly = models.BooleanField(default=True, verbose_name='Недельный отчёт')

    class Meta:
        verbose_name = 'Связь родитель–ребёнок'
        verbose_name_plural = 'Связи родитель–ребёнок'
        unique_together = [('parent', 'student')]
        ordering = ['-linked_at']

    def __str__(self):
        return f'{self.parent_id} ↔ {self.student_id}'


class PaymentOrder(models.Model):
    """Счёт на оплату Pro-подписки через bePaid / ЕРИП."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Ожидает оплаты'
        PAID = 'paid', 'Оплачен'
        FAILED = 'failed', 'Ошибка'
        CANCELLED = 'cancelled', 'Отменён'

    order_id = models.CharField(
        max_length=64,
        unique=True,
        verbose_name='ID заказа',
    )
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='payment_orders',
        verbose_name='Ученик',
    )
    plan_code = models.CharField(
        max_length=30,
        default='pro_1m',
        verbose_name='Код тарифа',
    )
    amount_byn = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        default=19.90,
        verbose_name='Сумма (BYN)',
    )
    days = models.PositiveIntegerField(default=30, verbose_name='Дней подписки')
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        verbose_name='Статус',
    )
    bepaid_checkout_url = models.URLField(max_length=500, blank=True, verbose_name='Ссылка на оплату bePaid')
    bepaid_token = models.CharField(max_length=255, blank=True, verbose_name='Токен bePaid')
    paid_at = models.DateTimeField(null=True, blank=True, verbose_name='Оплачено в')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')

    class Meta:
        verbose_name = 'Счёт bePaid / ЕРИП'
        verbose_name_plural = 'Счета bePaid / ЕРИП'
        ordering = ['-created_at']

    def __str__(self):
        return f'Заказ {self.order_id} ({self.student.display_name}) — {self.amount_byn} BYN'


class UserSessionLog(models.Model):
    """Учёт времени активности ученика в Mini App."""

    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='session_logs',
        verbose_name='Ученик',
    )
    date = models.DateField(default=timezone.localdate, db_index=True, verbose_name='Дата')
    duration_seconds = models.PositiveIntegerField(default=0, verbose_name='Время в Mini App (сек)')
    session_count = models.PositiveIntegerField(default=1, verbose_name='Сессий за день')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')

    class Meta:
        verbose_name = 'Сессия и время активности'
        verbose_name_plural = 'Сессии и время активности'
        unique_together = [('student', 'date')]
        ordering = ['-date']

    def __str__(self):
        mins = self.duration_seconds // 60
        return f'{self.student.display_name} — {self.date}: {mins} мин ({self.duration_seconds} сек)'

