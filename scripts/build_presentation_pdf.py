#!/usr/bin/env python3
"""Скрипт сборки PDF презентации с обновлёнными снимками Статистики и Рейтинга."""

import os
from pathlib import Path
from PIL import Image as PILImage
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable, PageBreak
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / 'Tvoy_Domashniy_Repetitor_Presentation.pdf'
SCREENS_DIR = ROOT / 'media' / 'presentation_screens'

FONT_NAME = 'Helvetica'
font_paths = [
    '/System/Library/Fonts/Supplemental/Arial.ttf',
    '/System/Library/Fonts/Helvetica.ttc',
    '/Library/Fonts/Arial.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
]

for fp in font_paths:
    if os.path.exists(fp):
        try:
            pdfmetrics.registerFont(TTFont('CustomCyrillic', fp))
            pdfmetrics.registerFont(TTFont('CustomCyrillic-Bold', fp))
            FONT_NAME = 'CustomCyrillic'
            break
        except Exception:
            pass

FONT_BOLD = 'CustomCyrillic-Bold' if FONT_NAME == 'CustomCyrillic' else FONT_NAME

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont(FONT_NAME, 8)
        self.setFillColor(colors.HexColor('#64748B'))
        self.drawString(45, 20, "Инвестиционная презентация проекта «Твой домашний репетитор» (Беларусь)")
        page_text = f"Стр. {self._pageNumber} из {page_count}"
        self.drawRightString(550, 20, page_text)
        self.setStrokeColor(colors.HexColor('#CBD5E1'))
        self.setLineWidth(0.5)
        self.line(45, 32, 550, 32)
        self.restoreState()

def create_proportional_image(path_str, target_width=220, max_height=320):
    """Масштабирует изображение с математически точным сохранением пропорций."""
    with PILImage.open(path_str) as im:
        orig_w, orig_h = im.size
    w = target_width
    h = w * (orig_h / orig_w)
    if h > max_height:
        h = max_height
        w = h * (orig_w / orig_h)
    return Image(path_str, width=w, height=h)

