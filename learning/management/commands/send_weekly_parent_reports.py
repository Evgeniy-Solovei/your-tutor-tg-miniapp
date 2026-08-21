import asyncio
import logging
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum, Count, Q
from students.models import Parent, ParentChildLink, Student
from learning.models import DailySession, TaskAttempt, TopicMastery
from core.telegram_send import batch_send_telegram_messages


class Command(BaseCommand):
    help = 'Отправка еженедельных отчётов родителям в Telegram-бот'

    def handle(self, *args, **options):
        asyncio.run(self._process_parent_reports())

    async def _process_parent_reports(self):
        end_date = timezone.localdate()
        start_date = end_date - timedelta(days=7)

        parents = Parent.objects.all()
        items = []

        async for parent in parents:
            links = [
                link async for link in ParentChildLink.objects.filter(parent=parent).select_related('student')
            ]
            if not links:
                continue

            for link in links:
                child = link.student
                # Собираем статистику ученика за неделю
                attempts = TaskAttempt.objects.filter(
                    student=child,
                    created_at__date__gte=start_date,
                    created_at__date__lte=end_date,
                )
                total_tasks = await attempts.acount()
                correct_tasks = await attempts.filter(is_correct=True).acount()

                accuracy = round((correct_tasks / total_tasks * 100)) if total_tasks > 0 else 0

                # Слабые темы
                weak_masteries = [
                    m async for m in TopicMastery.objects.filter(
                        student=child,
                        wrong_count__gt=0,
                    ).select_related('topic').order_by('mastery_score')[:3]
                ]

                weak_text = ''
                if weak_masteries:
                    weak_text = '\n⚠️ **Требуют внимания:**\n' + '\n'.join(
                        f'• {m.topic.name} ({m.mastery_score:.0%} верных)' for m in weak_masteries
                    )
                else:
                    weak_text = '\n✅ Все изученные темы освоены уверенно!'

                text = (
                    f'📊 **Еженедельный отчёт по ученику: {child.display_name}**\n'
                    f'🗓 За период: {start_date.strftime("%d.%m")} — {end_date.strftime("%d.%m")}\n\n'
                    f'✅ Решено заданий: **{total_tasks}**\n'
                    f'🎯 Точность ответов: **{accuracy}%**\n'
                    f'🔥 Серия занятий: **{child.streak_days} дн.**\n'
                    f'⭐ Опыт (XP): **{child.xp} XP**\n'
                    f'{weak_text}\n\n'
                    f'💡 *Совет репетитора:* хвалите ребёнка за регулярность, а не только за оценки!'
                )

                items.append({
                    'chat_id': parent.tg_id,
                    'text': text,
                    'parse_mode': 'Markdown',
                })

        res = await batch_send_telegram_messages(
            items,
            batch_size=25,
            delay_between_messages=0.05,
            delay_between_batches=1.0,
        )

        self.stdout.write(
            self.style.SUCCESS(
                f'Рассылка родительских отчётов завершена: отправлено {res["sent"]}, ошибок {res["failed"]}'
            )
        )

