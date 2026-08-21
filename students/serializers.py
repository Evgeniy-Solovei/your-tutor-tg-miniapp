from adrf.serializers import ModelSerializer

from students.models import Student


class StudentSerializer(ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id',
            'tg_id',
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