def build_pdf():
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=A4,
        leftMargin=45,
        rightMargin=45,
        topMargin=45,
        bottomMargin=45,
    )

    styles = getSampleStyleSheet()

    PRIMARY_COLOR = colors.HexColor('#2563EB')
    ACCENT_COLOR = colors.HexColor('#1D4ED8')
    DARK_TEXT = colors.HexColor('#0F172A')
    SECONDARY_TEXT = colors.HexColor('#334155')

    title_style = ParagraphStyle(
        'TitleStyle',
        parent=styles['Heading1'],
        fontName=FONT_BOLD,
        fontSize=20,
        leading=24,
        textColor=PRIMARY_COLOR,
        spaceAfter=4,
    )

    subtitle_style = ParagraphStyle(
        'SubTitleStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=10.5,
        leading=14,
        textColor=SECONDARY_TEXT,
        spaceAfter=10,
    )

    h1_style = ParagraphStyle(
        'H1Style',
        parent=styles['Heading2'],
        fontName=FONT_BOLD,
        fontSize=12,
        leading=15,
        textColor=ACCENT_COLOR,
        spaceBefore=8,
        spaceAfter=4,
    )

    body_style = ParagraphStyle(
        'BodyStyle',
        parent=styles['Normal'],
        fontName=FONT_NAME,
        fontSize=9,
        leading=12.5,
        textColor=DARK_TEXT,
        spaceAfter=4,
    )

    bullet_style = ParagraphStyle(
        'BulletStyle',
        parent=body_style,
        leftIndent=10,
        firstLineIndent=-6,
        spaceAfter=3,
    )

    story = []

    # ТИТУЛ
    story.append(Paragraph("БИЗНЕС-ПРЕДЛОЖЕНИЕ: «ТВОЙ ДОМАШНИЙ РЕПЕТИТОР»", title_style))
    story.append(Paragraph("Национальная ИИ-платформа персонального обучения и подготовки к ЦЭ/ЦТ в Telegram Mini App", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=PRIMARY_COLOR, spaceBefore=0, spaceAfter=8))

    # 1. ОБЪЁМ РЫНКА
    story.append(Paragraph("1. Анализ рынка и статистика Беларуси (Открытые данные)", h1_style))
    story.append(Paragraph("• <b>1 085 000+ школьников</b> обучается в учреждениях общего среднего образования РБ (Белстат и Минобразования РБ).", bullet_style))
    story.append(Paragraph("• <b>105 000+ выпускников</b> 9 и 11 классов ежегодно сдают обязательные экзамены, ЦЭ и ЦТ.", bullet_style))
    story.append(Paragraph("• <b>> 100 000 000 BYN ($35+ млн) в год</b> — суммарный объём рынка частных репетиторов в Беларуси.", bullet_style))
    story.append(Paragraph("• <b>Уникальность</b>: В Беларуси <b>НЕТ ни одного аналогичного комплексно интегрированного продукта</b> в Telegram Mini App с банком РИКЗ.", bullet_style))

    # 2. ПРОБЛЕМА
    story.append(Paragraph("2. Боль современной семьи: Проблема перегрузки и затрат", h1_style))
    story.append(Paragraph("• <b>Колоссальная нагрузка на детей</b>: Школа, кружки, спортивные секции. Подстроиться под график репетитора — огромный стресс.", bullet_style))
    story.append(Paragraph("• <b>Потеря времени в дороге</b>: Поездки к репетиторам отнимают у ребёнка до 1.5–2 часов ежедневно в транспорте и пробках.", bullet_style))
    story.append(Paragraph("• <b>Высокие финансовые затраты</b>: Подготовка к экзаменам по 3 предметам обходится родителям в 1500–3000 BYN ($500–1000) в год.", bullet_style))

    # 3. НАШЕ РЕШЕНИЕ
    story.append(Paragraph("3. Наше решение: Обучение прямо в смартфоне", h1_style))
    story.append(Paragraph("• <b>Занятия в любой момент</b>: Заниматься можно везде — в транспорте между тренировками, дома, на перемене (15 минут в день).", bullet_style))
    story.append(Paragraph("• <b>Прозрачность для родителей</b>: Родители видят точное время занятий, выполненные темы, % точности и отчёты в Telegram.", bullet_style))
    story.append(Paragraph("• <b>100% эталонный банк</b>: 13 500+ заданий РИКЗ за 2003–2025 гг., а ИИ (DeepSeek) используется строго для понятного разъяснения правил.", bullet_style))

    # 4. ДЛЯ КОГО ПРИЛОЖЕНИЕ
    story.append(Paragraph("4. Целевая аудитория (1–11 классы)", h1_style))
    story.append(Paragraph("• <b>1–4 классы</b> — начальная школа, базовая грамотность, игровые карточки с иллюстрациями.", bullet_style))
    story.append(Paragraph("• <b>5–8 классы</b> — средняя школа, орфография, синтаксис, подготовка к контрольным работам.", bullet_style))
    story.append(Paragraph("• <b>9 класс</b> — подготовка к изложениям, экзаменам и поступлению в Лицей БГУ и колледжи.", bullet_style))
    story.append(Paragraph("• <b>10–11 классы</b> — профильная подготовка, симуляция вариантов ЦЭ/ЦТ с таймером на 180 минут и шкалой РИКЗ.", bullet_style))

    # 5. ГЕЙМИФИКАЦИЯ И ПРИЗЫ
    story.append(Paragraph("5. Соревнования и Призы для школьников", h1_style))
    story.append(Paragraph("• <b>Рейтинги школ и городов</b>: Ученики соревнуются за честь своей школы и класса (Лиги недели).", bullet_style))
    story.append(Paragraph("• <b>Розыгрыши призов</b>: Подписки (Яндекс Плюс, Telegram Premium, Telegram Stars) и сертификаты для лучших учеников.", bullet_style))

    # 6. ВИТРИНА ДЛЯ МИНИСТЕРСТВА ОБРАЗОВАНИЯ РБ
    story.append(Paragraph("6. Вклад в образование РБ и интеграция с Минобразования", h1_style))
    story.append(Paragraph("• Программу можно официально вынести на согласование с <b>Министерством образования РБ</b>.", bullet_style))
    story.append(Paragraph("• <b>Стирание неравенства</b>: Учащиеся из сельских школ получают доступ к качеству подготовки лучших репетиторов Минска.", bullet_style))

    # 7. ФИНАНСОВЫЙ ПРОГНОЗ
    story.append(Paragraph("7. Прогноз доходов и Бизнес-предложение (Unit Economics)", h1_style))
    p7_text = (
        "• <b>Модель</b>: Freemium (3 задачи/день бесплатно) vs <b>Pro-подписка (19.90 BYN/мес)</b>.<br/>"
        "• <b>Прогноз выручки</b> при привлечении всего <b>2% рынка школьников РБ (20 000 учащихся)</b>:<br/>"
        "  — Ежемесячная выручка: <b>398 000 BYN в месяц (~$125 000 / мес)</b>.<br/>"
        "  — Годовая выручка (ARR): <b>~4 770 000 BYN (~$1.5 млн в год)</b>.<br/>"
        "• <b>Инвестиционный запрос</b>: 25 000 – 40 000 BYN на финализацию Mini App UI, запуск B2C маркетинга и пилот в школах Минска."
    )
    story.append(Paragraph(p7_text, body_style))

    # 8. ДВОЙНАЯ ГАЛЕРЕЯ ДИЗАЙНА
    story.append(PageBreak())
    story.append(Paragraph("8. Сравнение 2 вариантов дизайна (Тема «Вайб» vs «Спокойная»)", h1_style))
    story.append(Paragraph("Приложение поддерживает 2 уникальные цветовые темы оформления. Скриншоты сгенерированы с точным сохранением исходного разрешения без растяжения:", body_style))
    story.append(Spacer(1, 6))

    dual_pairs = [
        ("1. Главный экран (Задания дня, Стрик)", "ratio_1_home_vibe.png", "ratio_1_home_calm.png"),
        ("2. Курсы — Сетка всех 1–11 классов", "ratio_2_courses_grades_vibe.png", "ratio_2_courses_grades_calm.png"),
        ("3. Практика и Задания РИКЗ", "ratio_3_practice_vibe.png", "ratio_3_practice_calm.png"),
        ("4. Аналитика успеваемости (Слабые темы и ошибки)", "ratio_target_stats_vibe.png", "ratio_target_stats_calm.png"),
        ("5. Рейтинг школ Минска (Текущий ученик и лидеры)", "ratio_target_rating_vibe.png", "ratio_target_rating_calm.png"),
        ("6. Тарифы и Pro-подписка (19.90 BYN)", "ratio_6_tariffs_vibe.png", "ratio_6_tariffs_calm.png"),
        ("7. Кабинет родителей (Семья)", "ratio_7_family_vibe.png", "ratio_7_family_calm.png"),
    ]

    for title, v_file, c_file in dual_pairs:
        v_path = SCREENS_DIR / v_file
        c_path = SCREENS_DIR / c_file

        if v_path.exists() and c_path.exists():
            story.append(Paragraph(f"<b>{title}</b>", ParagraphStyle('PairTitle', parent=body_style, fontName=FONT_BOLD, fontSize=10, textColor=ACCENT_COLOR, spaceBefore=6, spaceAfter=4)))
            
            img_v = create_proportional_image(str(v_path), target_width=220, max_height=320)
            img_c = create_proportional_image(str(c_path), target_width=220, max_height=320)
            
            lbl_v = Paragraph("<b>Тема «Вайб» (Молодёжная)</b>", ParagraphStyle('VibeLbl', parent=body_style, fontSize=8, alignment=1))
            lbl_c = Paragraph("<b>Тема «Спокойная» (Академическая)</b>", ParagraphStyle('CalmLbl', parent=body_style, fontSize=8, alignment=1))

            t = Table([[img_v, img_c], [lbl_v, lbl_c]], colWidths=[245, 245])
            t.setStyle(TableStyle([
                ('ALIGN', (0,0), (-1,-1), 'CENTER'),
                ('VALIGN', (0,0), (-1,-1), 'TOP'),
                ('BOTTOMPADDING', (0,0), (-1,-1), 4),
            ]))
            story.append(t)
            story.append(Spacer(1, 8))

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f'Presentation PDF successfully rebuilt at: {PDF_PATH}')

if __name__ == '__main__':
    build_pdf()
