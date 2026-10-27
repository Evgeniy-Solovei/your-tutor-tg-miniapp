from django.db import migrations, models


def backfill_extra_task_counts(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            UPDATE knowledge_topic AS t
            SET extra_task_count = COALESCE(s.cnt, 0)
            FROM (
                SELECT topic_id, COUNT(*)::int AS cnt
                FROM knowledge_topicextratask
                WHERE is_active = TRUE
                GROUP BY topic_id
            ) AS s
            WHERE t.id = s.topic_id
            """
        )
        cursor.execute(
            """
            UPDATE knowledge_topic
            SET extra_task_count = 0
            WHERE extra_task_count IS DISTINCT FROM 0
              AND NOT EXISTS (
                SELECT 1 FROM knowledge_topicextratask e
                WHERE e.topic_id = knowledge_topic.id AND e.is_active = TRUE
              )
            """
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0009_topicextratask_image_topicextratask_image_url'),
    ]

    operations = [
        migrations.AddField(
            model_name='topic',
            name='extra_task_count',
            field=models.PositiveIntegerField(
                default=0,
                help_text='Денормализованный счётчик активных TopicExtraTask (без COUNT по таблице).',
                verbose_name='Кол-во доп. заданий',
            ),
        ),
        migrations.RunPython(backfill_extra_task_counts, noop_reverse),
    ]
