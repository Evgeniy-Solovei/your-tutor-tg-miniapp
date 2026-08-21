import asyncio
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from students.models import Student
from learning.models import DailySession
from core.telegram_send import batch_send_telegram_messages


class Command(BaseCommand):
    help = 'Отправка ежедневных напоминаний "5 заданий дня" в Telegram-бот'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Отправить напоминание всем зарегистрированным ученикам независимо от статуса',
        )

    def handle(self, *args, **options):
        asyncio.run(self._process_reminders(force=options.get('force', False)))

    async def _process_reminders(self, force: bool = False):
        today = timezone.localdate()

        qs = Student.objects.filter(
            registration_completed=True,
            notifications_enabled=True,
            tg_blocked=False,
        )

        items = []
        skipped_count = 0

        async for student in qs:
            if not force:
                completed = await DailySession.objects.filter(
                    student=student,
                    session_date=today,
                    status=DailySession.Status.COMPLETED,
                ).aexists()
                if completed:
                    skipped_count += 1
                    continue

            name = student.display_name or 'друг'
            streak = student.streak_days or 0
            streak_text = f'🔥 Твоя серия: {streak} дн.' if streak > 0 else '⚡️ Начни серию занятий!'

            text = (
                f'👋 Привет, {name}!\n\n'
                f'🎯 Твои **5 заданий дня** уже сформированы.\n'
                f'{streak_text}\n\n'
                f'Займёт всего 5 минут — подтяни слабые темы!'
            )

            items.append({
                'chat_id': student.tg_id,
                'text': text,
                'parse_mode': 'Markdown',
            })

        async def mark_blocked(chat_id: int):
            await Student.objects.filter(tg_id=chat_id).aupdate(tg_blocked=True)

        res = await batch_send_telegram_messages(
            items,
            batch_size=25,
            delay_between_messages=0.05,
            delay_between_batches=1.0,
            on_blocked=mark_blocked,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Рассылка завершена: отправлено {res["sent"]}, ошибок {res["failed"]}, '
                f'заблокировали {res["blocked"]}, пропущено {skipped_count}'
            )
        )

