from adrf.serializers import ModelSerializer
from rest_framework import serializers

from students.models import Student


class StudentSerializer(ModelSerializer):
    is_telegram_linked = serializers.BooleanField(read_only=True)

    class Meta:
        model = Student
        fields = [
            'id',
            'tg_id',
            'username',
            'web_login',
            'is_telegram_linked',
            'display_name',
            'grade',
            'goal',
            'subject',
            'exam_track',
            'city',
            'school',
            'exam_year',
            'is_pro',
            'xp',
            'streak_days',
            'registration_completed',
            'notifications_enabled',
        ]
