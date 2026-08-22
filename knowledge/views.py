from adrf.views import APIView
from django.db.models import Count
from rest_framework.response import Response

from knowledge.models import ExamTrack, Subject, Task, Topic


class SubjectListView(APIView):
    async def get(self, request):
        subjects = [
            {'id': s.id, 'name': s.name, 'slug': s.slug}
            async for s in Subject.objects.filter(is_active=True).order_by('order')
        ]
        if not subjects:
            s, _ = await Subject.objects.aget_or_create(
                slug='russian',
                defaults={
                    'name': 'Русский язык',
                    'description': 'Подготовка к ЦТ/ЦЭ и аттестату (Беларусь)',
                    'order': 1,
                    'is_active': True,
                },
            )
            subjects = [{'id': s.id, 'name': s.name, 'slug': s.slug}]
        return Response(subjects)


class ExamTrackListView(APIView):
    async def get(self, request, subject_id: int):
        tracks = [
            {
                'id': t.id,
                'name': t.name,
                'track_type': t.track_type,
                'grade_from': t.grade_from,
                'grade_to': t.grade_to,
            }
            async for t in ExamTrack.objects.filter(subject_id=subject_id, is_active=True)
        ]
        return Response(tracks)


class CatalogView(APIView):
    """Каталог: предметы × классы × сколько заданий (для страницы «Курсы»)."""

    authentication_classes = []
    permission_classes = []

    async def get(self, request):
        grade_hints = {
            1: 'Буквы, слоги, первые слова — с картинками',
            2: 'Состав слова, предложение — с картинками',
            3: 'Части речи, корень и приставка — с картинками',
            4: 'Орфография, главное в предложении — база начальной школы',
            5: 'Фонетика, лексика, существительное, прилагательное',
            6: 'Глагол, местоимение, числительное, стили речи',
            7: 'Причастие, деепричастие, наречие, предлоги',
            8: 'Синтаксис простого предложения, тире и двоеточие',
            9: 'Сложное предложение + подготовка к изложению (экзамен)',
            10: 'Систематизация орфографии и синтаксиса для старшей школы',
            11: 'Полный банк заданий ЦТ и ЦЭ (А1–А18, Б1–Б10)',
        }
        subjects = [
            subject
            async for subject in Subject.objects.filter(is_active=True).order_by('order', 'name')
        ]
        counts = {
            (row['topic__section__exam_track__subject_id'], row['topic__grade_level']): row['count']
            async for row in Task.objects.filter(
                is_active=True,
                topic__section__exam_track__subject_id__in=[s.id for s in subjects],
                topic__grade_level__range=(1, 11),
            )
            .values('topic__section__exam_track__subject_id', 'topic__grade_level')
            .annotate(count=Count('id'))
        }
        res = []
        for subject in subjects:
            grades_data = []
            for g in range(1, 12):
                grades_data.append({
                    'grade': g,
                    'task_count': counts.get((subject.id, g), 0),
                    'hint': grade_hints.get(g, ''),
                })
            res.append({
                'id': subject.id,
                'name': subject.name,
                'slug': subject.slug,
                'grades': grades_data,
            })
        return Response({'subjects': res})
