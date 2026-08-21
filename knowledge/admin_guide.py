"""Админ-гайд: как устроен контент и наполнение БД."""
from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import path

from knowledge.models import ExamTrack, Section, Subject, Task, Topic


@staff_member_required
def content_guide_view(request):
    subjects = []
    for subject in Subject.objects.filter(is_active=True).order_by('order', 'name'):
        tracks = []
        for track in ExamTrack.objects.filter(subject=subject, is_active=True).order_by('id'):
            by_grade = (
                Topic.objects.filter(section__exam_track=track, is_active=True)
                .values('grade_level')
                .annotate(
                    topics=Count('id'),
                    tasks=Count('tasks', filter=Q(tasks__is_active=True)),
                )
                .order_by('grade_level')
            )
            tracks.append(
                {
                    'track': track,
                    'sections': Section.objects.filter(exam_track=track).count(),
                    'by_grade': list(by_grade),
                }
            )
        subjects.append({'subject': subject, 'tracks': tracks})

    totals = {
        'subjects': Subject.objects.count(),
        'tracks': ExamTrack.objects.count(),
        'topics': Topic.objects.filter(is_active=True).count(),
        'tasks': Task.objects.filter(is_active=True).count(),
        'with_image': Task.objects.filter(is_active=True).exclude(image='').count(),
    }

    return render(
        request,
        'admin/content_guide.html',
        {
            **admin.site.each_context(request),
            'title': 'Как устроен контент',
            'subjects': subjects,
            'totals': totals,
            'commands': [
                ('seed_exam_tracks', 'Треки: школа / аттестат / ЦТ / ЦЭ'),
                ('import_school_grades', 'Темы + стартовые тесты 1–8'),
                ('import_primary_pictures', 'Картинки для 1–4 класса'),
                ('import_grade9_attestat', 'Темы 9 класса (аттестат)'),
                ('import_grade9_izlozheniya', 'Изложения 9 класса из PDF'),
                ('import_grade10_structure', 'Темы 10 класса'),
                ('import_rikz_bank', 'Банк ЦТ/ЦЭ 11 класса из PDF'),
                ('import_ct60_urokov', 'ЦТ за 60 уроков — задания + ключи'),
                ('register_exam_materials', 'Карточки всех PDF-сборников ЦТ/ЦЭ/РТ'),
                ('seed_score_scale', 'Шкала баллов ЦТ'),
            ],
        },
    )


def content_guide_urls():
    return [
        path(
            'content-guide/',
            admin.site.admin_view(content_guide_view),
            name='content_guide',
        ),
    ]
