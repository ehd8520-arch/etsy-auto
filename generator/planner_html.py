"""
Planner Generator v2 -- HTML+CSS -> PDF (상위 1% Etsy 셀러 벤치마킹).

- 사이드 인덱스 탭 (모든 페이지에서 월 이동)
- Quicksand + Poppins 폰트
- 파스텔 그래디언트
- 와시테이프 장식
- 커스텀 체크박스
- 코너 장식
"""
import calendar
import logging
import random
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from config.settings import OUTPUT_DIR
from models import Product, Category, ProductStatus

# 현재 테마 / 니치 (생성 시 설정)
_current_theme: dict = {}
_current_niche: str | None = None

# ── 니치별 오버라이드 ──
# 순서 = 수요 폭발 × 경쟁 낮음 우선순위
NICHE_CONFIG: dict[str | None, dict] = {
    None: {},  # generic — 범용

    # ── 수요 폭발 + 경쟁 낮음 ──
    "ADHD": {
        "title_prefix": "ADHD",
        "subtitle_override": "Focus & Executive Function Planner",
        "daily_sub": "Time Block · Task Breakdown · Dopamine Boost",
        "habit_sub": "Streak Tracker · Dopamine Log · Routine Builder",
        "seo_keywords": [
            "ADHD planner printable", "ADHD daily planner pdf", "ADHD planner pdf",
            "executive function planner", "ADHD productivity planner",
            "focus planner printable", "ADHD organization printable",
            "neurodivergent planner", "ADHD time management planner",
            "dopamine planner printable", "ADHD task planner", "ADHD habit tracker",
            "ADHD printable instant download", "ADHD goodnotes planner", "ADHD weekly planner",
        ],
    },
    "anxiety": {
        "title_prefix": "Anxiety Relief",
        "subtitle_override": "Calm & Grounding Daily Planner",
        "daily_sub": "Breathing Space · Worry Release · Gratitude Anchor",
        "habit_sub": "Calm Streak · Trigger Log · Coping Routine",
        "seo_keywords": [
            "anxiety planner printable", "anxiety journal pdf", "mental health planner printable",
            "anxiety relief planner", "calm planner pdf", "anxiety workbook printable",
            "mental wellness planner", "stress relief planner pdf", "anxiety tracker printable",
            "mindfulness planner pdf", "therapy planner printable", "grounding journal pdf",
            "anxiety management planner", "mental health journal printable", "calm daily planner",
        ],
    },
    "christian": {
        "title_prefix": "Christian",
        "subtitle_override": "Faith-Based Life & Devotional Planner",
        "daily_sub": "Scripture · Prayer · Gratitude · God's Purpose",
        "habit_sub": "Bible Reading Streak · Prayer Log · Faith Habits",
        "seo_keywords": [
            "christian planner printable", "christian planner pdf", "faith planner printable",
            "bible study planner", "christian daily planner", "prayer planner printable",
            "devotional planner pdf", "faith journal printable", "scripture planner pdf",
            "christian organizer printable", "christian gift printable", "prayer journal pdf",
            "christian habit tracker", "faith based planner", "christian weekly planner",
        ],
    },
    "sobriety": {
        "title_prefix": "Sobriety",
        "subtitle_override": "Recovery & Sober Living Planner",
        "daily_sub": "Sober Day Count · Trigger Log · Recovery Win",
        "habit_sub": "Sobriety Streak · Meeting Tracker · Recovery Habits",
        "seo_keywords": [
            "sobriety planner printable", "recovery planner pdf", "sober living planner",
            "sobriety journal printable", "addiction recovery planner", "sober planner pdf",
            "recovery journal printable", "sobriety tracker printable", "AA planner printable",
            "sobriety gift printable", "recovery daily planner", "sober daily tracker",
            "clean and sober planner", "recovery habit tracker", "sobriety milestone tracker",
        ],
    },

    # ── 수요 폭발 + 경쟁 중간 ──
    "mom": {
        "title_prefix": "Mom Life",
        "subtitle_override": "Family & Mom Productivity Planner",
        "daily_sub": "Family Schedule · Kids · Me-Time · Meal Prep",
        "habit_sub": "Mom Self-Care · Family Routine · Kids Activity Tracker",
        "seo_keywords": [
            "mom planner printable", "mom life planner pdf", "family planner printable",
            "mommy planner pdf", "mom daily planner printable", "busy mom planner",
            "mom organizer printable", "family schedule planner pdf", "mom weekly planner",
            "mom gift printable", "family planner pdf", "stay at home mom planner",
            "working mom planner printable", "mom habit tracker", "mom self care planner",
        ],
    },
    "homeschool": {
        "title_prefix": "Homeschool",
        "subtitle_override": "Curriculum & Family Learning Planner",
        "daily_sub": "Lesson Schedule · Subject Tracker · Learning Goals",
        "habit_sub": "Study Streak · Curriculum Tracker · Reading Log",
        "seo_keywords": [
            "homeschool planner printable", "homeschool planner pdf", "homeschool daily planner",
            "homeschool curriculum planner", "homeschool schedule printable",
            "homeschool lesson planner", "homeschool mom planner", "homeschool weekly planner",
            "homeschool organizer pdf", "homeschool planning printable",
            "homeschool record keeping", "homeschool tracker printable",
            "homeschool binder printable", "unschool planner pdf", "homeschool gift printable",
        ],
    },
    "self_care": {
        "title_prefix": "Self-Care",
        "subtitle_override": "Wellness & Self-Love Daily Planner",
        "daily_sub": "Morning Ritual · Body Check · Gratitude · Wind Down",
        "habit_sub": "Wellness Streak · Self-Love Tracker · Glow Routine",
        "seo_keywords": [
            "self care planner printable", "self care planner pdf", "wellness planner printable",
            "self love planner pdf", "self care journal printable", "wellness journal pdf",
            "self care daily planner", "self care routine planner", "wellness tracker printable",
            "self care gift printable", "mental wellness planner pdf", "glow up planner",
            "self care habit tracker", "wellbeing planner printable", "self care weekly planner",
        ],
    },

    # ── 2024-2025 신규 폭발 니치 (경쟁 거의 없음) ──
    "perimenopause": {
        "title_prefix": "Perimenopause",
        "subtitle_override": "Hormone & Midlife Wellness Planner",
        "daily_sub": "Symptom Log · Hormone Cycle · Sleep & Energy Tracker",
        "habit_sub": "HRT Tracker · Mood Log · Midlife Wellness Habits",
        "seo_keywords": [
            "perimenopause planner printable", "menopause planner pdf", "perimenopause journal",
            "menopause symptom tracker", "hormone planner printable", "midlife wellness planner",
            "perimenopause daily tracker", "menopause daily planner", "hot flash tracker printable",
            "perimenopause journal pdf", "menopause self care planner", "hormone health planner",
            "perimenopause gift printable", "midlife planner pdf", "menopause tracker printable",
        ],
    },
    "cycle_syncing": {
        "title_prefix": "Cycle Syncing",
        "subtitle_override": "Hormone Cycle & Fertility Wellness Planner",
        "daily_sub": "Cycle Phase · Energy · Mood · Nutrition by Phase",
        "habit_sub": "Cycle Tracker · Fertility Log · Hormone Habit Sync",
        "seo_keywords": [
            "cycle syncing planner printable", "cycle syncing pdf", "hormone cycle planner",
            "menstrual cycle planner", "fertility planner printable", "cycle syncing journal",
            "PCOS planner printable", "period tracker planner", "luteal phase planner",
            "cycle syncing workbook", "fertility tracker printable", "hormone balance planner",
            "cycle syncing instant download", "menstrual health planner", "PMDD planner printable",
        ],
    },
    "caregiver": {
        "title_prefix": "Caregiver",
        "subtitle_override": "Elderly Care & Family Caregiver Organizer",
        "daily_sub": "Care Schedule · Medications · Appointments · Notes",
        "habit_sub": "Caregiver Self-Care · Care Log · Medication Tracker",
        "seo_keywords": [
            "caregiver planner printable", "caregiver organizer pdf", "elderly care planner",
            "caregiver daily planner", "senior care organizer printable", "caregiver journal pdf",
            "parent care planner", "caregiver gift printable", "dementia caregiver planner",
            "caregiver self care planner", "family caregiver organizer", "elderly planner printable",
            "caregiver schedule printable", "sandwich generation planner", "care coordinator planner",
        ],
    },
    "glp1": {
        "title_prefix": "Weight Loss Journey",
        "subtitle_override": "GLP-1 Medication & Progress Tracker Planner",
        "daily_sub": "Injection Log · Protein Intake · Weight & Energy Tracker",
        "habit_sub": "Medication Streak · Nausea Log · Progress Milestone",
        "seo_keywords": [
            "weight loss planner printable", "weight loss journal pdf", "GLP1 tracker printable",
            "medication tracker planner", "weight loss tracker pdf", "ozempic tracker printable",
            "weight loss progress planner", "bariatric planner printable", "injection day tracker",
            "weight loss habit tracker", "protein tracker printable", "weight loss instant download",
            "weight loss daily planner", "body transformation tracker", "weight loss gift printable",
        ],
    },

    # ── 더블 니치 (Etsy 마켓 페이지 있음, 리스팅 극소) ──
    "ADHD_teacher": {
        "title_prefix": "ADHD Teacher",
        "subtitle_override": "Neurodivergent Educator Classroom Planner",
        "daily_sub": "Lesson Block · Focus Task · Dopamine Win · Student Notes",
        "habit_sub": "ADHD Routine · Grading Streak · Classroom Habit Log",
        "seo_keywords": [
            "ADHD teacher planner printable", "neurodivergent teacher planner", "ADHD educator planner",
            "ADHD lesson planner printable", "adhd teacher pdf", "neurodivergent educator planner",
            "ADHD classroom planner", "teacher ADHD organization", "ADHD teacher daily planner",
            "neurodivergent teacher pdf", "ADHD teacher gift printable", "focus teacher planner",
            "ADHD lesson plan template", "executive function teacher planner", "ADHD teacher instant download",
        ],
    },
    "ADHD_nurse": {
        "title_prefix": "ADHD Nurse",
        "subtitle_override": "Neurodivergent Healthcare Worker Planner",
        "daily_sub": "Shift Focus Block · Task Priority · Dopamine Check · Care Notes",
        "habit_sub": "Nurse ADHD Routine · Shift Streak · Focus Habit Log",
        "seo_keywords": [
            "ADHD nurse planner printable", "nurse ADHD planner pdf", "neurodivergent nurse planner",
            "ADHD healthcare planner", "nurse focus planner printable", "ADHD shift planner",
            "neurodivergent healthcare worker planner", "ADHD RN planner", "nurse ADHD organization",
            "ADHD nurse pdf", "ADHD nurse gift printable", "focus nurse planner printable",
            "ADHD nursing planner", "executive function nurse planner", "ADHD nurse instant download",
        ],
    },
    "christian_teacher": {
        "title_prefix": "Christian Teacher",
        "subtitle_override": "Faith-Based Educator & Classroom Planner",
        "daily_sub": "Scripture · Lesson Plan · Prayer for Students · Classroom Gratitude",
        "habit_sub": "Bible Reading · Prayer for Class · Faith Teaching Habits",
        "seo_keywords": [
            "christian teacher planner printable", "christian teacher planner pdf", "faith based teacher planner",
            "christian educator planner", "christian lesson planner printable", "bible teacher planner",
            "christian classroom planner", "faith teacher daily planner", "christian teacher gift printable",
            "christian teacher 2025 2026", "prayer teacher planner", "christian school planner",
            "christian homeschool teacher planner", "faith educator planner pdf", "christian teacher instant download",
        ],
    },
    "sobriety_mom": {
        "title_prefix": "Sober Mom",
        "subtitle_override": "Recovery & Mindful Motherhood Planner",
        "daily_sub": "Sober Day · Family Schedule · Recovery Win · Mom Self-Care",
        "habit_sub": "Sobriety Streak · Mom Routine · Recovery Habit Log",
        "seo_keywords": [
            "sober mom planner printable", "sobriety mom planner pdf", "recovery mom planner",
            "sober mother planner printable", "sober mom journal pdf", "recovery mom daily planner",
            "sober parenting planner", "mom sobriety tracker printable", "sober mom gift printable",
            "alcohol free mom planner", "sober curious mom planner", "recovery motherhood planner",
            "sober mom self care planner", "mom recovery planner pdf", "sober mom instant download",
        ],
    },

    # ── 높은 수요 + 경쟁 낮음 ──
    "nurse": {
        "title_prefix": "Nurse",
        "subtitle_override": "Shift Work & Patient Care Organizer",
        "daily_sub": "Shift Schedule · Patient Notes · Medication Log",
        "habit_sub": "Self-Care Tracker · Wellness Check · Nurse Routine",
        "seo_keywords": [
            "nurse planner printable", "nursing planner pdf", "nurse daily planner",
            "nurse shift planner", "healthcare planner printable",
            "nursing student planner", "nurse schedule planner",
            "medical planner printable", "RN planner pdf", "nurse life planner",
            "nurse organizer printable", "nurse weekly planner", "nurse self care planner",
            "nursing school planner", "nurse gift printable",
        ],
    },
    "teacher": {
        "title_prefix": "Teacher",
        "subtitle_override": "Lesson Plan & Classroom Organizer",
        "daily_sub": "Lesson Plan · Classroom Notes · Grade Tracker",
        "habit_sub": "Grading Tracker · Parent Contact Log · Classroom Routine",
        "seo_keywords": [
            "teacher planner printable", "teacher planner pdf", "lesson plan template printable",
            "classroom planner pdf", "teacher daily planner", "educator planner printable",
            "teacher weekly planner", "teacher organizer pdf", "lesson planner instant download",
            "elementary teacher planner", "teacher schedule planner", "teacher binder printable",
            "classroom teacher planner", "teacher gift printable", "school year planner teacher",
        ],
    },
    "pregnancy": {
        "title_prefix": "Pregnancy",
        "subtitle_override": "Week-by-Week Baby & Bump Planner",
        "daily_sub": "Baby Prep · Symptoms · Appointments · Bump Notes",
        "habit_sub": "Prenatal Vitamins · Movement Tracker · Nesting Checklist",
        "seo_keywords": [
            "pregnancy planner printable", "pregnancy journal pdf", "baby planner printable",
            "pregnancy tracker printable", "bump planner pdf", "maternity planner printable",
            "pregnancy daily planner", "prenatal planner pdf", "pregnancy gift printable",
            "pregnancy organizer printable", "baby shower gift printable", "pregnancy weekly planner",
            "new mom planner printable", "birth plan printable", "pregnancy habit tracker",
        ],
    },
    "entrepreneur": {
        "title_prefix": "Boss",
        "subtitle_override": "Entrepreneur & Side Hustle Planner",
        "daily_sub": "Revenue Goals · Tasks · Client Notes · Growth Wins",
        "habit_sub": "Income Tracker · Business Habit Log · CEO Routine",
        "seo_keywords": [
            "entrepreneur planner printable", "boss planner pdf", "business planner printable",
            "side hustle planner pdf", "entrepreneur daily planner", "small business planner",
            "CEO planner printable", "business goal planner pdf", "entrepreneur organizer",
            "girlboss planner printable", "freelancer planner pdf", "income tracker printable",
            "business habit tracker", "entrepreneur gift printable", "hustle planner pdf",
        ],
    },
}

logger = logging.getLogger(__name__)

THEMES = {
    # ── Romantic Bloom — mom / pregnancy / self_care ──
    "pastel_pink": {
        "primary": "#FB6F92", "light": "#FFE5EC", "accent": "#FFC2D1",
        "bg": "#FFFBFF", "line": "#F0D0D5", "text": "#444",
        "gradient": "linear-gradient(135deg, #FB6F92, #FFC2D1)",
        "tab_colors": ["#FFE5EC","#FFC2D1","#E8DFF5","#DAEAF6","#DDEDEA","#ADF7B6",
                        "#FFEE93","#FFC09F","#F6BC66","#F6AC69","#D4AFB9","#ABC4FF"],
        "font_title":  "'Playfair Display', Georgia, serif",
        "font_body":   "'Nunito', sans-serif",
        "font_accent": "'Quicksand', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Playfair+Display:wght@400;600;700&family=Nunito:wght@400;600;700&family=Quicksand:wght@400;600;700&family=Poppins:wght@400;600&display=swap",
        "header_style": "gradient_pill", "bg_pattern": "dots",
        "checkbox_style": "rounded",     "line_style": "dotted",
        "section_divider": "underline",  "border_radius": "10px",
        "corner_style": "bracket",
    },
    # ── Calm Nature — anxiety / homeschool / christian ──
    "sage_green": {
        "primary": "#6B8F71", "light": "#DDEDEA", "accent": "#A8C5A0",
        "bg": "#F5FAF5", "line": "#D0E0D0", "text": "#444",
        "gradient": "linear-gradient(135deg, #6B8F71, #A8C5A0)",
        "tab_colors": ["#DDEDEA","#C1E1C1","#B5D5B5","#A8C5A0","#9BBF9B","#8FB98F",
                        "#7FB069","#6B8F71","#5A7D5A","#4A6741","#D0E0D0","#E8F5E8"],
        "font_title":  "'Quicksand', sans-serif",
        "font_body":   "'Nunito', sans-serif",
        "font_accent": "'Quicksand', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&family=Nunito:wght@400;600;700&family=Poppins:wght@400;600&display=swap",
        "header_style": "gradient_pill", "bg_pattern": "dots",
        "checkbox_style": "rounded",     "line_style": "dotted",
        "section_divider": "underline",  "border_radius": "10px",
        "corner_style": "bracket",
    },
    # ── Ocean Professional — nurse / budget / ADHD_nurse ──
    "ocean_blue": {
        "primary": "#3A6B8C", "light": "#DAEAF6", "accent": "#79ADDC",
        "bg": "#F0F7FA", "line": "#C0D8E8", "text": "#444",
        "gradient": "linear-gradient(135deg, #3A6B8C, #79ADDC)",
        "tab_colors": ["#DAEAF6","#C0D8E8","#ABC4FF","#79ADDC","#5B9BD5","#3A6B8C",
                        "#2E5D7B","#1E4D6B","#B8D4E8","#E0EEF6","#A0C4DC","#6B9FCC"],
        "font_title":  "'Poppins', sans-serif",
        "font_body":   "'Poppins', sans-serif",
        "font_accent": "'Poppins', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap",
        "header_style": "flat_block",    "bg_pattern": "grid",
        "checkbox_style": "square",      "line_style": "solid",
        "section_divider": "left_bar",   "border_radius": "4px",
        "corner_style": "none",
    },
    # ── Dream Purple — ADHD / anxiety / sobriety ──
    "lavender": {
        "primary": "#7B6BA0", "light": "#E8DFF5", "accent": "#B8A8D0",
        "bg": "#F8F5FC", "line": "#D8D0E8", "text": "#444",
        "gradient": "linear-gradient(135deg, #7B6BA0, #B8A8D0)",
        "tab_colors": ["#E8DFF5","#D8D0E8","#C8B8D8","#B8A8D0","#A898C0","#9888B0",
                        "#8878A0","#7B6BA0","#F0E8F8","#E0D8F0","#D0C0E0","#C0B0D0"],
        "font_title":  "'Raleway', sans-serif",
        "font_body":   "'Raleway', sans-serif",
        "font_accent": "'Raleway', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Raleway:wght@400;500;600;700;800&display=swap",
        "header_style": "minimal_line",  "bg_pattern": "none",
        "checkbox_style": "circle",      "line_style": "dashed",
        "section_divider": "pill_badge", "border_radius": "16px",
        "corner_style": "dot",
    },
    # ── Cozy Boho — teacher / christian_teacher / homeschool ──
    "warm_beige": {
        "primary": "#8B7355", "light": "#FAF3E0", "accent": "#C8B090",
        "bg": "#FBF8F0", "line": "#E0D8C8", "text": "#444",
        "gradient": "linear-gradient(135deg, #8B7355, #C8B090)",
        "tab_colors": ["#FAF3E0","#F0E8D0","#E8DDC0","#DDD2B0","#C8B090","#B8A080",
                        "#A89070","#8B7355","#F5EDD8","#EBE0C8","#E0D5B8","#D5C8A8"],
        "font_title":  "'Lora', serif",
        "font_body":   "'Nunito', sans-serif",
        "font_accent": "'Lora', serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Lora:wght@400;500;600;700&family=Nunito:wght@400;600;700&family=Poppins:wght@400;600&display=swap",
        "header_style": "side_accent",   "bg_pattern": "none",
        "checkbox_style": "rounded",     "line_style": "solid",
        "section_divider": "underline",  "border_radius": "8px",
        "corner_style": "bracket",
    },
    # ── Dark Luxury — entrepreneur / perimenopause / glp1 ──
    "dark_elegant": {
        "primary": "#C9A84C", "light": "#2D2D44", "accent": "#E8D5A0",
        "bg": "#1C1C2E", "line": "#3A3A55", "text": "#E8E4D8",
        "gradient": "linear-gradient(135deg, #2A2040, #3D3060)",
        "tab_colors": ["#2D2D44","#353550","#3D3D60","#454570","#C9A84C","#D4B860",
                        "#DFC870","#E8D5A0","#252540","#2D2D4A","#353555","#3D3D60"],
        "font_title":  "'Cormorant Garamond', serif",
        "font_body":   "'Raleway', sans-serif",
        "font_accent": "'Cormorant Garamond', serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@400;500;600;700&family=Raleway:wght@400;500;600;700&display=swap",
        "header_style": "dark_card",     "bg_pattern": "none",
        "checkbox_style": "diamond",     "line_style": "solid",
        "section_divider": "left_bar",   "border_radius": "6px",
        "corner_style": "none",
    },
    # ── Ultra Minimal — ADHD / ADHD_teacher / ADHD_nurse ──
    "minimal_mono": {
        "primary": "#1A1A1A", "light": "#F0F0F0", "accent": "#888888",
        "bg": "#FAFAFA", "line": "#E0E0E0", "text": "#1A1A1A",
        "gradient": "linear-gradient(135deg, #2A2A2A, #555555)",
        "tab_colors": ["#F0F0F0","#E8E8E8","#E0E0E0","#D8D8D8","#C8C8C8","#B8B8B8",
                        "#A8A8A8","#989898","#888888","#787878","#EFEFEF","#E5E5E5"],
        "font_title":  "'Inter', sans-serif",
        "font_body":   "'Inter', sans-serif",
        "font_accent": "'Inter', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap",
        "header_style": "minimal_line",  "bg_pattern": "grid",
        "checkbox_style": "square",      "line_style": "solid",
        "section_divider": "plain",      "border_radius": "0px",
        "corner_style": "none",
    },
    # ── Earthy Warmth — caregiver / sobriety_mom / mom ──
    "terracotta": {
        "primary": "#C4714A", "light": "#FDF0E8", "accent": "#E8A882",
        "bg": "#FDF6EE", "line": "#EDD5C0", "text": "#3D2B1F",
        "gradient": "linear-gradient(135deg, #C4714A, #E8A882)",
        "tab_colors": ["#FDF0E8","#F5E0D0","#EDD0B8","#E8A882","#D08060","#C4714A",
                        "#B06040","#A05030","#F8E8D8","#F0D8C0","#E8C8A8","#E0B890"],
        "font_title":  "'Josefin Sans', sans-serif",
        "font_body":   "'Nunito', sans-serif",
        "font_accent": "'Josefin Sans', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Josefin+Sans:wght@400;600;700&family=Nunito:wght@400;600;700&display=swap",
        "header_style": "gradient_pill", "bg_pattern": "diagonal",
        "checkbox_style": "rounded",     "line_style": "dotted",
        "section_divider": "underline",  "border_radius": "12px",
        "corner_style": "bracket",
    },
    # ── Forest Faith — christian / sobriety / christian_teacher ──
    "forest_green": {
        "primary": "#2D5A27", "light": "#E8F5E3", "accent": "#6A9E5A",
        "bg": "#F4FAF3", "line": "#C8E0C0", "text": "#1A3318",
        "gradient": "linear-gradient(135deg, #2D5A27, #6A9E5A)",
        "tab_colors": ["#E8F5E3","#D0ECC8","#B8E0B0","#A0D498","#6A9E5A","#508A40",
                        "#3A7030","#2D5A27","#F0F8EE","#E0F0D8","#D0E8C8","#C0E0B8"],
        "font_title":  "'Merriweather', serif",
        "font_body":   "'Lato', sans-serif",
        "font_accent": "'Merriweather', serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Merriweather:wght@400;700&family=Lato:wght@400;700&display=swap",
        "header_style": "flat_block",    "bg_pattern": "none",
        "checkbox_style": "circle",      "line_style": "solid",
        "section_divider": "left_bar",   "border_radius": "8px",
        "corner_style": "dot",
    },
    # ── Sunrise Energy — pregnancy / cycle_syncing / perimenopause ──
    "coral_peach": {
        "primary": "#E8614A", "light": "#FFF0EC", "accent": "#FFB89A",
        "bg": "#FFF9F6", "line": "#FFD5C5", "text": "#3D1F18",
        "gradient": "linear-gradient(135deg, #E8614A, #FFB347)",
        "tab_colors": ["#FFF0EC","#FFE0D4","#FFD0BC","#FFB89A","#FF9D7A","#E8614A",
                        "#D05038","#BC4030","#FFF5F0","#FFE8E0","#FFD8C8","#FFC8B0"],
        "font_title":  "'Nunito', sans-serif",
        "font_body":   "'Nunito', sans-serif",
        "font_accent": "'Nunito', sans-serif",
        "font_url":    "https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800;900&family=Poppins:wght@400;600&display=swap",
        "header_style": "side_accent",   "bg_pattern": "dots",
        "checkbox_style": "circle",      "line_style": "dotted",
        "section_divider": "pill_badge", "border_radius": "20px",
        "corner_style": "none",
    },
}

MONTHS = list(calendar.month_abbr)[1:]
MONTHS_FULL = list(calendar.month_name)[1:]

# 섹션별 SVG 아이콘 (inline SVG, 외부 에셋 불필요)
SECTION_ICONS: dict[str, str] = {
    "Yearly Overview": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="3" y1="10" x2="21" y2="10"/></svg>',
    "Monthly":         '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><rect x="3" y="4" width="18" height="18" rx="2"/><line x1="3" y1="10" x2="21" y2="10"/><line x1="8" y1="2" x2="8" y2="6"/><line x1="16" y1="2" x2="16" y2="6"/></svg>',
    "Weekly":          '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>',
    "Daily":           '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
    "Habit":           '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/></svg>',
    "Notes":           '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
    "Budget":          '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><line x1="12" y1="1" x2="12" y2="23"/><path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/></svg>',
    "Meal":            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><path d="M18 8h1a4 4 0 0 1 0 8h-1"/><path d="M2 8h16v9a4 4 0 0 1-4 4H6a4 4 0 0 1-4-4V8z"/><line x1="6" y1="1" x2="6" y2="4"/><line x1="10" y1="1" x2="10" y2="4"/><line x1="14" y1="1" x2="14" y2="4"/></svg>',
    "Gratitude":       '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"/></svg>',
    "Monthly Review":  '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>',
    "Vision Board":    '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>',
    "Project Tracker": '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><rect x="2" y="7" width="20" height="14" rx="2"/><path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16"/></svg>',
    "Mood":            '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><path d="M8 14s1.5 2 4 2 4-2 4-2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>',
}


def _base_css(t: dict) -> str:
    # ── 테마 스타일 변수 추출 (기본값 = pastel_pink 스타일) ──
    font_title   = t.get("font_title",  "'Playfair Display', Georgia, serif")
    font_body    = t.get("font_body",   "'Nunito', sans-serif")
    font_accent  = t.get("font_accent", "'Quicksand', sans-serif")
    font_url     = t.get("font_url",    "https://fonts.googleapis.com/css2?family=Quicksand:wght@400;500;600;700&family=Nunito:wght@400;600;700&family=Playfair+Display:wght@400;600;700&family=Poppins:wght@400;600&display=swap")
    brad         = t.get("border_radius", "10px")
    line_sty     = t.get("line_style",  "dotted")
    cb_style     = t.get("checkbox_style", "rounded")
    sec_div      = t.get("section_divider", "underline")
    corner_style = t.get("corner_style", "bracket")
    header_style = t.get("header_style", "gradient_pill")
    bg_pat       = t.get("bg_pattern",  "dots")

    # ── 배경 패턴 ──
    if bg_pat == "dots":
        _bg_img = (f"radial-gradient(circle, {t['line']} 0.5px, transparent 0.5px),"
                   f"radial-gradient(ellipse 90% 60% at 5% 95%, {t['light']}BB 0%, transparent 55%),"
                   f"radial-gradient(ellipse 70% 50% at 95% 5%, {t['accent']}55 0%, transparent 50%)")
        _bg_sz  = "14px 14px, 100% 100%, 100% 100%"
    elif bg_pat == "grid":
        _bg_img = (f"repeating-linear-gradient(0deg,transparent,transparent 19px,{t['line']}50 19px,{t['line']}50 20px),"
                   f"repeating-linear-gradient(90deg,transparent,transparent 19px,{t['line']}30 19px,{t['line']}30 20px)")
        _bg_sz  = "auto"
    elif bg_pat == "diagonal":
        _bg_img = (f"repeating-linear-gradient(45deg,{t['line']}30 0px,{t['line']}30 1px,transparent 1px,transparent 12px),"
                   f"radial-gradient(ellipse 90% 60% at 5% 95%, {t['light']}88 0%, transparent 55%)")
        _bg_sz  = "auto, 100% 100%"
    else:  # none
        _bg_img = f"radial-gradient(ellipse 90% 60% at 5% 95%, {t['light']}66 0%, transparent 55%)"
        _bg_sz  = "100% 100%"

    # ── 코너 장식 ──
    if corner_style == "bracket":
        _corner = (f".corner{{position:absolute;width:20px;height:20px;border-color:{t['accent']};border-style:solid;}}"
                   f".c-tl{{top:12px;left:12px;border-width:2px 0 0 2px;border-radius:4px 0 0 0;}}"
                   f".c-tr{{top:12px;right:40px;border-width:2px 2px 0 0;border-radius:0 4px 0 0;}}"
                   f".c-bl{{bottom:12px;left:12px;border-width:0 0 2px 2px;border-radius:0 0 0 4px;}}"
                   f".c-br{{bottom:12px;right:12px;border-width:0 2px 2px 0;border-radius:0 0 4px 0;}}")
    elif corner_style == "dot":
        _corner = (f".corner{{position:absolute;width:6px;height:6px;background:{t['accent']};border-radius:50%;border:none;}}"
                   f".c-tl{{top:14px;left:14px;}} .c-tr{{top:14px;right:42px;}}"
                   f".c-bl{{bottom:14px;left:14px;}} .c-br{{bottom:14px;right:14px;}}")
    else:  # none
        _corner = ".corner{display:none;}"

    # ── 헤더 ──
    if header_style == "gradient_pill":
        _header = f"""
    .header{{background:{t['gradient']};border-radius:16px;padding:15px 22px;margin-bottom:14px;margin-right:32px;
        display:flex;justify-content:space-between;align-items:center;
        box-shadow:0 4px 16px rgba(0,0,0,0.10);position:relative;overflow:hidden;}}
    .header::after{{content:'';position:absolute;top:0;left:0;right:0;bottom:0;
        background:linear-gradient(135deg,rgba(255,255,255,0.18) 0%,transparent 60%);
        pointer-events:none;border-radius:16px;}}
    .header h1{{font-family:{font_title};font-size:22px;color:white;text-shadow:1px 1px 2px rgba(0,0,0,0.1);}}
    .header .sub{{font-size:11px;color:rgba(255,255,255,0.9);font-weight:600;}}
    .header .pg{{font-size:10px;color:rgba(255,255,255,0.7);background:rgba(255,255,255,0.2);padding:3px 10px;border-radius:12px;}}"""
    elif header_style == "flat_block":
        _header = f"""
    .header{{background:{t['primary']};border-radius:0;padding:12px 20px;margin-bottom:14px;margin-right:32px;
        display:flex;justify-content:space-between;align-items:center;}}
    .header h1{{font-family:{font_title};font-size:20px;color:white;font-weight:700;}}
    .header .sub{{font-size:11px;color:rgba(255,255,255,0.85);font-weight:500;}}
    .header .pg{{font-size:10px;color:rgba(255,255,255,0.7);background:rgba(255,255,255,0.15);padding:3px 10px;border-radius:3px;}}"""
    elif header_style == "minimal_line":
        _header = f"""
    .header{{background:transparent;border-bottom:3px solid {t['primary']};padding:8px 0 10px;
        margin-bottom:14px;margin-right:32px;display:flex;justify-content:space-between;align-items:flex-end;}}
    .header h1{{font-family:{font_title};font-size:20px;color:{t['primary']};font-weight:700;}}
    .header .sub{{font-size:11px;color:{t['accent']};font-weight:600;}}
    .header .pg{{font-size:10px;color:{t['accent']};font-weight:600;}}"""
    elif header_style == "side_accent":
        _header = f"""
    .header{{background:{t['light']};border-left:5px solid {t['primary']};border-radius:0 {brad} {brad} 0;
        padding:12px 20px;margin-bottom:14px;margin-right:32px;
        display:flex;justify-content:space-between;align-items:center;}}
    .header h1{{font-family:{font_title};font-size:20px;color:{t['primary']};font-weight:700;}}
    .header .sub{{font-size:11px;color:{t['text']};font-weight:600;opacity:0.8;}}
    .header .pg{{font-size:10px;color:{t['accent']};font-weight:700;}}"""
    else:  # dark_card
        _header = f"""
    .header{{background:{t['light']};border:1px solid {t['primary']}55;border-radius:8px;
        padding:14px 22px;margin-bottom:14px;margin-right:32px;
        display:flex;justify-content:space-between;align-items:center;
        box-shadow:0 2px 12px rgba(0,0,0,0.3);}}
    .header h1{{font-family:{font_title};font-size:22px;color:{t['primary']};font-weight:600;letter-spacing:1px;}}
    .header .sub{{font-size:11px;color:{t['accent']};font-weight:500;letter-spacing:0.5px;}}
    .header .pg{{font-size:10px;color:{t['primary']};font-weight:600;}}"""

    # ── 체크박스 ──
    _cb_r = {"rounded": "4px", "circle": "50%", "square": "0", "diamond": "2px"}.get(cb_style, "4px")
    _cb_x = "transform:rotate(45deg);margin-right:10px;" if cb_style == "diamond" else ""
    _checkbox = (f".cb{{display:inline-block;width:14px;height:14px;border:1.5px solid {t['accent']};"
                 f"border-radius:{_cb_r};margin-right:6px;vertical-align:middle;background:{t['light']};{_cb_x}}}")

    # ── 섹션 타이틀 ──
    if sec_div == "underline":
        _sec = (f".section-title{{font-family:{font_accent};font-weight:700;font-size:13px;"
                f"color:{t['primary']};text-transform:uppercase;letter-spacing:1.5px;"
                f"margin:12px 0 6px;padding-bottom:4px;border-bottom:2px solid {t['light']};}}")
    elif sec_div == "left_bar":
        _sec = (f".section-title{{font-family:{font_accent};font-weight:700;font-size:13px;"
                f"color:{t['primary']};text-transform:uppercase;letter-spacing:1px;"
                f"margin:12px 0 6px;padding:2px 0 2px 10px;border-left:4px solid {t['primary']};}}")
    elif sec_div == "pill_badge":
        _sec = (f".section-title{{font-family:{font_accent};font-weight:700;font-size:11px;"
                f"color:white;text-transform:uppercase;letter-spacing:1.5px;"
                f"margin:10px 0 6px;padding:3px 12px;background:{t['primary']};"
                f"border-radius:20px;display:inline-block;}}")
    else:  # plain
        _sec = (f".section-title{{font-family:{font_accent};font-weight:800;font-size:14px;"
                f"color:{t['primary']};text-transform:uppercase;letter-spacing:2px;margin:14px 0 6px;}}")

    return f"""
    @import url('{font_url}');

    @page {{ size: letter; margin: 0; }}
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}

    body {{
        font-family: {font_body};
        background: {t['bg']};
        color: {t['text']};
    }}

    .page {{
        width: 8.5in;
        height: 11in;
        padding: 0.5in 0.5in 0.5in 0.4in;
        page-break-after: always;
        position: relative;
        overflow: hidden;
        background-color: {t['bg']};
        background-image: {_bg_img};
        background-size: {_bg_sz};
    }}
    .page:last-child {{ page-break-after: auto; }}

    /* ── 사이드 탭 ── */
    .side-tabs {{
        position: absolute; right: 0; top: 0.8in;
        display: flex; flex-direction: column; gap: 1px; z-index: 10;
    }}
    .side-tab {{
        width: 28px; height: 32px; border-radius: 0 8px 8px 0;
        display: flex; align-items: center; justify-content: center;
        font-family: {font_body}; font-size: 7px; font-weight: 600;
        color: {t['text']}; writing-mode: vertical-rl; text-orientation: mixed; opacity: 0.7;
    }}
    .side-tab.active {{ width: 34px; opacity: 1; font-weight: 700; box-shadow: -2px 0 4px rgba(0,0,0,0.08); }}

    /* ── 코너 장식 ── */
    {_corner}

    /* ── 헤더 ── */
    {_header}

    /* ── 섹션 타이틀 ── */
    {_sec}

    /* ── 체크박스 ── */
    {_checkbox}

    /* ── 입력 라인 ── */
    .input-line {{
        border-bottom: 1.5px {line_sty} {t['line']};
        min-height: 20px; margin: 3px 0;
    }}

    /* ── 캘린더 그리드 ── */
    .cal-grid {{
        display: grid; grid-template-columns: repeat(7, 1fr);
        gap: 1px; background: {t['line']};
        border-radius: {brad}; overflow: hidden; margin-right: 30px;
    }}
    .cal-hdr {{
        background: {t['primary']}; color: white;
        font-family: {font_body}; font-weight: 600; font-size: 10px;
        text-align: center; padding: 6px 2px;
    }}
    .cal-day {{
        background: {t['bg']}E8; min-height: 55px; padding: 3px 5px; font-size: 10px;
    }}
    .cal-day-num {{
        font-family: {font_body}; font-weight: 700; font-size: 11px; color: {t['primary']};
    }}
    .cal-empty {{ background: {t['bg']}; }}

    /* ── 주간 박스 ── */
    .week-grid {{
        display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-right: 30px;
    }}
    .day-box {{
        border: 1.5px solid {t['line']}; border-radius: {brad};
        padding: 8px 10px; background: {t['bg']}CC; min-height: 90px;
    }}
    .day-box h3 {{
        font-family: {font_accent}; font-weight: 700; font-size: 12px;
        color: {t['primary']}; margin-bottom: 4px; padding-bottom: 3px;
        border-bottom: 1px solid {t['light']};
    }}
    .day-line {{ border-bottom: 1px {line_sty} {t['line']}; height: 18px; }}

    /* ── 푸터 ── */
    .footer {{
        position: absolute; bottom: 0.3in; left: 0.4in; right: 0.5in;
        display: flex; justify-content: space-between;
        font-size: 8px; color: {t['accent']}88;
        border-top: 1px dashed {t['line']}; padding-top: 4px;
    }}
    .footer .brand {{ color: {t['accent']}; font-weight: 700; }}

    /* ── 커버 ── */
    .cover {{
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        text-align: center; background: {t['gradient']};
    }}
    .cover-frame {{
        position: absolute; top: 0.45in; left: 0.45in; right: 0.45in; bottom: 0.45in;
        border: 1.5px solid rgba(255,255,255,0.35); border-radius: 18px; pointer-events: none;
    }}
    .cover-frame-inner {{
        position: absolute; top: 0.56in; left: 0.56in; right: 0.56in; bottom: 0.56in;
        border: 0.5px solid rgba(255,255,255,0.18); border-radius: 14px; pointer-events: none;
    }}
    .cover h1 {{
        font-family: {font_title}; font-size: 44px; font-weight: 700;
        color: white; text-shadow: 2px 2px 8px rgba(0,0,0,0.18);
        margin-bottom: 8px; letter-spacing: -0.5px; line-height: 1.15;
    }}
    .cover .sub {{
        font-family: {font_accent}; font-size: 17px;
        color: rgba(255,255,255,0.95); font-weight: 600;
        margin-bottom: 24px; letter-spacing: 0.8px;
    }}
    .cover .badge {{
        background: rgba(255,255,255,0.25); padding: 8px 24px; border-radius: 24px;
        font-size: 16px; color: white; font-weight: 700; margin-bottom: 30px;
    }}
    .cover .rainbow {{
        width: 180px; height: 5px;
        background: linear-gradient(90deg, #FF8FAB, #79ADDC, #ADF7B6, #FFEE93, #FFC09F);
        border-radius: 3px; margin: 14px auto;
    }}
    .cover .features {{ list-style: none; text-align: left; }}
    .cover .features li {{ font-family: {font_body}; font-size: 14px; color: rgba(255,255,255,0.95); margin-bottom: 8px; }}
    .cover .brand-bot {{ position: absolute; bottom: 1in; font-size: 13px; color: rgba(255,255,255,0.6); font-weight: 700; }}

    /* ── TOC ── */
    .toc-item {{
        display: flex; justify-content: space-between; align-items: center;
        padding: 8px 12px; margin: 3px 0; border-radius: {brad};
        font-family: {font_accent}; font-weight: 600; font-size: 13px;
    }}
    .toc-item:nth-child(even) {{ background: {t['light']}; }}
    .toc-dot {{ flex: 1; border-bottom: 1px dotted {t['line']}; margin: 0 10px; height: 12px; }}
    .toc-pg {{ color: {t['accent']}; font-family: {font_body}; font-weight: 700; }}
    """


def _side_tabs_html(active_month: int = 0) -> str:
    """Generate side tabs for all 12 months using current theme colors."""
    # 테마 탭 색상 우선 사용, 없으면 기본 팔레트
    tab_colors = _current_theme.get("tab_colors", [
        "#FFE5EC","#FFC2D1","#E8DFF5","#DAEAF6","#DDEDEA","#ADF7B6",
        "#FFEE93","#FFC09F","#F6BC66","#F6AC69","#D4AFB9","#ABC4FF",
    ])
    tabs = ""
    for i, mon in enumerate(MONTHS):
        active = " active" if (i + 1) == active_month else ""
        color = tab_colors[i % len(tab_colors)]
        tabs += f'<div class="side-tab{active}" style="background:{color}">{mon}</div>\n'
    return f'<div class="side-tabs">{tabs}</div>'


def _tab_color(idx: int) -> str:
    """Fallback tab color (테마 미설정 시)."""
    tab_colors = _current_theme.get("tab_colors", [
        "#FFE5EC","#FFC2D1","#E8DFF5","#DAEAF6","#DDEDEA","#ADF7B6",
        "#FFEE93","#FFC09F","#F6BC66","#F6AC69","#D4AFB9","#ABC4FF",
    ])
    return tab_colors[idx % len(tab_colors)]


def _make_header(title: str, sub: str = "", pg: int = 0,
                  total: int = 0, section: str = "") -> str:
    """SVG 아이콘 포함 섹션 헤더 HTML 생성."""
    icon = SECTION_ICONS.get(section, SECTION_ICONS.get(title, ""))
    pg_badge = f'<span class="pg">p.{pg}</span>' if pg else ""
    sub_html = f'<div class="sub">{sub}</div>' if sub else ""
    return f"""
    <div class="header">
        <div style="display:flex;align-items:center;gap:10px;">
            {icon}
            <div>
                <h1>{title}</h1>
                {sub_html}
            </div>
        </div>
        {pg_badge}
    </div>"""


def _page_frame(content: str, month: int = 0) -> str:
    return f"""
    <div class="page">
        <div class="corner c-tl"></div><div class="corner c-tr"></div>
        <div class="corner c-bl"></div><div class="corner c-br"></div>
        {_side_tabs_html(month)}
        {content}
        <div class="footer">
            <span>© DailyPrintHaus</span>
            <span class="brand">dailyprinthaus.etsy.com</span>
        </div>
    </div>
    """


def _cover_html(title: str, subtitle: str, pages: int, style: int = 1) -> str:
    """Generate one of 10 distinct cover designs using current theme colors."""
    t = _current_theme
    p, a, li, bg, gr = t["primary"], t["accent"], t["light"], t["bg"], t["gradient"]

    _features = [
        f"📖 {pages}+ Pages",
        "✦ Undated · Use Any Year",
        "🔗 Clickable TOC Navigation",
        "📱 GoodNotes · Notability Ready",
        "⬇ Instant Download",
    ]
    feat_list = "".join(
        f'<li style="font-size:13px;color:rgba(255,255,255,0.92);margin-bottom:7px">{f}</li>'
        for f in _features
    )
    feat_list_dark = "".join(
        f'<li style="font-size:12px;color:{p};margin-bottom:6px;font-weight:600">{f}</li>'
        for f in _features
    )

    if style == 1:
        # ── Classic Centered (gradient bg, double frame, feature list) ──
        return f"""
        <div class="page cover">
            <div class="cover-frame"></div><div class="cover-frame-inner"></div>
            <h1 style="font-family:\'Playfair Display\',serif;font-size:44px;color:white;
                text-shadow:2px 2px 8px rgba(0,0,0,0.18);margin-bottom:8px;line-height:1.15">{title}</h1>
            <p style="font-family:\'Quicksand\',sans-serif;font-size:17px;color:rgba(255,255,255,0.95);
                font-weight:600;margin-bottom:24px;letter-spacing:0.8px">{subtitle}</p>
            <div style="background:rgba(255,255,255,0.25);padding:8px 24px;border-radius:24px;
                font-size:15px;color:white;font-weight:700;margin-bottom:28px">📖 {pages}+ Pages</div>
            <div style="width:180px;height:5px;background:linear-gradient(90deg,#FF8FAB,#79ADDC,#ADF7B6,#FFEE93,#FFC09F);
                border-radius:3px;margin:0 auto 20px"></div>
            <ul style="list-style:none;text-align:left">{feat_list}</ul>
            <div style="position:absolute;bottom:1in;font-size:13px;color:rgba(255,255,255,0.6);font-weight:700">DailyPrintHaus</div>
        </div>"""

    elif style == 2:
        # ── Minimal Bold (white bg, large color top block, clean typography) ──
        return f"""
        <div class="page" style="background:{bg};display:flex;flex-direction:column;align-items:stretch;padding:0;overflow:hidden">
            <div style="background:{gr};height:3.5in;display:flex;flex-direction:column;
                align-items:center;justify-content:center;padding:0.4in 0.5in;position:relative">
                <div style="position:absolute;bottom:-30px;left:0;right:0;height:60px;
                    background:{bg};border-radius:50% 50% 0 0/60px 60px 0 0"></div>
                <h1 style="font-family:\'Playfair Display\',serif;font-size:46px;color:white;
                    text-align:center;line-height:1.1;text-shadow:1px 2px 6px rgba(0,0,0,0.15)">{title}</h1>
            </div>
            <div style="flex:1;display:flex;flex-direction:column;align-items:center;
                justify-content:center;padding:0.5in 0.6in">
                <div style="width:60px;height:3px;background:{p};border-radius:2px;margin-bottom:16px"></div>
                <p style="font-family:\'Quicksand\',sans-serif;font-size:15px;color:{p};
                    font-weight:700;text-align:center;letter-spacing:1px;margin-bottom:24px">{subtitle}</p>
                <ul style="list-style:none;width:100%">{feat_list_dark}</ul>
                <div style="margin-top:20px;font-size:11px;color:{a};font-weight:700;letter-spacing:2px">DAILYPRINTHAUS</div>
            </div>
        </div>"""

    elif style == 3:
        # ── Botanical (white bg, large statement botanical SVG, elegant serif) ──
        botanical_svg = f"""<svg style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none"
            viewBox="0 0 816 1056" fill="none" xmlns="http://www.w3.org/2000/svg">
          <!-- large left branch -->
          <ellipse cx="-20" cy="300" rx="160" ry="70" fill="{p}" opacity="0.18" transform="rotate(-40 -20 300)"/>
          <ellipse cx="60" cy="220" rx="130" ry="55" fill="{p}" opacity="0.15" transform="rotate(-55 60 220)"/>
          <ellipse cx="120" cy="160" rx="100" ry="45" fill="{a}" opacity="0.2" transform="rotate(-65 120 160)"/>
          <ellipse cx="30" cy="380" rx="150" ry="60" fill="{a}" opacity="0.12" transform="rotate(-30 30 380)"/>
          <path d="M-30 400 Q100 280 180 100" stroke="{p}" stroke-width="3" fill="none" opacity="0.35"/>
          <!-- large right branch -->
          <ellipse cx="836" cy="750" rx="160" ry="70" fill="{p}" opacity="0.18" transform="rotate(140 836 750)"/>
          <ellipse cx="756" cy="830" rx="130" ry="55" fill="{p}" opacity="0.15" transform="rotate(125 756 830)"/>
          <ellipse cx="696" cy="890" rx="100" ry="45" fill="{a}" opacity="0.2" transform="rotate(115 696 890)"/>
          <ellipse cx="786" cy="670" rx="150" ry="60" fill="{a}" opacity="0.12" transform="rotate(150 786 670)"/>
          <path d="M846 656 Q716 776 636 956" stroke="{p}" stroke-width="3" fill="none" opacity="0.35"/>
          <!-- small accent leaves -->
          <ellipse cx="700" cy="120" rx="70" ry="30" fill="{a}" opacity="0.15" transform="rotate(30 700 120)"/>
          <ellipse cx="730" cy="90" rx="55" ry="22" fill="{p}" opacity="0.12" transform="rotate(45 730 90)"/>
          <ellipse cx="116" cy="936" rx="70" ry="30" fill="{a}" opacity="0.15" transform="rotate(-150 116 936)"/>
        </svg>"""
        return f"""
        <div class="page" style="background:{bg};position:relative;overflow:hidden;
            display:flex;flex-direction:column;align-items:center;justify-content:center">
            {botanical_svg}
            <div style="position:relative;z-index:2;text-align:center;padding:0 1.2in">
                <div style="width:50px;height:2px;background:{p};margin:0 auto 20px;border-radius:1px"></div>
                <h1 style="font-family:\'Playfair Display\',serif;font-size:46px;color:{p};
                    font-style:italic;line-height:1.1;margin-bottom:14px">{title}</h1>
                <div style="width:100px;height:1px;background:{a};margin:16px auto"></div>
                <p style="font-family:\'Quicksand\',sans-serif;font-size:14px;color:{p};
                    font-weight:600;letter-spacing:2px;text-transform:uppercase;
                    opacity:0.75;margin-bottom:28px">{subtitle}</p>
                <ul style="list-style:none;text-align:left;display:inline-block;margin-bottom:24px">{feat_list_dark}</ul>
                <div style="font-size:10px;color:{a};letter-spacing:3px;font-weight:700">DAILYPRINTHAUS</div>
            </div>
        </div>"""

    elif style == 4:
        # ── Split Layout (true side-by-side via absolute positioning) ──
        return f"""
        <div class="page" style="background:{bg};padding:0;overflow:hidden;position:relative">
            <!-- Left colored panel: absolute 45% width, full height -->
            <div style="position:absolute;top:0;left:0;width:45%;height:100%;
                background:{gr};display:flex;flex-direction:column;
                align-items:center;justify-content:center;padding:0.5in 0.25in">
                <div style="writing-mode:vertical-rl;transform:rotate(180deg);
                    font-family:\'Playfair Display\',serif;font-size:36px;color:white;
                    font-weight:700;text-shadow:1px 1px 8px rgba(0,0,0,0.2);
                    line-height:1.15;text-align:center">{title}</div>
                <div style="position:absolute;bottom:0.35in;font-size:10px;
                    color:rgba(255,255,255,0.55);letter-spacing:2px;font-weight:700">DAILYPRINTHAUS</div>
            </div>
            <!-- Right content panel: starts at 45% -->
            <div style="position:absolute;top:0;left:45%;right:0;height:100%;
                display:flex;flex-direction:column;justify-content:center;padding:0.4in 0.35in">
                <div style="width:36px;height:4px;background:{p};border-radius:2px;margin-bottom:18px"></div>
                <p style="font-family:\'Quicksand\',sans-serif;font-size:12px;color:{p};
                    font-weight:700;letter-spacing:1.5px;text-transform:uppercase;
                    margin-bottom:18px;line-height:1.4">{subtitle}</p>
                <ul style="list-style:none;margin-bottom:22px">{feat_list_dark}</ul>
                <div style="background:{li};border-radius:10px;padding:10px 14px;
                    font-size:12px;color:{p};font-weight:700;text-align:center;
                    border:1px solid {a}44">📖 {pages}+ Pages Included</div>
            </div>
        </div>"""

    elif style == 5:
        # ── Geometric (bold white polygon shapes, strong visual contrast) ──
        geo_svg = f"""<svg style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none"
            viewBox="0 0 816 1056" fill="none">
          <polygon points="0,0 400,0 280,320 0,220" fill="rgba(255,255,255,0.12)"/>
          <polygon points="816,0 816,380 540,260 680,0" fill="rgba(255,255,255,0.09)"/>
          <polygon points="0,1056 360,1056 240,740 0,840" fill="rgba(255,255,255,0.1)"/>
          <polygon points="816,1056 816,680 500,800 600,1056" fill="rgba(255,255,255,0.08)"/>
          <polygon points="200,0 600,0 700,200 100,200" fill="rgba(255,255,255,0.06)"/>
          <circle cx="408" cy="528" r="260" fill="none" stroke="rgba(255,255,255,0.2)" stroke-width="2"/>
          <circle cx="408" cy="528" r="220" fill="none" stroke="rgba(255,255,255,0.1)" stroke-width="1"/>
          <line x1="0" y1="528" x2="816" y2="528" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
          <line x1="408" y1="0" x2="408" y2="1056" stroke="rgba(255,255,255,0.08)" stroke-width="1"/>
        </svg>"""
        return f"""
        <div class="page cover" style="position:relative">
            {geo_svg}
            <div style="position:relative;z-index:2;text-align:center;padding:0 0.7in">
                <div style="display:inline-block;background:rgba(255,255,255,0.15);
                    border:1px solid rgba(255,255,255,0.3);border-radius:6px;
                    padding:4px 16px;font-size:9px;color:white;letter-spacing:4px;
                    font-weight:700;text-transform:uppercase;margin-bottom:24px">DailyPrintHaus</div>
                <h1 style="font-family:\'Playfair Display\',serif;font-size:52px;color:white;
                    line-height:1.0;text-shadow:2px 4px 16px rgba(0,0,0,0.25);
                    margin-bottom:16px">{title}</h1>
                <div style="width:60px;height:3px;background:rgba(255,255,255,0.7);
                    margin:18px auto;border-radius:2px"></div>
                <p style="font-size:15px;color:rgba(255,255,255,0.9);font-weight:600;
                    letter-spacing:1px;margin-bottom:30px">{subtitle}</p>
                <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
                    {''.join(f'<span style="background:rgba(255,255,255,0.18);border:1px solid rgba(255,255,255,0.35);padding:6px 16px;border-radius:22px;font-size:11px;color:white;font-weight:700">{feat}</span>' for feat in [f"{pages}+ Pages", "Undated", "GoodNotes Ready", "Instant PDF"])}
                </div>
            </div>
        </div>"""

    elif style == 6:
        # ── Dark Elegant (deep overlay, light gold accents, luxury feel) ──
        return f"""
        <div class="page" style="background:linear-gradient(145deg,#1a1a2e,#16213e,#0f3460);
            padding:0;overflow:hidden;display:flex;flex-direction:column;
            align-items:center;justify-content:center;position:relative">
            <div style="position:absolute;top:0;left:0;right:0;bottom:0;
                background:radial-gradient(ellipse at 30% 40%,{p}22 0%,transparent 60%)"></div>
            <div style="position:absolute;top:0.4in;left:0.4in;right:0.4in;bottom:0.4in;
                border:1px solid {a}44;border-radius:16px"></div>
            <div style="position:absolute;top:0.55in;left:0.55in;right:0.55in;bottom:0.55in;
                border:0.5px solid {a}22;border-radius:12px"></div>
            <div style="position:relative;z-index:2;text-align:center;padding:0 0.7in">
                <div style="font-size:11px;color:{a};letter-spacing:5px;font-weight:700;
                    text-transform:uppercase;margin-bottom:22px">✦ DailyPrintHaus ✦</div>
                <h1 style="font-family:\'Playfair Display\',serif;font-size:46px;color:#f0e6d3;
                    font-style:italic;line-height:1.1;margin-bottom:14px;
                    text-shadow:0 2px 20px rgba(0,0,0,0.4)">{title}</h1>
                <div style="width:100px;height:1px;background:linear-gradient(90deg,transparent,{a},transparent);
                    margin:18px auto"></div>
                <p style="font-size:14px;color:{a}cc;font-weight:600;letter-spacing:2px;
                    text-transform:uppercase;margin-bottom:26px">{subtitle}</p>
                <div style="font-size:13px;color:#f0e6d388;font-weight:500">
                    {pages}+ Pages &nbsp;|&nbsp; Undated &nbsp;|&nbsp; Instant Download
                </div>
            </div>
            <div style="position:absolute;bottom:0.7in;font-size:9px;color:{a}66;letter-spacing:3px">PREMIUM DIGITAL PLANNER</div>
        </div>"""

    elif style == 7:
        # ── Watercolor Wash (soft blob shapes, airy and feminine) ──
        blobs = f"""<svg style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none" viewBox="0 0 816 1056" fill="none">
            <ellipse cx="100" cy="150" rx="200" ry="180" fill="{li}" opacity="0.7"/>
            <ellipse cx="700" cy="200" rx="180" ry="160" fill="{a}" opacity="0.35"/>
            <ellipse cx="750" cy="850" rx="220" ry="190" fill="{li}" opacity="0.6"/>
            <ellipse cx="80" cy="900" rx="190" ry="170" fill="{a}" opacity="0.3"/>
            <ellipse cx="408" cy="528" rx="300" ry="260" fill="{li}" opacity="0.2"/>
        </svg>"""
        return f"""
        <div class="page" style="background:{bg};position:relative;overflow:hidden;
            display:flex;flex-direction:column;align-items:center;justify-content:center">
            {blobs}
            <div style="position:relative;z-index:2;text-align:center;padding:0 0.5in">
                <h1 style="font-family:\'Playfair Display\',serif;font-size:48px;color:{p};
                    font-style:italic;line-height:1.1;margin-bottom:12px;
                    text-shadow:1px 1px 4px {a}44">{title}</h1>
                <div style="width:140px;height:2px;background:{gr};border-radius:1px;margin:16px auto"></div>
                <p style="font-family:\'Quicksand\',sans-serif;font-size:15px;color:{p};
                    font-weight:600;letter-spacing:1px;margin-bottom:28px;opacity:0.85">{subtitle}</p>
                <ul style="list-style:none;text-align:left;display:inline-block">{feat_list_dark}</ul>
                <div style="margin-top:22px;font-size:11px;color:{a};letter-spacing:3px;font-weight:700">DAILYPRINTHAUS</div>
            </div>
        </div>"""

    elif style == 8:
        # ── Typographic (huge outline letter BG, bold modern design) ──
        big_letter = title[0].upper() if title else "P"
        return f"""
        <div class="page" style="background:{gr};overflow:hidden;position:relative;
            display:flex;flex-direction:column;align-items:center;justify-content:center">
            <!-- Huge outline letter as background -->
            <div style="position:absolute;font-family:\'Playfair Display\',serif;font-size:680px;
                -webkit-text-stroke:3px rgba(255,255,255,0.22);color:transparent;
                line-height:0.85;top:50%;left:50%;
                transform:translate(-50%,-50%);pointer-events:none;font-weight:700;
                user-select:none">{big_letter}</div>
            <div style="position:relative;z-index:2;text-align:center;padding:0 0.5in">
                <div style="font-size:10px;color:rgba(255,255,255,0.6);letter-spacing:5px;
                    font-weight:700;text-transform:uppercase;margin-bottom:24px">DailyPrintHaus</div>
                <h1 style="font-family:\'Fredoka One\',cursive;font-size:52px;color:white;
                    line-height:1.05;text-shadow:3px 3px 10px rgba(0,0,0,0.2);
                    margin-bottom:10px">{title}</h1>
                <p style="font-size:16px;color:rgba(255,255,255,0.88);font-weight:600;
                    letter-spacing:0.5px;margin-bottom:30px">{subtitle}</p>
                <div style="display:flex;gap:0;border:1px solid rgba(255,255,255,0.4);border-radius:12px;overflow:hidden">
                    {''.join(f"""<div style="flex:1;padding:10px 6px;text-align:center;font-size:10px;color:white;font-weight:700;border-right:1px solid rgba(255,255,255,0.2)">{f}</div>""" for f in [f"{pages}+pg","Undated","PDF","GN Ready","Download"])}
                </div>
            </div>
        </div>"""

    elif style == 9:
        # ── Circle Frame (large decorative circle focal point, modern) ──
        return f"""
        <div class="page" style="background:{bg};position:relative;overflow:hidden;
            display:flex;flex-direction:column;align-items:center;justify-content:center">
            <div style="position:absolute;width:5.5in;height:5.5in;border-radius:50%;
                background:{gr};top:50%;left:50%;transform:translate(-50%,-50%);
                box-shadow:0 0 60px {a}55"></div>
            <div style="position:absolute;width:5.8in;height:5.8in;border-radius:50%;
                border:1px solid {a}44;top:50%;left:50%;transform:translate(-50%,-50%)"></div>
            <div style="position:relative;z-index:2;text-align:center;padding:0 1in">
                <h1 style="font-family:\'Playfair Display\',serif;font-size:44px;color:white;
                    font-style:italic;line-height:1.1;text-shadow:2px 2px 8px rgba(0,0,0,0.15);
                    margin-bottom:12px">{title}</h1>
                <div style="width:80px;height:2px;background:rgba(255,255,255,0.5);margin:14px auto"></div>
                <p style="font-size:14px;color:rgba(255,255,255,0.9);font-weight:600;
                    letter-spacing:1px;margin-bottom:20px">{subtitle}</p>
                <div style="font-size:12px;color:rgba(255,255,255,0.75)">📖 {pages}+ Pages · Undated PDF</div>
            </div>
            <div style="position:absolute;bottom:0.6in;font-size:10px;
                color:{p};letter-spacing:3px;font-weight:700">DAILYPRINTHAUS</div>
            <div style="position:absolute;top:0.5in;right:0.5in;width:60px;height:60px;
                border-radius:50%;background:rgba(255,255,255,0.15);display:flex;
                align-items:center;justify-content:center;font-size:11px;
                color:white;font-weight:700;text-align:center">PDF</div>
        </div>"""

    else:  # style == 10
        # ── Stripe Modern (diagonal stripe bg, asymmetric title block) ──
        stripe_svg = f'<svg style="position:absolute;top:0;left:0;width:100%;height:100%" viewBox="0 0 816 1056" fill="none"><rect width="816" height="1056" fill="{bg}"/><line x1="-100" y1="400" x2="916" y2="150" stroke="{li}" stroke-width="60" opacity="0.8"/><line x1="-100" y1="550" x2="916" y2="300" stroke="{li}" stroke-width="30" opacity="0.5"/><line x1="-100" y1="650" x2="916" y2="400" stroke="{li}" stroke-width="80" opacity="0.3"/></svg>'
        return f"""
        <div class="page" style="background:{bg};position:relative;overflow:hidden;padding:0">
            {stripe_svg}
            <div style="position:relative;z-index:2;height:100%;display:flex;flex-direction:column">
                <div style="background:{gr};flex:0 0 auto;padding:0.7in 0.6in 0.5in;position:relative">
                    <div style="font-size:10px;color:rgba(255,255,255,0.65);
                        letter-spacing:4px;font-weight:700;margin-bottom:14px">DAILYPRINTHAUS</div>
                    <h1 style="font-family:\'Playfair Display\',serif;font-size:48px;color:white;
                        line-height:1.05;text-shadow:2px 2px 8px rgba(0,0,0,0.15)">{title}</h1>
                </div>
                <div style="flex:1;display:flex;flex-direction:column;justify-content:center;
                    padding:0.4in 0.6in">
                    <p style="font-family:\'Quicksand\',sans-serif;font-size:15px;color:{p};
                        font-weight:700;letter-spacing:1px;margin-bottom:20px">{subtitle}</p>
                    <ul style="list-style:none;margin-bottom:24px">{feat_list_dark}</ul>
                    <div style="display:flex;gap:10px;align-items:center">
                        <div style="background:{p};color:white;padding:10px 22px;border-radius:10px;
                            font-size:13px;font-weight:700">📖 {pages}+ Pages</div>
                        <div style="font-size:11px;color:{a};font-weight:700">Instant Download</div>
                    </div>
                </div>
            </div>
        </div>"""


def _toc_html(sections: list, t: dict) -> str:
    items = ""
    for name, pg in sections:
        sec_id = name.lower().replace(" ", "-")
        items += f"""
        <div class="toc-item">
            <a href="#{sec_id}" style="color:inherit; text-decoration:none;
               display:flex; width:100%; align-items:center; gap:6px;">
                <span style="flex:1;">{name}</span>
                <span class="toc-dot" style="flex:1;"></span>
                <span class="toc-pg">{pg}</span>
            </a>
        </div>
        """
    return _page_frame(f"""
        <div class="header"><div><h1>📋 Table of Contents</h1>
        <div class="sub" style="color:rgba(255,255,255,0.85); font-size:10px; margin-top:2px;">
            ✦ Click any section to jump directly (digital PDF)
        </div></div></div>
        {items}
    """)


def _monthly_html(month_num: int, pg: int, total: int) -> str:
    month_name = MONTHS_FULL[month_num - 1]
    # Calendar grid
    days_hdr = "".join(f'<div class="cal-hdr">{d}</div>' for d in ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"])
    cal = calendar.monthcalendar(datetime.now().year, month_num)
    days = ""
    for week in cal:
        for day in week:
            if day == 0:
                days += '<div class="cal-day cal-empty"></div>'
            else:
                days += f'<div class="cal-day"><span class="cal-day-num">{day}</span></div>'

    # 니치별 Monthly Goals ghost text
    _MG: dict[str | None, list[str]] = {
        "ADHD":          ["Set 3 focus goals — not 10", "Schedule brain dump Sundays", "One habit to build this month"],
        "ADHD_teacher":  ["Prep all lesson plans by Friday", "One new ADHD strategy to try", "Student check-ins weekly"],
        "ADHD_nurse":    ["Prep shift bag night before", "One self-regulation strategy to test", "30-min debrief routine after shifts"],
        "anxiety":       ["One thing I will let go of", "3 grounding habits to practice", "Reduce one anxiety trigger"],
        "christian":     ["Scripture chapter to memorize", "Serve in one church role", "Daily quiet time consistency"],
        "christian_teacher": ["Faith theme for the classroom", "Pray over each student by name", "Scripture verse for bulletin board"],
        "sobriety":      ["Days sober target: ___", "Meeting attendance goal", "New sober coping skill to try"],
        "sobriety_mom":  ["Recovery goal for this month", "One mom self-care ritual", "Family sober activity to plan"],
        "mom":           ["Family priority this month", "One thing just for me", "Meal prep goal for the week"],
        "homeschool":    ["Curriculum unit to complete", "Field trip or project idea", "Reading goal for my child"],
        "nurse":         ["Wellness habit on shift days", "One boundary to protect", "CEU or skill to review"],
        "teacher":       ["Classroom goal this month", "One student to connect with", "Professional goal to work on"],
        "pregnancy":     ["Prenatal appointment to prep for", "Baby prep task to complete", "Self-care ritual for this trimester"],
        "entrepreneur":  ["Revenue target: $___", "One system to build this month", "Content creation goal"],
        "self_care":     ["One boundary to set", "Daily ritual to protect", "Self-care practice to start"],
        "caregiver":     ["Respite break to schedule", "One task to delegate", "Personal wellness goal"],
        "perimenopause": ["Symptom to track this month", "One lifestyle change to test", "Wellness appointment to book"],
        "cycle_syncing": ["Cycle phase to honor this month", "Movement goal per phase", "Nutrition focus for this cycle"],
        "glp1":          ["Weight loss goal this month", "Protein target: ___g/day", "Movement habit to build"],
        None:            ["Priority #1 this month", "Habit to build or break", "One thing to stop doing"],
    }
    _MN: dict[str | None, str] = {
        "ADHD": "What's on my mind (brain dump):",
        "anxiety": "Worries I'm releasing this month:",
        "christian": "Prayer focus this month:",
        "sobriety": "Recovery reflection:",
        "mom": "Family notes & reminders:",
        "nurse": "Work notes & reminders:",
        "teacher": "Classroom notes:",
        "pregnancy": "Symptoms & appointments:",
        "entrepreneur": "Business ideas & notes:",
        None: "Notes & reminders:",
    }
    GHOST = "color:#c0c0c0;font-style:italic;font-size:10px"
    _mg_items = _MG.get(_current_niche) or _MG[None]
    _note_label = _MN.get(_current_niche) or _MN[None]

    goals = ""
    for i, _gtxt in enumerate(_mg_items[:3]):
        goals += (f'<div style="margin:3px 0"><span class="cb"></span>'
                  f'<span style="{GHOST};display:inline-block;width:80%">{_gtxt}</span></div>')

    return _page_frame(f"""
        {_make_header(month_name, "Monthly Overview", pg, total, "Monthly")}
        <div class="cal-grid">{days_hdr}{days}</div>
        <div class="section-title" style="margin-right:30px">Monthly Goals</div>
        {goals}
        <div class="section-title" style="margin-right:30px">Notes</div>
        <div style="margin:3px 0;{GHOST}">{_note_label}</div>
        <div class="input-line"></div><div class="input-line"></div>
    """, month_num)


def _weekly_html(week_num: int, pg: int, total: int) -> str:
    # 니치별 요일 ghost text — 2줄 예시 + 2줄 빈 칸
    _WEEKLY_GHOST: dict[str | None, list[str]] = {
        "ADHD":           ["Focus block: 25min →", "Brain dump first →"],
        "ADHD_teacher":   ["Lesson plan: ___", "Student check-in →"],
        "ADHD_nurse":     ["Shift prep list →", "Meds/charting focus →"],
        "anxiety":        ["Grounding task →", "Worry release space →"],
        "christian":      ["Scripture for today →", "Prayer intention →"],
        "christian_teacher": ["Class devotional →", "Student prayer →"],
        "sobriety":       ["Sober day: ___", "Meeting/sponsor →"],
        "sobriety_mom":   ["Recovery check-in →", "Family win today →"],
        "mom":            ["Family priority →", "Self-care moment →"],
        "homeschool":     ["Lesson subject →", "Read-aloud pick →"],
        "nurse":          ["Shift goals →", "Patient care note →"],
        "teacher":        ["Lesson focus →", "Student shoutout →"],
        "pregnancy":      ["Symptoms today →", "Baby prep task →"],
        "entrepreneur":   ["Revenue task →", "Follow-up: ___"],
        "self_care":      ["Self-care ritual →", "Mood intention →"],
        "caregiver":      ["Care task: ___", "Personal break →"],
        "perimenopause":  ["Symptom log →", "Wellness habit →"],
        "cycle_syncing":  ["Cycle phase: ___", "Energy task match →"],
        "glp1":           ["Protein goal: ___g", "Movement: ___min"],
        None:             ["Top priority: ___", "Must-do today →"],
    }
    GHOST = "color:#c0c0c0;font-style:italic;font-size:9.5px"
    _glines = _WEEKLY_GHOST.get(_current_niche) or _WEEKLY_GHOST[None]

    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    boxes = ""
    for d in days[:7]:
        # ghost 2줄 + 빈 줄 2개
        lines = ""
        for _gl in _glines:
            lines += f'<div class="day-line" style="margin-bottom:1px"><span style="{GHOST}">{_gl}</span></div>'
        lines += "".join('<div class="day-line"></div>' for _ in range(2))
        boxes += f'<div class="day-box"><h3>{d}</h3>{lines}</div>'
    # 8th box = notes (niche-specific label)
    nc = NICHE_PAGE_CONTENT.get(_current_niche) or NICHE_PAGE_CONTENT[None]
    notes_lines = ""
    for _gl in _glines:
        notes_lines += f'<div class="day-line" style="margin-bottom:1px"><span style="{GHOST}">{_gl}</span></div>'
    notes_lines += "".join('<div class="day-line"></div>' for _ in range(2))
    boxes += f'<div class="day-box"><h3>{nc["weekly_note_label"]}</h3>{notes_lines}</div>'

    return _page_frame(f"""
        {_make_header(f"Week {week_num}", "Weekly Planner", pg, total, "Weekly")}
        <div class="week-grid">{boxes}</div>
    """)


def _daily_html(pg: int, total: int) -> str:
    nc = NICHE_PAGE_CONTENT.get(_current_niche) or NICHE_PAGE_CONTENT[None]

    # ── 샘플 데이터 (ghost text — 예시 내용, 실제 인쇄본에서 흐릿하게 보임) ──
    samples_list = NICHE_DAILY_SAMPLES.get(_current_niche) or NICHE_DAILY_SAMPLES[None]
    sample = samples_list[pg % len(samples_list)]
    GHOST = "color:#c0c0c0;font-style:italic;font-size:10px"

    priorities = ""
    for txt in sample["priorities"]:
        priorities += (
            f'<div style="margin:3px 0;margin-right:30px">'
            f'<span class="cb"></span> '
            f'<span style="{GHOST}">{txt}</span></div>'
        )

    schedule = ""
    for hour in range(7, 20):  # 7:00~19:00 — 13슬롯
        text = sample["schedule"].get(hour)
        content = (
            f'<span style="{GHOST};flex:1">{text}</span>'
            if text else
            '<span class="input-line" style="flex:1"></span>'
        )
        schedule += f"""
        <div style="display:flex;align-items:center;gap:8px;margin-right:30px;margin-bottom:1px">
            <span style="font-size:10px;font-weight:600;color:{_tab_color(hour%12)};min-width:40px">{hour:02d}:00</span>
            {content}
        </div>"""

    todo_items = "".join(
        f'<div style="margin:3px 0"><span class="cb"></span>'
        f'<span style="{GHOST};display:inline-block;width:75%">{t}</span></div>'
        for t in sample["todo"]
    )

    note_lines = "".join(
        f'<div style="margin:4px 0;{GHOST}">{n}</div>' if n else
        '<div class="input-line" style="margin:4px 0"></div>'
        for n in (sample["notes"] + [""])  # ghost 2줄 + 빈 줄 1개
    )

    t = _current_theme
    accent = t.get("primary", "#aaa")

    return _page_frame(f"""
        {_make_header("Daily Planner", nc["date_label"], pg, total, "Daily")}
        <div class="section-title" style="margin-right:30px">{nc["priorities_label"]}</div>
        {priorities}
        <div class="section-title" style="margin-right:30px">{nc["schedule_label"]}</div>
        {schedule}
        <div style="display:flex;gap:10px;margin-right:30px;margin-top:6px">
            <div style="flex:1">
                <div class="section-title">{nc["todo_label"]}</div>
                {todo_items}
            </div>
            <div style="flex:1">
                <div class="section-title">{nc["notes_label"]}</div>
                {note_lines}
            </div>
        </div>
        <div style="margin-top:8px;margin-right:30px;padding:10px 12px;border-radius:10px;background:rgba(0,0,0,0.025);border:1.5px solid {accent}22">
            {_build_niche_extra()}
        </div>
    """)


def _habit_tracker_html(pg: int, total: int) -> str:
    nc = NICHE_PAGE_CONTENT.get(_current_niche) or NICHE_PAGE_CONTENT[None]
    habit_names = nc.get("habit_names", [f"Habit {i+1}" for i in range(10)])

    days_hdr = "".join(f'<th style="font-size:7px;padding:2px;color:#999">{d}</th>' for d in range(1, 32))
    rows = ""
    for i, name in enumerate(habit_names[:10]):
        cells = "".join(f'<td style="width:14px;height:18px;border:1px solid {_tab_color(i)};border-radius:3px"></td>' for _ in range(31))
        rows += f'<tr><td style="font-size:9px;padding:4px 6px;font-weight:600;color:#666;min-width:115px">{name}</td>{cells}</tr>'

    return _page_frame(f"""
        {_make_header("Habit Tracker", "Track Your Daily Habits", pg, total, "Habit")}
        <div style="overflow-x:auto;margin-right:30px">
            <table style="border-collapse:separate;border-spacing:2px;width:100%">
                <tr><th></th>{days_hdr}</tr>
                {rows}
            </table>
        </div>
    """)


def _gratitude_html(pg: int, total: int) -> str:
    # 니치별 감사일기 ghost text — 섹션 줄마다 이탤릭 예시 표시
    _GRATITUDE_GHOST: dict[str | None, list[str]] = {
        "ADHD":          ["My brain found a creative solution", "Asked for help and it worked", "Completed ONE thing fully", "Body-double session helped", "Noticed a hyperfocus win", "Gave myself grace for mistakes"],
        "ADHD_teacher":  ["Student had a breakthrough moment", "Used a new ADHD strategy in class", "Remembered an IEP accommodation", "Kept calm during a chaotic lesson", "A parent email went well", "Survived the week with grace"],
        "ADHD_nurse":    ["Stayed focused through a long shift", "Caught something others missed", "Patient thanked me genuinely", "Self-medicated with a short walk", "Finished charting on time", "Asked for support when needed"],
        "anxiety":       ["Breathed through a hard moment", "Anxiety didn't stop me today", "Reached out to someone I trust", "Let go of what I can't control", "Found one thing that felt safe", "Accepted uncertainty for a moment"],
        "christian":     ["God's faithfulness this morning", "A scripture that spoke to me", "An answered prayer I witnessed", "Grace I didn't deserve today", "Community that lifted my spirit", "Felt God's presence in small things"],
        "christian_teacher": ["Student asked a faith question", "Guided a student with patience", "Found a Bible connection in lesson", "A colleague encouraged me", "My classroom felt peaceful today", "Prayed over my students"],
        "sobriety":      ["Another sober day — a real win", "Craving passed without giving in", "Sponsor/meeting helped me today", "Found joy without substances", "Body feeling clearer this week", "Proud moment I'll remember"],
        "sobriety_mom":  ["Stayed sober for my kids today", "My child saw me at my best", "Recovery community supported me", "Set a boundary without guilt", "A family moment I was present for", "Asked for help as a mom in recovery"],
        "mom":           ["My child laughed today", "A quiet 5 minutes just for me", "Dinner made it to the table", "Hugs that filled up my tank", "Said yes to something fun", "Felt like a good mom today"],
        "homeschool":    ["Lesson clicked for my child", "Learning happened unexpectedly", "My child asked a great question", "Found a free educational resource", "Flexible schedule worked beautifully", "Connected learning to real life"],
        "nurse":         ["Patient recovered well today", "Team worked together smoothly", "Caught a critical detail in time", "Colleague covered for me graciously", "Stayed calm in a hard moment", "Went home knowing I helped"],
        "teacher":       ["Student had a lightbulb moment", "Class was engaged and focused", "Parent positive feedback received", "Found a creative lesson idea", "Stayed calm during a tough moment", "Remembered why I love teaching"],
        "pregnancy":     ["Felt baby move today", "Body doing an amazing thing", "Partner supported me perfectly", "Nausea was milder today", "Milestone ultrasound went well", "Felt calm and hopeful about birth"],
        "entrepreneur":  ["Client said yes to the proposal", "Revenue goal hit today", "Solved a business problem solo", "Team member did incredible work", "Took a real break without guilt", "Vision for the business felt clear"],
        "self_care":     ["Prioritized myself without guilt", "Said no to protect my energy", "Body feels rested and nourished", "Made time for joy today", "Boundary held and it felt right", "Showed up for myself like a friend would"],
        "caregiver":     ["Found a moment of peace today", "Caree had a comfortable day", "Someone checked in on me", "Asked for respite without shame", "Managed a hard task with grace", "Felt proud of my patience"],
        "perimenopause": ["Energy was better than expected", "Symptom was manageable today", "Slept a bit better last night", "Found a strategy that helped", "Showed my body compassion", "Stayed grounded through a hot flash"],
        "cycle_syncing": ["Honored my phase's energy level", "Chose the right task for today", "Body gave me a clear signal", "Cycle tracking revealed a pattern", "Felt in sync with my rhythms", "Trusted my body's wisdom today"],
        "glp1":          ["Stayed on plan and felt good", "Protein goal hit without struggle", "Movement felt achievable today", "Non-scale victory worth noting", "Mindful eating moment happened", "Body changing — I see it now"],
        None:            ["Woke up with energy today", "Made progress on my goal", "Finished something I started", "A small unexpected kindness", "Felt fully present for a moment", "Grateful for the basics: health, home, hope"],
    }
    GHOST = "color:#c0c0c0;font-style:italic;font-size:10px"
    _ghost_pool = _GRATITUDE_GHOST.get(_current_niche) or _GRATITUDE_GHOST[None]
    _ghost_idx  = 0

    nc = NICHE_PAGE_CONTENT.get(_current_niche) or NICHE_PAGE_CONTENT[None]
    sections = nc.get("gratitude_sections", NICHE_PAGE_CONTENT[None]["gratitude_sections"])
    date_label = nc.get("date_label", "Date: _______________")

    content = ""
    for title, lines in sections:
        content += f'<div class="section-title" style="margin-right:30px">{title}</div>'
        for i in range(lines):
            if _ghost_idx < len(_ghost_pool):
                _gtxt = _ghost_pool[_ghost_idx]; _ghost_idx += 1
                content += (f'<div style="margin:4px 0;margin-right:30px;font-size:11px;color:#999">'
                            f'{i+1}. <span style="{GHOST}">{_gtxt}</span></div>')
            else:
                content += (f'<div style="margin:4px 0;margin-right:30px;font-size:11px;color:#999">'
                            f'{i+1}. <span class="input-line" style="display:inline-block;width:88%"></span></div>')

    return _page_frame(f"""
        {_make_header("Gratitude Journal", date_label, pg, total, "Gratitude")}
        {content}
    """)


def _budget_html(pg: int, total: int) -> str:
    income_rows = ""
    for item in ["Salary/Wages", "Side Income", "Other"]:
        income_rows += f'<div style="display:flex;gap:10px;margin:4px 0;margin-right:30px"><span style="min-width:120px;font-size:12px">{item}</span><span class="input-line" style="flex:1"></span></div>'

    expense_rows = ""
    for item in ["Housing", "Utilities", "Groceries", "Transport", "Insurance", "Dining Out", "Entertainment", "Subscriptions", "Savings", "Other"]:
        expense_rows += f'<div style="display:flex;gap:10px;margin:3px 0;margin-right:30px"><span style="min-width:120px;font-size:11px">{item}</span><span class="input-line" style="flex:1"></span></div>'

    return _page_frame(f"""
        {_make_header("Budget Tracker", "Monthly Income &amp; Expenses", pg, total, "Budget")}
        <div class="section-title" style="margin-right:30px">📈 Income</div>
        {income_rows}
        <div style="margin:6px 0;margin-right:30px;font-weight:700;font-size:13px;color:#2ECC71">Total Income: $__________</div>
        <div class="section-title" style="margin-right:30px">📉 Expenses</div>
        {expense_rows}
        <div style="margin:6px 0;margin-right:30px;font-weight:700;font-size:13px;color:#E74C3C">Total Expenses: $__________</div>
        <div style="margin:10px 0;margin-right:30px;font-weight:700;font-size:15px;color:#3498DB">Remaining: $__________</div>
    """)


def _meal_html(pg: int, total: int) -> str:
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    meals = ["Breakfast", "Lunch", "Dinner", "Snack"]
    hdr = "<th></th>" + "".join(f'<th style="font-size:10px;padding:6px;background:{_tab_color(i)};color:#555;font-weight:600">{m}</th>' for i, m in enumerate(meals))
    rows = ""
    for d in days:
        cells = "".join(f'<td style="border:1px solid #eee;padding:4px;min-height:30px;border-radius:4px"></td>' for _ in meals)
        rows += f'<tr><td style="font-size:11px;font-weight:700;padding:6px;color:#666">{d}</td>{cells}</tr>'

    grocery = ""
    for i in range(12):
        grocery += f'<div style="display:inline-block;width:30%;margin:2px 0"><span class="cb"></span><span class="input-line" style="display:inline-block;width:70%"></span></div>'

    return _page_frame(f"""
        {_make_header("Meal Planner", "Weekly Menu &amp; Grocery List", pg, total, "Meal")}
        <table style="width:calc(100% - 30px);border-collapse:separate;border-spacing:3px">
            <tr>{hdr}</tr>{rows}
        </table>
        <div class="section-title" style="margin-right:30px">🛒 Grocery List</div>
        {grocery}
    """)


def _notes_html(pg: int, total: int) -> str:
    lines = "".join('<div class="input-line"></div>' for _ in range(22))
    return _page_frame(f"""
        {_make_header("Notes", "", pg, total, "Notes")}
        <div style="margin-right:30px">{lines}</div>
    """)


def _yearly_overview_html(pg: int, total: int) -> str:
    """Year-at-a-glance: 12개 미니 달력 3x4 그리드 + 연간 목표."""
    t = _current_theme
    primary = t.get("primary", "#6B8F71")
    light   = t.get("light",   "#DDEDEA")
    line    = t.get("line",    "#D0E0D0")
    accent  = t.get("accent",  "#A8C5A0")
    year    = datetime.now().year

    mini_cals = ""
    for m in range(1, 13):
        month_name = MONTHS_FULL[m - 1][:3]
        cal = calendar.monthcalendar(year, m)
        day_headers = "".join(
            f'<div style="font-size:5.5px;font-weight:700;color:#aaa;text-align:center">{d}</div>'
            for d in ["M","T","W","T","F","S","S"]
        )
        day_cells = ""
        for week in cal:
            for day in week:
                if day == 0:
                    day_cells += '<div></div>'
                else:
                    day_cells += f'<div style="font-size:6.5px;text-align:center;color:#555;padding:1px 0">{day}</div>'

        mini_cals += f"""
        <div style="border:1.5px solid {line};border-radius:8px;padding:5px 6px;background:rgba(255,255,255,0.7)">
            <div style="font-family:Poppins,sans-serif;font-weight:700;font-size:10px;text-align:center;
                        color:{primary};margin-bottom:3px;text-transform:uppercase;letter-spacing:0.5px">{month_name}</div>
            <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:0">{day_headers}{day_cells}</div>
        </div>"""

    goal_rows = "".join(
        f'<div style="margin:4px 0;margin-right:30px"><span class="cb"></span>'
        f'<span class="input-line" style="display:inline-block;width:86%"></span></div>'
        for _ in range(4)
    )
    important_rows = "".join(
        f'<div style="display:flex;gap:8px;margin:3px 0;margin-right:30px">'
        f'<span style="font-size:11px;color:{accent};min-width:80px">___/___</span>'
        f'<span class="input-line" style="flex:1"></span></div>'
        for _ in range(4)
    )

    return _page_frame(f"""
        {_make_header("Year at a Glance", f"{year} Overview", pg, total, "Yearly Overview")}
        <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:5px;margin-right:32px;margin-bottom:10px">
            {mini_cals}
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-right:32px">
            <div>
                <div class="section-title">🎯 {year} Goals</div>
                {goal_rows}
            </div>
            <div>
                <div class="section-title">📌 Key Dates</div>
                {important_rows}
            </div>
        </div>
    """)


def _monthly_review_html(pg: int, total: int) -> str:
    """월별 리뷰/회고 페이지 -- 상위 1% 플래너 필수 구성."""
    t = _current_theme
    primary = t.get("primary", "#6B8F71")
    GHOST = "color:#c0c0c0;font-style:italic;font-size:10px"

    # 니치별 ghost text 샘플
    _REVIEW_SAMPLES = {
        "christian":        {"wins": ["Consistent morning devotional all month", "Led small group with confidence", "Memorized 3 new scriptures"],
                             "well": ["Daily prayer kept me grounded", "Leaned on community for support"],
                             "improve": ["More patience in difficult moments", "Deeper Bible study time"],
                             "goals": ["Read through Psalms", "Serve at church event", "30-day gratitude journal"]},
        "ADHD":             {"wins": ["Used time-blocks 4 weeks straight", "Finished a project before deadline", "Brain dumps helped me focus daily"],
                             "well": ["Morning routine stuck all month", "Dopamine rewards kept me motivated"],
                             "improve": ["Reduce phone distractions at work", "Better sleep schedule"],
                             "goals": ["Body double study sessions 3x/week", "Try Pomodoro for deep work", "Finish one backlog task/day"]},
        "anxiety":          {"wins": ["Completed worry journal every day", "Said no to overcommitment twice", "Slept 7+ hrs most nights"],
                             "well": ["Breathing exercises helped at work", "Kept schedule calm and predictable"],
                             "improve": ["Less scrolling news at night", "More gentle movement daily"],
                             "goals": ["5-min grounding ritual each morning", "One social plan per week", "Limit caffeine after 2pm"]},
        "sobriety":         {"wins": ["Hit 30-day milestone", "Identified 2 new coping strategies", "Attended 4 support meetings"],
                             "well": ["Trigger log revealed a key pattern", "Sober community kept me accountable"],
                             "improve": ["Call sponsor more proactively", "Build more sober friendships"],
                             "goals": ["Journal every evening", "Try a new sober hobby", "90-day streak target"]},
        "sobriety_mom":     {"wins": ["30 sober days + showed up for my kids", "Created a calm-down kit for hard moments", "Asked for help when I needed it"],
                             "well": ["Morning recovery ritual before kids wake up", "Family routine felt more stable"],
                             "improve": ["More patience during bedtime chaos", "Self-care before burnout hits"],
                             "goals": ["Weekly mom-group meeting", "20 min alone time daily", "Plan a sober family outing"]},
        "mom":              {"wins": ["Meal prepped 3 weeks in a row", "Protected 2 me-time blocks per week", "Kids' activities all coordinated"],
                             "well": ["Sunday planning session saved weekdays", "Family dinner routine is working"],
                             "improve": ["Delegate more household tasks", "Less guilt about rest"],
                             "goals": ["One date night this month", "Read 1 chapter/night before bed", "Prep school lunches on Sundays"]},
        "nurse":            {"wins": ["All shifts covered without burnout", "Post-shift debrief helped me decompress", "Self-care logged 18 of 30 days"],
                             "well": ["Meal prep saved time on long shift weeks", "Boundaries with overtime improved"],
                             "improve": ["More hydration on 12-hour shifts", "Decompress faster after tough cases"],
                             "goals": ["10-min walk after every shift", "Plan 1 vacation day per month", "Reach out to a colleague weekly"]},
        "teacher":          {"wins": ["Lesson plans prepped a week ahead", "Parent communication log kept current", "Used grade tracker consistently"],
                             "well": ["Sunday reset routine worked well", "Clear classroom routines reduced chaos"],
                             "improve": ["Grade papers same day when possible", "Better work-life boundary after 5pm"],
                             "goals": ["Connect with 1 student intentionally/week", "Try 1 new classroom strategy", "Leave on time 3x/week"]},
        "pregnancy":        {"wins": ["Tracked all symptoms and appointments", "Baby prep checklist 50% done", "Made time for daily gentle movement"],
                             "well": ["OB appointment notes organized well", "Partner communication about birth plan"],
                             "improve": ["More water and less caffeine", "Earlier bedtime in third trimester"],
                             "goals": ["Finish hospital bag packing", "Practice breathing exercises daily", "Write birth preferences letter"]},
        "entrepreneur":     {"wins": ["Hit monthly revenue goal", "Signed 2 new clients", "CEO time-blocks protected 3 weeks"],
                             "well": ["Morning deep work sessions productive", "Client follow-up system working"],
                             "improve": ["Batch similar tasks together", "Delegate admin work sooner"],
                             "goals": ["Launch email sequence", "Record 4 content pieces", "Review Q2 financial report"]},
        "caregiver":        {"wins": ["All appointments coordinated on time", "Respite break taken — no guilt", "Medication schedule error-free all month"],
                             "well": ["Care schedule kept family informed", "Morning check-in routine clicked"],
                             "improve": ["Ask for more help from siblings", "Don't skip my own doctor appointments"],
                             "goals": ["Schedule 2 respite breaks", "Join 1 caregiver support group", "Plan a 30-min solo outing weekly"]},
        "glp1":             {"wins": ["Injection schedule consistent all month", "Lost 4 lbs — celebrated non-scale wins", "Protein goal hit 20 of 30 days"],
                             "well": ["Weekly progress photos kept me motivated", "Meal prep reduced poor food choices"],
                             "improve": ["More water with each meal", "Walk 10 min after dinner consistently"],
                             "goals": ["Try 2 new high-protein recipes", "10,000 steps 4 days/week", "Monthly measurement check-in"]},
        None:               {"wins": ["Completed the project I've been putting off", "Kept consistent morning routine all month", "Connected meaningfully with someone I love"],
                             "well": ["Weekly planning session saved so much time", "Prioritizing rest actually increased my output"],
                             "improve": ["Less reactive, more intentional with phone", "Plan meals to reduce decision fatigue"],
                             "goals": ["Read 2 chapters/day", "Exercise 4x per week", "One creative project this month"]},
    }
    s = _REVIEW_SAMPLES.get(_current_niche) or _REVIEW_SAMPLES[None]

    def _ghost_lines(items, fallback_count):
        out = ""
        for i, txt in enumerate(items[:fallback_count]):
            out += (f'<div style="margin:4px 0;margin-right:32px;font-size:11px">{i+1}. '
                    f'<span style="{GHOST}">{txt}</span></div>')
        return out

    sections_html = [
        ("🌟 Top 3 Wins This Month",   _ghost_lines(s["wins"], 3)),
        ("📈 What Went Well?",          _ghost_lines(s["well"], 2)),
        ("🔄 What Could Be Improved?",  _ghost_lines(s["improve"], 2)),
        ("🎯 Goals for Next Month",     _ghost_lines(s["goals"], 3)),
    ]
    content = ""
    for title, ghost in sections_html:
        content += f'<div class="section-title" style="margin-right:32px">{title}</div>'
        content += ghost

    rating_stars = "".join(
        f'<div style="text-align:center">'
        f'<div style="font-size:11px;color:#999;margin-bottom:4px">{label}</div>'
        f'<div style="font-size:26px;letter-spacing:3px;color:{primary}">&#9733;&#9733;&#9733;&#9733;&#9733;</div></div>'
        for label in ["Health", "Work", "Relationships", "Finance", "Personal Growth"]
    )

    # 니치별 월 마무리 성찰 프롬프트 (Life Balance 아래 빈공간 활용)
    _CLOSE_PROMPTS: dict[str | None, tuple[str, str, str]] = {
        "ADHD":          ("One word for this month:", "What helped my focus most?", "Next month I will give myself grace about:"),
        "ADHD_teacher":  ("One word for this month:", "What classroom strategy worked?", "One thing I'll do differently:"),
        "ADHD_nurse":    ("One word for this month:", "What kept me grounded on hard shifts?", "Next month I'll protect:"),
        "anxiety":       ("One word for this month:", "What reduced my anxiety most?", "One worry I'm releasing:"),
        "christian":     ("One word for this month:", "Where did I see God's hand?", "My prayer focus next month:"),
        "christian_teacher": ("One word for this month:", "How did faith show up in my classroom?", "Verse to carry into next month:"),
        "sobriety":      ("One word for this month:", "What kept me sober?", "My recovery focus next month:"),
        "sobriety_mom":  ("One word for this month:", "What helped me most as a sober mom?", "Next month I will ask for help with:"),
        "mom":           ("One word for this month:", "Best family moment:", "One thing I'll do just for me:"),
        "homeschool":    ("One word for this month:", "What excited my child most?", "Topic to explore next month:"),
        "nurse":         ("One word for this month:", "What kept me from burnout?", "Next month I'll protect my:"),
        "teacher":       ("One word for this month:", "Proudest classroom moment:", "One thing I'll do differently:"),
        "pregnancy":     ("One word for this month:", "How am I feeling about the journey?", "Something I'm excited about:"),
        "entrepreneur":  ("One word for this month:", "Biggest business win:", "What I'll stop doing next month:"),
        "self_care":     ("One word for this month:", "Best self-care moment:", "One boundary I'll protect:"),
        "caregiver":     ("One word for this month:", "What gave me strength?", "Next month I'll ask for help with:"),
        "perimenopause": ("One word for this month:", "What symptom improved?", "Wellness focus next month:"),
        "cycle_syncing": ("One word for this month:", "Best phase for energy:", "What I'll sync differently:"),
        "glp1":          ("One word for this month:", "Non-scale victory:", "Nutrition focus next month:"),
        None:            ("One word for this month:", "What am I most proud of?", "One thing I'll carry into next month:"),
    }
    _cp = _CLOSE_PROMPTS.get(_current_niche) or _CLOSE_PROMPTS[None]

    closing_html = ""
    for _prompt in _cp:
        closing_html += (f'<div style="margin:5px 0;margin-right:32px;font-size:10.5px;color:#888">'
                         f'{_prompt} <span style="{GHOST}">___________________________</span></div>')

    return _page_frame(f"""
        {_make_header("Monthly Review", "Reflect · Learn · Grow", pg, total, "Monthly Review")}
        {content}
        <div class="section-title" style="margin-right:32px">⭐ Life Balance Rating</div>
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-right:32px;margin-top:6px">
            {rating_stars}
        </div>
        <div style="margin-top:10px">{closing_html}</div>
    """)


def _vision_board_html(pg: int, total: int) -> str:
    """비전보드 템플릿 -- 상위 셀러 차별화 요소."""
    t = _current_theme
    accent = t.get("accent", "#A8C5A0")
    light  = t.get("light",  "#DDEDEA")

    boxes = [
        ("💪 Health & Wellness", "My body goals..."),
        ("💼 Career & Work",     "My professional goals..."),
        ("<3️ Relationships",     "My relationship goals..."),
        ("💰 Financial Goals",   "My money goals..."),
        ("🌱 Personal Growth",   "Skills to learn..."),
        ("✈️ Travel Dreams",     "Places to visit..."),
    ]
    input_lines = '<div class="input-line"></div>' * 3
    boxes_html = ""
    for title, hint in boxes:
        boxes_html += f"""
        <div style="border:2px dashed {accent};border-radius:12px;padding:10px 12px;
                    background:rgba(255,255,255,0.6);min-height:110px">
            <div style="font-family:Quicksand,sans-serif;font-weight:700;font-size:11px;
                        color:#555;margin-bottom:6px">{title}</div>
            <div style="font-size:9px;color:#ccc;margin-bottom:4px">{hint}</div>
            {input_lines}
        </div>"""

    word_of_year = f"""
    <div style="border:2px solid {accent};border-radius:14px;padding:10px 16px;
                background:{light};margin-bottom:10px;margin-right:32px;text-align:center">
        <div style="font-family:Quicksand,sans-serif;font-weight:700;font-size:11px;color:#777;margin-bottom:4px">
            * My Word of the Year
        </div>
        <div style="border-bottom:2px solid {accent};min-height:28px;margin:0 40px"></div>
    </div>"""

    return _page_frame(f"""
        {_make_header("Vision Board", "Dream Big · Plan Smart", pg, total, "Vision Board")}
        {word_of_year}
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px;margin-right:32px">
            {boxes_html}
        </div>
    """)


def _project_tracker_html(pg: int, total: int) -> str:
    """프로젝트 트래커 -- 상위 1% 플래너 필수 구성."""
    t = _current_theme
    primary = t.get("primary", "#6B8F71")
    light   = t.get("light",   "#DDEDEA")
    line    = t.get("line",    "#D0E0D0")

    header_style = (f"background:{primary};color:white;font-family:Poppins,sans-serif;"
                    "font-weight:700;font-size:10px;padding:6px 8px;text-align:center")
    cell_style   = f"border:1px solid {line};padding:5px 8px;min-height:28px;font-size:10px"

    rows_html = ""
    for _ in range(8):
        rows_html += (f'<tr>'
                      f'<td style="{cell_style}"></td>'
                      f'<td style="{cell_style}"></td>'
                      f'<td style="{cell_style};text-align:center"></td>'
                      f'<td style="{cell_style};text-align:center">o</td>'
                      f'<td style="{cell_style}"></td>'
                      f'</tr>')

    notes_lines = "".join('<div class="input-line"></div>' for _ in range(3))

    return _page_frame(f"""
        {_make_header("Project Tracker", "Plan · Track · Accomplish", pg, total, "Project Tracker")}
        <table style="width:calc(100% - 32px);border-collapse:collapse;margin-bottom:10px">
            <tr>
                <th style="{header_style};width:30%">Project</th>
                <th style="{header_style};width:22%">Due Date</th>
                <th style="{header_style};width:14%">Priority</th>
                <th style="{header_style};width:14%">Status</th>
                <th style="{header_style};width:20%">Notes</th>
            </tr>
            {rows_html}
        </table>
        <div class="section-title" style="margin-right:32px">📌 Notes</div>
        <div style="margin-right:32px">{notes_lines}</div>
    """)


def _workout_log_html(pg: int, total: int) -> str:
    """Fitness planner: weekly workout log with sets/reps/weight tracking."""
    t = _current_theme
    days = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    day_cells = "".join(
        f'<th style="font-size:10px;padding:4px 2px;background:{_tab_color(i)};color:#555;'
        f'font-weight:700;text-align:center;border-radius:4px 4px 0 0">{d}</th>'
        for i, d in enumerate(days)
    )
    exercise_rows = ""
    for ex_i in range(8):
        day_inputs = "".join(
            f'<td style="border:1px solid #eee;padding:3px;text-align:center;'
            f'border-radius:3px;min-width:52px">'
            f'<div style="font-size:7px;color:#bbb">sets×reps</div>'
            f'<div style="border-bottom:1px solid #ddd;height:12px;margin:2px 2px 1px"></div>'
            f'<div style="font-size:7px;color:#bbb">kg/lbs</div></td>'
            for _ in days
        )
        exercise_rows += (
            f'<tr><td style="font-size:10px;padding:4px 6px;font-weight:600;color:#666;'
            f'min-width:110px;border-bottom:1px solid #f0f0f0">Exercise {ex_i+1}'
            f'<div class="input-line" style="margin-top:2px"></div></td>'
            f'{day_inputs}</tr>'
        )
    cardio_rows = ""
    for label in ["Distance (km)", "Duration (min)", "Calories"]:
        day_cells_c = "".join(
            f'<td style="border:1px solid #eee;padding:4px;border-radius:3px">'
            f'<span class="input-line" style="display:block;margin-top:2px"></span></td>'
            for _ in days
        )
        cardio_rows += (
            f'<tr><td style="font-size:10px;padding:4px 6px;color:#666;min-width:110px">'
            f'{label}</td>{day_cells_c}</tr>'
        )
    return _page_frame(f"""
        {_make_header("Workout Log", "Week of: _______________", pg, total, "Habit")}
        <table style="width:calc(100% - 30px);border-collapse:separate;border-spacing:2px;margin-bottom:10px">
            <tr><th style="text-align:left;font-size:9px;padding:4px;color:#999">Exercise</th>{day_cells}</tr>
            {exercise_rows}
        </table>
        <div class="section-title" style="margin-right:30px">🏃 Cardio Log</div>
        <table style="width:calc(100% - 30px);border-collapse:separate;border-spacing:2px">
            <tr><th></th>{day_cells}</tr>
            {cardio_rows}
        </table>
    """)


def _body_measurement_html(pg: int, total: int) -> str:
    """Fitness planner: body measurement & progress tracking page."""
    t = _current_theme
    measurements = [
        ("⚖️ Weight", "kg / lbs"), ("📏 Chest", "cm / in"), ("📏 Waist", "cm / in"),
        ("📏 Hips", "cm / in"), ("💪 Bicep (L)", "cm / in"), ("💪 Bicep (R)", "cm / in"),
        ("🦵 Thigh (L)", "cm / in"), ("🦵 Thigh (R)", "cm / in"),
        ("🏋️ Body Fat %", "%"), ("❤️ Resting HR", "bpm"),
    ]
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
              "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    month_hdrs = "".join(
        f'<th style="font-size:7px;padding:3px 1px;background:{_tab_color(i)};'
        f'color:#555;font-weight:700;text-align:center">{m}</th>'
        for i, m in enumerate(months)
    )
    rows = ""
    for label, unit in measurements:
        cells = "".join(
            f'<td style="border:1px solid #eee;padding:3px;text-align:center;'
            f'border-radius:3px;min-width:38px"><span class="input-line" '
            f'style="display:block;margin-top:4px"></span></td>'
            for _ in months
        )
        rows += (
            f'<tr><td style="font-size:9px;padding:4px 6px;font-weight:600;color:#666;'
            f'white-space:nowrap">{label}<span style="font-size:7px;color:#bbb;'
            f'margin-left:3px">({unit})</span></td>{cells}</tr>'
        )
    goal_lines = "".join(
        f'<div style="margin:5px 0;margin-right:30px">'
        f'<span style="font-size:10px;color:{t["primary"]};font-weight:600">'
        f'{"⚖️ Weight" if i==0 else "💪 Fitness" if i==1 else "🎯 Body"} Goal: </span>'
        f'<span class="input-line" style="display:inline-block;width:70%"></span></div>'
        for i in range(3)
    )
    return _page_frame(f"""
        {_make_header("Body Measurements", "Track Your Progress", pg, total, "Habit")}
        {goal_lines}
        <div style="overflow-x:auto;margin-right:30px;margin-top:8px">
            <table style="border-collapse:separate;border-spacing:2px;width:100%">
                <tr><th style="text-align:left;font-size:9px;color:#999;padding:4px">Measurement</th>
                {month_hdrs}</tr>
                {rows}
            </table>
        </div>
        <div style="margin-top:10px;margin-right:30px">
            <div class="section-title">📸 Progress Photos (Before / During / After)</div>
            <div style="display:flex;gap:8px;margin-top:4px">
                {''.join(f"""<div style="flex:1;height:80px;border:2px dashed {t["accent"]};border-radius:8px;display:flex;align-items:center;justify-content:center;color:#ccc;font-size:9px">{lbl}</div>""" for lbl in ["Month 1","Month 6","Month 12"])}
            </div>
        </div>
    """)


# ═══════════════════════════════════════════════════════════
# 니치별 Daily 페이지 샘플 데이터 (ghost text — 예시 내용)
# 3세트 로테이션 → 52페이지가 동일해 보이지 않도록
# ═══════════════════════════════════════════════════════════

NICHE_DAILY_SAMPLES: dict[str | None, list] = {
    None: [
        {
            "priorities": ["Finish project proposal draft", "Reply to 3 pending emails", "30-min walk after lunch"],
            "schedule":   {8: "Morning routine + coffee", 9: "Deep work block (no interruptions)", 12: "Lunch break", 14: "Team check-in", 17: "End-of-day review"},
            "todo":       ["Grocery run", "Call back Dr. Smith", "Read 20 min before bed"],
            "notes":      ["Remember: dentist appt Thursday", "Budget review due this Friday"],
        },
        {
            "priorities": ["Prepare slides for Friday meeting", "Clear inbox to zero", "Pick up dry cleaning"],
            "schedule":   {9: "Focus block — no phone", 11: "Client call (30 min)", 13: "Lunch + short walk", 15: "Admin tasks", 18: "Dinner prep"},
            "todo":       ["Pay utility bill", "Book car service", "Journal before bed"],
            "notes":      ["Workout clothes in car", "Water bottle refill × 3"],
        },
        {
            "priorities": ["Morning pages + intention setting", "Complete 2 key tasks before noon", "Connect with a friend today"],
            "schedule":   {7: "Morning routine", 10: "Deep work — most important task", 12: "Lunch + recharge", 16: "Admin & messages", 19: "Evening wind-down"},
            "todo":       ["Prep tomorrow's outfit", "Water plants", "Send thank-you note"],
            "notes":      ["This week's focus: finish Q2 review", "Low energy day → protect mornings"],
        },
    ],
    "mom": [
        {
            "priorities": ["School drop-off + pack lunches", "Meal prep for the week (Sunday reset)", "Protect 30 min of me-time"],
            "schedule":   {7: "Kids wake-up + breakfast chaos", 9: "School drop-off → coffee ☕", 12: "Errands + quick lunch", 15: "School pick-up", 18: "Dinner + homework help"},
            "todo":       ["RSVP to Emma's birthday party", "Restock snack drawer", "Schedule pediatrician appt"],
            "notes":      ["Soccer practice moved to 4 PM", "Dentist reminder: Tue 10 AM"],
        },
        {
            "priorities": ["Batch cook chicken + veggies", "Laundry (fold + put away!)", "Bedtime routine by 8 PM"],
            "schedule":   {8: "Me-time — coffee while it's hot", 10: "Grocery store run", 13: "Nap time / quiet hour", 16: "Snack + outdoor play", 19: "Kids in bed → exhale 😮‍💨"},
            "todo":       ["Order school supplies", "Write in gratitude journal", "Call Mom"],
            "notes":      ["Freezer meals saved 2 hrs this week!", "Self-care isn't selfish — refill your cup"],
        },
        {
            "priorities": ["Morning circle time with kids", "Send birthday gift for nephew", "Early bedtime — I need rest too"],
            "schedule":   {7: "Breakfast + pack bags", 9: "Workout while kids play", 11: "Learning activity together", 14: "Rest / downtime", 17: "Family dinner — phones away"},
            "todo":       ["Fill out permission slip", "Prep diaper bag", "Text carpool mom"],
            "notes":      ["Win today: actually ate a hot meal!", "Kids' shoes → next size up needed"],
        },
    ],
    "ADHD": [
        {
            "priorities": ["⏱ 25-min focus sprint: report draft", "💊 Take meds before 9 AM", "🎯 ONE thing moved forward today"],
            "schedule":   {8: "Meds + body doubling (cowork app)", 9: "🔴 Focus block — phone in drawer", 12: "Lunch + dopamine reset walk", 14: "Low-demand tasks + inbox", 16: "Brain dump & tomorrow plan"},
            "todo":       ["Set 3 phone alarms for meds", "Lay out tomorrow's clothes NOW", "5-min tidy before bed"],
            "notes":      ["Hyperfocus risk today: set hard stop at 3 PM", "Reward: 20 min gaming after focus block ✅"],
        },
        {
            "priorities": ["Break big task into 3 tiny steps", "Dopamine snack between tasks 🍓", "Stop work by 6 PM (no overrun)"],
            "schedule":   {9: "Task 1 only — time-box 30 min", 10: "Short break — movement!", 11: "Task 2 — body double if stuck", 14: "Admin doom pile (20 min timer)", 17: "Wind-down routine START"},
            "todo":       ["Lay out gym bag tonight", "Reply to 2 texts (not all!)", "Water + snack logged"],
            "notes":      ["External accountability → text Alex by 5 PM", "Today's dopamine reward: new playlist 🎵"],
        },
        {
            "priorities": ["Morning routine check (non-negotiable)", "Time-block the 3 tasks I keep avoiding", "End-of-day shutdown ritual"],
            "schedule":   {7: "Wake-up routine (posted on mirror)", 9: "Deep work — DO NOT DISTURB", 12: "Lunch away from desk", 15: "Flexible block (ADHD buffer)", 18: "Shutdown complete ✅"},
            "todo":       ["Refill pill organizer", "Set tomorrow's 3 intentions tonight", "Stretch for 10 min"],
            "notes":      ["If overwhelmed → pick just ONE task", "Progress, not perfection 💙"],
        },
    ],
    "anxiety": [
        {
            "priorities": ["🌿 Morning grounding (5 senses)", "One task I've been avoiding (tiny step)", "Evening wind-down by 9 PM"],
            "schedule":   {8: "Box breathing × 4 rounds", 9: "Gentle schedule — no overloading", 12: "Nourishing lunch + outside air", 15: "Small brave task (10 min only)", 18: "Phone off + wind-down ritual"},
            "todo":       ["Limit news to 10 min max", "Walk around the block", "Worry list → close the loop"],
            "notes":      ["Worry: write it, schedule it, release it", "Today's safe anchor: chamomile tea + book"],
        },
        {
            "priorities": ["Start day with 1 calming thing", "Work on 1 task at a time (no multitasking)", "Connect with someone safe today"],
            "schedule":   {9: "Mindful coffee — no phone", 10: "One task, one hour, then break", 13: "Lunch away from screen", 16: "Journal: today's brave moment", 20: "Lights low + no screens"},
            "todo":       ["5-min body scan before work", "Reply to one message I've been avoiding", "Gratitude: 3 tiny things"],
            "notes":      ["Anxiety lied to me again — I handled it", "Overwhelm signal → stop + breathe first"],
        },
        {
            "priorities": ["Gentle morning (no alarm chaos)", "Progress on one grounding habit", "Protect quiet time this evening"],
            "schedule":   {8: "Slow morning — no rushing", 10: "Manageable task block", 12: "Nourishing meal + short walk", 15: "Rest or gentle movement", 19: "Journaling + gratitude"},
            "todo":       ["Breathing exercise before meetings", "Drink water every hour", "Celebrate one small win today"],
            "notes":      ["Nervous system needs consistency", "It's okay to say no to protect your peace"],
        },
    ],
    "christian": [
        {
            "priorities": ["📖 Quiet time + Scripture reading", "Pray for _______ today", "One act of kindness or service"],
            "schedule":   {7: "Morning prayer + devotional", 9: "Work / responsibilities with purpose", 12: "Gratitude lunch pause", 15: "Scripture reflection (5 min)", 20: "Evening prayer + surrender"},
            "todo":       ["Bible chapter: Philippians 4", "Text encouragement to a friend", "Church volunteer sign-up"],
            "notes":      ["Verse for today: 'I can do all things through Christ...'", "Prayer request: ___________________"],
        },
        {
            "priorities": ["Start with prayer before anything else", "Live out today's Scripture verse", "Encourage one person intentionally"],
            "schedule":   {7: "Quiet time — God first", 9: "Work as worship — excellence today", 13: "Lunch: thankful pause", 17: "Family / community time", 21: "Night prayers + surrender the day"},
            "todo":       ["Write prayer journal entry", "Listen to worship playlist during commute", "Read 1 Proverbs chapter"],
            "notes":      ["God's plan is better than mine 🙏", "Who can I lift up today?"],
        },
        {
            "priorities": ["Devotional + listening prayer", "Serve faithfully in today's role", "Evening gratitude & reflection"],
            "schedule":   {6: "Rise + pray before the day starts", 9: "Work with integrity & purpose", 12: "Lunch — mindful, thankful", 15: "Check in: am I living my values?", 20: "Family devotional + bedtime prayer"},
            "todo":       ["Memorize this week's verse", "Give generously (time or gift)", "Sabbath rest planned for Sunday"],
            "notes":      ["Faith over fear today", "Pray first, plan second"],
        },
    ],
    "sobriety": [
        {
            "priorities": ["✅ Sober Day #___ — count it!", "Call or text sponsor today", "Identify today's trigger risk + plan"],
            "schedule":   {7: "Morning reflection + gratitude", 9: "Recovery meeting / step work", 12: "Sober-safe lunch spot", 15: "Check in with accountability partner", 19: "Evening wind-down: no bars route"},
            "todo":       ["Read daily reflection book", "Write 3 sober wins this week", "Plan weekend sober activity"],
            "notes":      ["Trigger today: _______________ → coping: ___", "HALT check: Hungry / Angry / Lonely / Tired?"],
        },
        {
            "priorities": ["Morning affirmation: I choose sobriety", "One recovery action today (meeting/step/call)", "Protect my evening routine"],
            "schedule":   {8: "Gratitude list (3 things)", 10: "Step work — 20 min focused", 13: "Sober lunch + walk", 17: "Avoid high-risk time block", 20: "Recovery reading + early bed"},
            "todo":       ["Journal: why I chose sobriety today", "Plan tomorrow's meals (avoid triggers)", "Text someone in recovery community"],
            "notes":      ["Sobriety date: _______________", "Today's mantra: One day at a time 🌅"],
        },
        {
            "priorities": ["Start day clean — celebrate it", "Service: help someone else today", "End day with gratitude, not regret"],
            "schedule":   {7: "Morning prayer / meditation", 9: "Productive work — purpose-driven", 12: "Healthy meal — body is a gift", 16: "Recovery meeting or call", 21: "Nighttime inventory: stay honest"},
            "todo":       ["Add to gratitude journal", "Write letter to future self (sober + thriving)", "Self-care: walk / bath / read"],
            "notes":      ["Craving passed — it always does 💪", "Who in recovery can I support today?"],
        },
    ],
    "nurse": [
        {
            "priorities": ["Pre-shift visual checklist ✓", "Patient safety top priority all shift", "Post-shift debrief + decompress"],
            "schedule":   {7: "Pre-shift prep + report", 8: "Morning assessment rounds", 12: "30-min lunch (actually take it!)", 15: "Afternoon meds + charting", 19: "End-of-shift handoff + sign out"},
            "todo":       ["Restock med cart supplies", "Follow up: Rm 214 labs pending", "Compression socks in locker"],
            "notes":      ["Charge nurse: Sarah (ext 2201)", "Incident report due by Friday"],
        },
        {
            "priorities": ["Self-care = patient safety (eat + hydrate!)", "Clear charting before end of shift", "One moment of human connection per patient"],
            "schedule":   {6: "Night shift wind-down debrief", 9: "Sleep — phone on silent", 14: "Wake + nourishing meal", 16: "Life admin (bills/appts)", 18: "Workout / fresh air before next shift"},
            "todo":       ["Book CEU course registration", "Meal prep for night shifts", "Call back union rep"],
            "notes":      ["Post-shift ritual: shoes off, shower, journal", "You saved lives today 💙 rest now"],
        },
        {
            "priorities": ["Medication double-check protocol", "Therapeutic communication with difficult case", "Leave work at work — decompress tonight"],
            "schedule":   {7: "Huddle + assignment review", 10: "High-acuity patient priority block", 13: "Lunch + 10-min feet-up break", 16: "Documentation sprint", 19: "Shift end: celebrate one win"},
            "todo":       ["Renew BLS certification (due next month)", "Submit PTO request", "Buy comfortable shoes (feet 😭)"],
            "notes":      ["Compassion fatigue check: ___/10", "Remember: you can't pour from an empty cup"],
        },
    ],
    "teacher": [
        {
            "priorities": ["Lesson plans finalized for the week", "Return graded essays to Period 3", "Parent email follow-up: Jake's progress"],
            "schedule":   {7: "Classroom setup + coffee", 8: "Period 1 — Math (engagement warm-up)", 12: "Lunch + quick grade batch", 14: "Period 5 — differentiation strategy", 16: "After-school: parent communication"},
            "todo":       ["Print tomorrow's worksheets", "Update gradebook by Friday", "Order new whiteboard markers"],
            "notes":      ["IEP meeting: Thursday 3 PM — prep materials", "Behavior plan review: Marcus + Jordan"],
        },
        {
            "priorities": ["Morning circle / community builder", "Small-group intervention (reading group)", "Self-care: leave by 4:30 today"],
            "schedule":   {8: "Morning meeting — class community", 9: "Literacy block — guided reading", 11: "Math centers (differentiated)", 13: "Lunch + 15-min break (you earned it)", 15: "Planning period — next week prep"},
            "todo":       ["Laminate centers for Monday", "Sub plans folder — update", "Send weekly parent newsletter"],
            "notes":      ["Celebration: 3 students hit their AR goals! 🎉", "Reminder: data team meeting Wednesday"],
        },
        {
            "priorities": ["Review assessment data (action plan)", "Engage disengaged student today (1-on-1)", "Grades submitted before weekend"],
            "schedule":   {7: "Coffee + mental prep (you've got this)", 9: "Project work time — circulate + coach", 12: "Lunch OFF campus (reset!)", 14: "PLC meeting — bring data", 16: "Grade batch + respond to 3 parent emails"},
            "todo":       ["Restock classroom supplies from closet", "Schedule observation debrief with admin", "Write one positive note to a student"],
            "notes":      ["This job is hard. You are making a difference.", "Boundary: no emails after 7 PM"],
        },
    ],
    "homeschool": [
        {
            "priorities": ["Morning circle + calendar time", "Math lesson + hands-on practice", "Nature study / outdoor learning"],
            "schedule":   {8: "Morning meeting — pledge, weather, news", 9: "Math: fractions unit (manipulatives)", 11: "Language arts: creative writing", 13: "Lunch + free reading", 14: "Science experiment 🔬"},
            "todo":       ["Grade yesterday's math worksheet", "Order new library books (hold list)", "Prep art supplies for Friday project"],
            "notes":      ["Emma: needs extra time on multiplication", "Co-op field trip permission slip due Fri"],
        },
        {
            "priorities": ["Read-aloud chapter + narration", "Complete history unit project", "PE / movement break × 2 today"],
            "schedule":   {9: "Bible / character study", 10: "History: timeline activity", 12: "Lunch + audiobook", 14: "Outdoor nature journal", 15: "Music practice (20 min)"},
            "todo":       ["Update portfolio with this week's work", "Plan next month's unit studies", "Co-op lesson prep (my turn Thursday)"],
            "notes":      ["Learning win: Jake read 3 chapters solo! 📚", "Curriculum fair next month — register"],
        },
        {
            "priorities": ["Assessment week: math & reading", "Keep routine light — rest is learning too", "Connect: field trip or museum visit"],
            "schedule":   {8: "Morning circle + gratitude", 10: "Reading assessment (1:1 with each child)", 12: "Lunch + quiet time", 14: "Geography: map activity", 16: "Free learning / interests"},
            "todo":       ["Pull next unit materials from binder", "Send monthly report to accountability group", "Organize art portfolio"],
            "notes":      ["Flexibility is a homeschool superpower 💪", "Today's vibe: slow + intentional"],
        },
    ],
    "self_care": [
        {
            "priorities": ["Morning ritual (non-negotiable)", "One thing purely for joy today", "Protect evening wind-down"],
            "schedule":   {7: "Wake slowly — no phone for 30 min", 8: "Morning ritual: journal + stretch + tea", 12: "Nourishing lunch — sit down & eat it", 17: "Movement: yoga / walk / dance", 20: "Glow routine + skincare ritual"},
            "todo":       ["Book massage / facial this month", "Prepare healthy snacks for the week", "Digital detox: no screens after 9 PM"],
            "notes":      ["Glow-up habit stack: water → stretch → journal", "Rest is productive. Recovery is progress."],
        },
        {
            "priorities": ["Honor my energy level today (no forcing)", "Nourish body: real food, real water", "One hour of pure pleasure (no guilt)"],
            "schedule":   {8: "Body scan — how do I feel today?", 9: "High-energy task while fresh", 12: "Lunch + sunlight break", 15: "Slow afternoon — creativity or rest", 19: "Evening ritual: bath + book + bed early"},
            "todo":       ["Order that book I've been wanting", "Schedule solo date this week", "Meal prep feel-good foods Sunday"],
            "notes":      ["Self-care isn't selfish — it's essential", "What does my body actually need right now?"],
        },
        {
            "priorities": ["Start day with something beautiful", "Move body in a way that feels good", "Sleep 8 hours tonight (set alarm now)"],
            "schedule":   {7: "Sunrise — watch it (5 min outside)", 9: "Creative or passion project block", 13: "Lunch with intention + gratitude", 16: "Walk or gentle movement", 21: "Lights dim + wind-down begins"},
            "todo":       ["Try one new recipe this week", "Unfollow 5 accounts that drain energy", "Write future self a love letter"],
            "notes":      ["Skin: hydrate from inside + outside today", "Boundary win this week: _______________"],
        },
    ],
    "pregnancy": [
        {
            "priorities": ["Take prenatal vitamin + iron", "Kick count: _____ kicks by noon", "Rest when body asks — no guilt"],
            "schedule":   {8: "Morning prenatal vitamin + ginger tea", 9: "Light movement: prenatal yoga / walk", 12: "Lunch: protein + iron-rich meal", 14: "Kick count + journal entry", 16: "Nap / feet up — reduce swelling"},
            "todo":       ["OB appointment prep: questions list", "Order hospital bag items", "Call insurance re: birth coverage"],
            "notes":      ["Week ___: _____________ is size of a ___", "Midwife callback: _______________"],
        },
        {
            "priorities": ["Hydration goal: 10 glasses today", "Nursery task: _______________", "Practice labor breathing techniques"],
            "schedule":   {9: "Prenatal class / video series", 11: "Nesting task (30 min only!)", 13: "Lunch + afternoon rest", 15: "Birth plan review", 18: "Evening walk (safe + gentle)"},
            "todo":       ["Pack one section of hospital bag", "Register for baby shower gifts", "Research pediatricians nearby"],
            "notes":      ["Sleep position: left side + pillow between knees", "Baby movement log: _______________"],
        },
        {
            "priorities": ["Celebrate today's pregnancy milestone", "Self-compassion: body is doing incredible work", "Delegate one thing I don't need to do"],
            "schedule":   {8: "Gentle wake-up + prenatal stretch", 10: "Appointment or admin task", 12: "Nutritious lunch — slow + seated", 15: "Sibling prep / partner connection time", 20: "Relaxation: guided meditation for birth"},
            "todo":       ["Write birth preferences document", "Freeze one postpartum meal", "Thank someone in my village today"],
            "notes":      ["You are growing a human being. That's everything.", "Next appointment: _______________"],
        },
    ],
    "entrepreneur": [
        {
            "priorities": ["Revenue-generating task FIRST (no admin)", "One customer/client touchpoint", "CEO debrief: what moved the needle today?"],
            "schedule":   {8: "Protect mornings — deep work only", 9: "Lead gen / sales block (revenue first)", 12: "Lunch + business podcast", 14: "Content / marketing batch", 17: "CEO review: wins, blockers, tomorrow"},
            "todo":       ["Follow up with 3 warm leads", "Post content (schedule queue)", "Check cash flow + invoices"],
            "notes":      ["This week's revenue goal: $_______________", "Bottleneck to remove: _______________"],
        },
        {
            "priorities": ["Launch / deliver one thing today", "Protect deep work: 2 hrs uninterrupted", "Systems over hustle — automate one thing"],
            "schedule":   {9: "CEO power hour — no distractions", 11: "Team Loom / async update", 13: "Lunch away from screen", 15: "Product / service work block", 18: "Gratitude + business journal"},
            "todo":       ["Review last week's metrics", "Delegate / automate one task", "CEO date: work ON the business, not IN it"],
            "notes":      ["Biggest leverage activity this week: ___", "Don't confuse busy with productive"],
        },
        {
            "priorities": ["Protect the vision: strategy over tactics", "Visible: show up for audience today", "Profit: review margins on _______________"],
            "schedule":   {7: "Morning CEO mindset routine", 9: "Money-making task — first 2 hrs", 12: "Lunch + reading (learning = investing)", 15: "Creative batch or planning block", 19: "Gratitude: 3 business wins today"},
            "todo":       ["Update financial tracker", "Reach out to potential collaborator", "Plan next 90-day sprint"],
            "notes":      ["Business breakthrough: _______________", "Reminder: done is better than perfect 🚀"],
        },
    ],
    "perimenopause": [
        {
            "priorities": ["🌿 Anti-inflammatory breakfast (no skipping)", "Track symptoms + energy level today", "Sleep prep: dim lights by 8:30 PM"],
            "schedule":   {7: "Gentle wake-up — no rushing", 9: "Movement: weight-bearing exercise", 12: "Hormone-friendly lunch + rest", 15: "Symptom log: mood / heat / energy", 19: "Magnesium + wind-down routine"},
            "todo":       ["Take supplements (Vit D + Mag + B12)", "Schedule DEXA scan (bone density check)", "Research HRT options — questions for Dr."],
            "notes":      ["Hot flash log: ___ times today / severity ___", "Sleep quality last night: ___/10"],
        },
        {
            "priorities": ["Reduce cortisol: protect morning quiet", "Nourish with protein at every meal", "One joyful thing today (non-negotiable)"],
            "schedule":   {8: "Morning walk — supports bone + mood", 10: "High-value task (peak cortisol window)", 13: "Protein-rich lunch + rest if needed", 16: "Gentle afternoon — no over-scheduling", 20: "Magnesium bath + early sleep"},
            "todo":       ["Order phytoestrogen-rich foods", "Book appointment with menopause specialist", "Cancel over-commitment (you can say no)"],
            "notes":      ["Brain fog moment: pause, breathe, hydrate", "Your body is transitioning — not failing you"],
        },
        {
            "priorities": ["Prioritize sleep above all else today", "Stress management: protect your nervous system", "Celebrate this season's wisdom"],
            "schedule":   {9: "Slow morning ritual — hormone reset", 11: "Work block (lighter load today)", 13: "Lunch + feet up", 15: "Walk outside — natural light for sleep", 21: "Bedtime routine start — 8-hr goal"},
            "todo":       ["Log night sweats / hot flashes in tracker", "Reach out to perimenopause support community", "Schedule 'me day' this month"],
            "notes":      ["Inflammation foods to avoid today: ___", "This too shall ease 🌿 you've got this"],
        },
    ],
    "cycle_syncing": [
        {
            "priorities": ["🌙 Identify today's cycle phase", "Match energy to phase-aligned tasks", "Seed cycling: today's seeds _______________"],
            "schedule":   {8: "Check cycle phase + plan accordingly", 9: "Phase-matched work (follicular: create / luteal: admin)", 12: "Phase-aligned meal + rest if needed", 15: "Movement for this phase (HIIT vs yin yoga)", 20: "Cycle journal + body check-in"},
            "todo":       ["Log cycle day in tracker", "Prep phase-aligned meals for tomorrow", "Research this phase's optimal nutrition"],
            "notes":      ["Cycle day: ___ / Phase: _______________", "Seed today: pumpkin / flax / sesame / sunflower"],
        },
        {
            "priorities": ["Honor today's energy (don't override it)", "Phase nutrition: _______________", "Body wisdom moment: what is she saying?"],
            "schedule":   {9: "Morning: cycle check + intentions", 10: "Creative / social (if follicular) or solo (if luteal)", 13: "Hormone-supportive lunch", 16: "Movement that matches my phase", 19: "Reflection + tomorrow's phase prep"},
            "todo":       ["Update cycle app / tracker", "Meal prep for luteal phase (complex carbs)", "Communicate needs to partner / family"],
            "notes":      ["How I feel vs how I expect to feel: ___", "Cramps/bloat: support with ___ today"],
        },
        {
            "priorities": ["Flow with, not against, my cycle today", "Adjust schedule for today's energy reality", "Nourish depleted minerals this phase"],
            "schedule":   {8: "Gentle wake-up — honor my body", 10: "Task matching: creative or grounding?", 12: "Iron-rich or hormone-balancing lunch", 15: "Short rest if luteal (it's not lazy)", 20: "Yoni steam / castor pack / rest ritual"},
            "todo":       ["Schedule lighter workload around period week", "Track symptoms for doctor appointment", "Connect with cycle syncing community"],
            "notes":      ["Cycle wisdom: _______________", "Body is intelligent. Listen before pushing."],
        },
    ],
    "caregiver": [
        {
            "priorities": ["💛 AM care routine for _______________", "Medication schedule (no misses today)", "My own basic needs: eat, drink, breathe"],
            "schedule":   {7: "Morning care: meds + vitals + breakfast", 9: "Activities / engagement time with loved one", 12: "Caregiver lunch (sit down — you need it)", 14: "Appointment / call / paperwork block", 17: "Evening care + family dinner"},
            "todo":       ["Refill prescription (_______________)", "Call insurance re: coverage question", "Schedule respite care for _____________"],
            "notes":      ["Care notes: mood today — ___/10, appetite ___", "Emergency contacts updated: ✅ / ❌"],
        },
        {
            "priorities": ["Safety check: fall risks, mobility, meds", "One moment of real connection today", "Accept help when offered (it's okay)"],
            "schedule":   {8: "Morning assessment + daily briefing", 10: "Therapy / PT appointment", 13: "Lunch together + gentle activity", 15: "Admin: insurance / forms / calls", 19: "Evening routine + check tomorrow's needs"},
            "todo":       ["Update care log for this week", "Research respite care options", "Self-care: I matter too — book ___ "],
            "notes":      ["Behavior note: ___ was agitated at ___", "I am doing enough. More than enough. 💛"],
        },
        {
            "priorities": ["Sustainable pace: you're a marathon, not sprint", "Medication organizer refilled for the week", "One thing that brings me joy today"],
            "schedule":   {7: "Early care tasks before family wakes", 9: "Care tasks + my own breakfast", 12: "Respite hour — rest or errand (NO guilt)", 15: "Care check-in + snack", 20: "Evening wind-down for both of us"},
            "todo":       ["Contact caregiver support group", "Write in care journal (feelings matter)", "Ask family for specific help with ___"],
            "notes":      ["Caregiver burnout check: ___ / 10", "You cannot pour from an empty vessel 🌿"],
        },
    ],
    "glp1": [
        {
            "priorities": ["💉 Injection day / dose tracking", "Protein goal: 100g+ (log every meal)", "Non-scale victory check-in today"],
            "schedule":   {8: "Morning weigh-in + log (same time daily)", 9: "Protein-first breakfast (30g+)", 12: "Lunch: protein + vegetables, slow eating", 15: "Hydration check + movement (10k steps)", 19: "Dinner + evening injection (if weekly schedule)"},
            "todo":       ["Refill GLP-1 prescription (auto-refill set?)", "Log meals in tracking app", "Before/after photo this week"],
            "notes":      ["Side effects today: nausea ___/10, fatigue ___/10", "Injection site rotation: _______________"],
        },
        {
            "priorities": ["Eat slowly — satiety signals are different now", "Hydration: 80+ oz today (prevents nausea)", "Strength training protects muscle on GLP-1"],
            "schedule":   {9: "Protein breakfast — don't skip (muscle loss!)", 11: "Walk or resistance workout", 13: "Small protein lunch + lots of water", 15: "Healthy snack if needed (don't force hunger)", 18: "Dinner before 7 PM — better sleep"},
            "todo":       ["Research: protein powder options", "Schedule DEXA scan (muscle + bone baseline)", "Join GLP-1 support community online"],
            "notes":      ["Weight this week: ___ lbs (trend matters, not daily)", "NSV today: _______________  🎉"],
        },
        {
            "priorities": ["Consistency > perfection on this journey", "Move body: strength + steps today", "Celebrate progress, not just the scale"],
            "schedule":   {8: "Morning log: weight + energy + mood", 10: "Workout: prioritize strength over cardio", 12: "Protein-packed lunch + mindful eating", 16: "Steps goal check + top-up walk", 19: "Reflect: how did body feel today?"},
            "todo":       ["Meal prep high-protein options for the week", "Blood work follow-up with doctor", "Before selfie + measurements update"],
            "notes":      ["Down ___ lbs total — incredible progress 💪", "Remind myself: this is a tool, I do the work"],
        },
    ],
    "ADHD_teacher": [
        {
            "priorities": ["⏱ Lesson plan time-blocked (not open-ended)", "💊 Meds before students arrive", "Transition cue set for every period change"],
            "schedule":   {7: "Meds + visual schedule review", 8: "Period 1 — hook/anchor activity ready", 12: "Lunch OFF campus (reset your nervous system)", 14: "Period 5 — low-demand (ADHD energy dip)", 16: "Brain dump before leaving school"},
            "todo":       ["Set phone timer for transitions", "Prep sub plans in advance (executive function buffer)", "Text accountability partner your end-of-day win"],
            "notes":      ["ADHD + teaching = double output — honor that", "Hyperfocus trap: set hard stop for grading at 5 PM"],
        },
        {
            "priorities": ["Prioritize high-energy teaching periods", "Reduce decision fatigue: batch grading time", "Leave school by ___ (hard boundary)"],
            "schedule":   {8: "Morning setup: visuals + supplies ready", 9: "High-engagement lesson (peak energy)", 11: "Small-group work (circulate + refocus)", 13: "Lunch + brief walk outside", 15: "Admin batch — timer 45 min only"},
            "todo":       ["Use lesson plan template (reduce cognitive load)", "Prep tomorrow's materials tonight", "Declutter desk: only today's papers out"],
            "notes":      ["Teaching win today: _______________", "ADHD superpower used: _______________"],
        },
        {
            "priorities": ["Execute, don't over-plan: one clear lesson goal", "Use movement breaks for students AND yourself", "Celebrate one student win publicly today"],
            "schedule":   {7: "Coffee + 5-min lesson mental rehearsal", 9: "Differentiated instruction block", 12: "Recharge lunch (you need it more than they know)", 14: "Flexible period — adapt, don't force", 16: "Quick shutdown routine before going home"},
            "todo":       ["Reduce paper trail — go digital where possible", "Schedule 5-min check-in with admin (stay visible)", "Journal: what worked, what to adjust"],
            "notes":      ["Remember: imperfect lesson taught > perfect lesson not taught", "Your ADHD brain sees what neurotypical teachers miss 💙"],
        },
    ],
    "ADHD_nurse": [
        {
            "priorities": ["Pre-shift checklist completed (non-negotiable)", "Meds on board before shift starts", "One patient safety double-check per hour"],
            "schedule":   {6: "Pre-shift: meds + visual checklist review", 7: "Handoff report — write key points down", 10: "Mid-shift check: am I behind? Recalibrate.", 12: "LUNCH — eat it, sit down, you need glucose", 15: "Afternoon meds + charting sprint", 19: "Shutdown: complete tasks or hand off clearly"},
            "todo":       ["Set phone alarms for time-sensitive meds", "Use SBAR template (reduces cognitive load)", "Ask for help before overwhelm hits"],
            "notes":      ["Shift brain dump: _______________", "ADHD nursing superpower today: _______________"],
        },
        {
            "priorities": ["Body doubling: work near colleagues when possible", "Time-box charting: 15 min per patient, then move", "Post-shift decompress — don't bring it home"],
            "schedule":   {7: "Report handoff + priority triage", 9: "High-acuity patient block (peak focus)", 12: "Mandatory break — actually leave the floor", 14: "Charting catch-up sprint (timer set)", 18: "End-of-shift shutdown + debrief ritual"},
            "todo":       ["Pre-pack shift bag tonight (reduce morning chaos)", "Charge devices before leaving", "Compression socks + good shoes today"],
            "notes":      ["Hyperfocus patient case today: ___", "If behind: ask for help — it's not weakness 💙"],
        },
        {
            "priorities": ["Safe patient care first — always", "External structure: checklists over memory", "Celebrate: I showed up and did hard things"],
            "schedule":   {6: "Arrive early — transition time is ADHD fuel", 8: "Rounds: structured walk reduces overwhelm", 12: "Brain break: step outside for 5 min of air", 15: "End-of-shift priority: critical tasks only", 19: "Decompress ritual: shoes off, tea, debrief"},
            "todo":       ["Sticky note system for today's priority tasks", "Review med list before administering", "Write one positive patient memory today"],
            "notes":      ["You are more competent than your ADHD tells you", "Debrief: what went well? What to hand off?"],
        },
    ],
    "christian_teacher": [
        {
            "priorities": ["📖 Scripture + prayer before first bell", "Teach with purpose: God placed me here", "Pour into one struggling student intentionally"],
            "schedule":   {6: "Rise + pray for your students by name", 8: "Morning: set Christ-centered intention for class", 12: "Lunch: pray + refuel (you're doing God's work)", 15: "Check in: am I loving my students well today?", 20: "Evening prayer: release the day to God"},
            "todo":       ["Write verse of the week on board", "Send encouraging note to discouraged student", "Pray for _______________  (specific student)"],
            "notes":      ["Today's classroom verse: _______________", "God called me to this. I am enough for today."],
        },
        {
            "priorities": ["Faith-integrated lesson moment today", "Grace over perfection in grading", "Community: connect with fellow Christian educator"],
            "schedule":   {7: "Devotional + lesson review with prayer", 9: "Engaging lesson — teach as unto the Lord", 12: "Lunch with intentional gratitude", 14: "Faith connection: weave truth into content", 16: "Admin with excellence + servant spirit"},
            "todo":       ["Plan character trait lesson for next week", "Thank God for one student who challenged me", "Connect with Christian Teachers Network"],
            "notes":      ["Teaching as worship: how did I do today?", "Parent prayer request: _______________"],
        },
        {
            "priorities": ["Model Christ's character in every interaction", "Lesson that plants seeds of truth", "Rest well — sabbath principle matters"],
            "schedule":   {7: "Quiet time — fill the well before giving", 9: "Pour into students with genuine care", 12: "Lunch: thank God for this calling", 15: "Faculty prayer group / accountability", 19: "Evening: release students' burdens to God"},
            "todo":       ["Bible verse for classroom bulletin board (change monthly)", "Pray over empty seats before students arrive", "Memorize one student's prayer request this week"],
            "notes":      ["Kingdom impact is often invisible — keep going 🙏", "Today's 'God moment' in class: _______________"],
        },
    ],
    "sobriety_mom": [
        {
            "priorities": ["✅ Sober Day #___ + mom win combined", "Morning trigger check before kids wake", "One recovery action + one family joy today"],
            "schedule":   {7: "Sober morning: gratitude + kids' breakfast", 9: "Recovery check-in (call/text sponsor)", 12: "Lunch with kids — present, not distracted", 15: "School pick-up sober routine (calming music)", 19: "Kids to bed → recovery reading + journal"},
            "todo":       ["Recovery meeting this week (childcare lined up?)", "Write 3 reasons I choose sobriety as a mom", "Plan sober-safe family weekend activity"],
            "notes":      ["Trigger time: ___ PM (kids' chaos peak) → coping plan: ___", "Sober mom win today: _______________"],
        },
        {
            "priorities": ["Sober morning routine before mom duties begin", "Teach kids by example: honesty + healing", "Self-compassion: I am a recovering AND good mom"],
            "schedule":   {6: "Pre-kid quiet: gratitude + sobriety intention", 8: "School morning: calm, not chaotic (breathe)", 12: "Recovery lunch: healthy + grounding", 15: "Mom mode: present for after-school window", 21: "After bedtime: my recovery time — sacred"},
            "todo":       ["Family recovery-friendly activity planned", "Talk to therapist about mom guilt this week", "Celebrate days sober with small ritual"],
            "notes":      ["Sobriety date: _______________ (my kids know this matters)", "When overwhelmed by mom + recovery: HALT check first"],
        },
        {
            "priorities": ["Show up for kids sober — that IS enough", "Recovery community: reach out, don't isolate", "Rest: sober parenting is hard, sleep matters"],
            "schedule":   {7: "Morning affirmation: I am a sober, loving mom", 9: "Kids' activities + recovery support call", 13: "Lunch together — gratitude for this moment", 16: "Park / outside — sober family time", 20: "Kids asleep → step work or meeting (online ok)"},
            "todo":       ["Write letter to kids for their future (to open at 18)", "One sober social activity this week", "Boundaries: identify one to hold this week"],
            "notes":      ["Recovery mantra: 'I am rewriting our family story'", "Proud moment today: _______________  💙"],
        },
    ],
}


# ═══════════════════════════════════════════════════════════
# 니치별 페이지 콘텐츠 — 같은 레이아웃이지만 내용이 완전히 다름
# ═══════════════════════════════════════════════════════════

NICHE_PAGE_CONTENT: dict[str | None, dict] = {
    None: {  # generic
        "date_label":       "Date: _______________",
        "priorities_label": "🎯 Top 3 Priorities",
        "schedule_label":   "⏰ Schedule",
        "todo_label":       "☑️ To-Do",
        "notes_label":      "📝 Notes",
        "extra_label":      "💡 Ideas",
        "habit_names": [f"Habit {i+1}" for i in range(10)],
        "gratitude_sections": [
            ("🙏 3 Things I'm Grateful For", 3),
            ("✨ What Would Make Today Great?", 2),
            ("💪 Daily Affirmation", 1),
            ("🌟 Amazing Things That Happened", 3),
            ("🔄 How Could Today Be Better?", 2),
        ],
        "weekly_note_label": "📝 Notes & Priorities",
    },
    "ADHD": {
        "date_label":       "Date: _______________ | Energy: ○ ○ ○ ○ ○",
        "priorities_label": "🧠 Top 3 Focus Tasks (w/ Time Estimate)",
        "schedule_label":   "⏱ Time Blocks (avoid gaps)",
        "todo_label":       "⚡ Task Breakdown (small steps)",
        "notes_label":      "💡 Brain Dump",
        "extra_label":      "🎯 Dopamine Reward",
        "habit_names": ["Morning Routine ✓", "Medication / Supplements", "5-min Focus Sprint", "Body Doubling Session", "Screen-Free Break", "Walk / Movement", "Hydration (8 glasses)", "Wind-Down Routine", "Gratitude (3 things)", "Today's Win 🏆"],
        "gratitude_sections": [
            ("🧠 3 Things My Brain Did Well Today", 3),
            ("⚡ What Helped Me Focus?", 2),
            ("💙 Kind Thought Toward Myself", 1),
            ("🎯 One Task I Completed", 2),
            ("🔄 What to Adjust Tomorrow", 2),
        ],
        "weekly_note_label": "🧠 Brain Dump & Next Week Focus",
    },
    "anxiety": {
        "date_label":       "Date: _______________ | Anxiety Level: 1 2 3 4 5",
        "priorities_label": "🌿 3 Grounding Tasks for Today",
        "schedule_label":   "📅 Gentle Schedule (no overloading)",
        "todo_label":       "🐢 Small Steps (progress not perfection)",
        "notes_label":      "💭 Worry Release",
        "extra_label":      "🌱 Today's Affirmation",
        "habit_names": ["Morning Grounding Routine", "Box Breathing (4-4-4-4)", "Mindful Walk (10min)", "Limit News / Social Media", "Hydration", "Journaling", "Gratitude (3 things)", "Evening Wind-Down", "Connect with Someone Safe", "Sleep by 10 PM"],
        "gratitude_sections": [
            ("🌿 3 Things That Felt Safe Today", 3),
            ("💛 Moment of Calm I Noticed", 2),
            ("🌱 Today's Affirmation", 1),
            ("🌸 Small Brave Thing I Did", 2),
            ("🕊️ One Worry I'm Releasing", 2),
        ],
        "weekly_note_label": "💭 Worry List → Release Here",
    },
    "christian": {
        "date_label":       "Date: _______________ | Verse of the Day",
        "priorities_label": "✝️ Intentional Goals for Today",
        "schedule_label":   "📅 Schedule (offered to God)",
        "todo_label":       "☑️ Tasks with Purpose",
        "notes_label":      "📖 Scripture & Reflection",
        "extra_label":      "🙏 Prayer Points",
        "habit_names": ["Morning Prayer", "Bible Reading (chapter)", "Devotional / Quiet Time", "Gratitude Journal", "Act of Kindness", "Church / Community", "Worship / Praise Time", "Evening Prayer", "Sabbath Rest", "Serving Others"],
        "gratitude_sections": [
            ("🙏 3 Blessings I'm Thanking God For", 3),
            ("📖 Scripture That Spoke to Me Today", 2),
            ("✝️ How I Saw God Work Today", 2),
            ("💛 How I Loved Someone Today", 2),
            ("🌟 Prayer for Tomorrow", 2),
        ],
        "weekly_note_label": "🙏 Prayer Requests This Week",
    },
    "sobriety": {
        "date_label":       "Date: _______________ | Day # in Recovery: _____",
        "priorities_label": "💙 Recovery Priorities Today",
        "schedule_label":   "📅 Sober Schedule (fill every hour)",
        "todo_label":       "✅ Recovery To-Do",
        "notes_label":      "💭 Trigger Check & Coping Plan",
        "extra_label":      "🏆 Today's Sober Win",
        "habit_names": ["Sober Today ✓", "Morning Reflection", "Meeting / Step Work", "Called Sponsor / Support", "Gratitude (3 things)", "Physical Exercise", "Healthy Meal", "Avoided a Trigger", "Evening Check-In", "Sleep Routine"],
        "gratitude_sections": [
            ("💙 3 Things Sobriety Has Given Me", 3),
            ("🏆 Today's Recovery Win", 2),
            ("🙏 Grateful for My Support System", 2),
            ("🌱 What I Did Instead of Using", 2),
            ("🌟 Message to My Future Self", 2),
        ],
        "weekly_note_label": "💙 Weekly Recovery Reflection",
    },
    "mom": {
        "date_label":       "Date: _______________",
        "priorities_label": "❤️ Family + Me Priorities (yes, both!)",
        "schedule_label":   "👨‍👩‍👧 Family Schedule",
        "todo_label":       "📋 Mom's To-Do",
        "notes_label":      "💛 Self-Care Reminder",
        "extra_label":      "🌟 Grateful Mom Moment",
        "habit_names": ["Morning Me-Time (10min)", "Kids' Needs Handled", "Healthy Meal Prepped", "Movement / Exercise", "Quality Time with Kids", "Self-Care Check ✓", "One Household Task", "Partner Connection", "Grateful Mom Moment", "Wind-Down Routine"],
        "gratitude_sections": [
            ("❤️ 3 Mom Wins Today (big or tiny!)", 3),
            ("🌸 Moment I Want to Remember", 2),
            ("💛 Self-Care I Did Today", 1),
            ("👨‍👩‍👧 Family Blessing I Noticed", 2),
            ("🌟 How I'll Be Present Tomorrow", 2),
        ],
        "weekly_note_label": "❤️ Family Notes & Reminders",
    },
    "homeschool": {
        "date_label":       "Date: _______________ | Week # _____",
        "priorities_label": "📚 Today's Lesson Priorities",
        "schedule_label":   "🕐 Learning Schedule",
        "todo_label":       "☑️ Curriculum To-Do",
        "notes_label":      "📝 Student Progress Notes",
        "extra_label":      "🌱 Learning Win Today",
        "habit_names": ["Morning Circle Time", "Core Subjects (Math/Reading)", "Science / History Block", "Read-Aloud Time", "Hands-On Activity", "Outdoor Learning", "Grading & Assessment", "Lesson Prep for Tomorrow", "Student Check-In", "Educator Self-Care"],
        "gratitude_sections": [
            ("📚 3 Learning Wins Today", 3),
            ("💡 Best Moment of Discovery", 2),
            ("💛 How I Encouraged My Child Today", 2),
            ("🌱 What We'll Build on Tomorrow", 2),
            ("🌟 Why I Love Homeschooling", 2),
        ],
        "weekly_note_label": "📚 Weekly Curriculum Notes",
    },
    "self_care": {
        "date_label":       "Date: _______________ | Mood: 😊 😌 😐 😔 😤",
        "priorities_label": "🌸 3 Self-Care Intentions Today",
        "schedule_label":   "💆 Wellness Schedule",
        "todo_label":       "✨ Glow-Up To-Do",
        "notes_label":      "💭 Feelings & Reflections",
        "extra_label":      "🌺 Today's Act of Self-Love",
        "habit_names": ["Morning Skincare", "Hydration (8 glasses)", "Mindful Movement", "Nourishing Meal", "Digital Detox (1hr)", "Creative Outlet", "Gratitude Journal", "Connect with Someone", "Evening Routine", "8hr Sleep Goal"],
        "gratitude_sections": [
            ("🌸 3 Ways I Honored Myself Today", 3),
            ("💆 How I Rested & Restored", 2),
            ("✨ Something Beautiful I Noticed", 1),
            ("💛 Kind Thing I Did for Myself", 2),
            ("🌺 Tomorrow's Self-Love Intention", 2),
        ],
        "weekly_note_label": "🌸 Self-Care Reflections",
    },
    "nurse": {
        "date_label":       "Date: _______________ | Shift: AM / PM / NOC",
        "priorities_label": "💊 Top Shift Priorities",
        "schedule_label":   "🏥 Patient / Task Schedule",
        "todo_label":       "📋 Clinical To-Do",
        "notes_label":      "📝 Handoff Notes",
        "extra_label":      "💙 Post-Shift Self-Care",
        "habit_names": ["Pre-Shift Prep & Review", "Hydration & Meals on Shift", "Medication Reconciliation", "Patient Assessments", "Documentation Complete", "Handoff Communication", "Post-Shift Debrief", "Decompress Routine", "Physical Self-Care", "Connect / Celebrate Wins"],
        "gratitude_sections": [
            ("💊 3 Patient Moments I'm Grateful For", 3),
            ("💪 Clinical Win Today", 2),
            ("💙 How I Took Care of Myself", 2),
            ("🌟 Something I Learned on Shift", 2),
            ("🔄 One Thing I'll Do Differently", 2),
        ],
        "weekly_note_label": "🏥 Clinical Notes & Goals",
    },
    "teacher": {
        "date_label":       "Date: _______________",
        "priorities_label": "🍎 Lesson & Classroom Priorities",
        "schedule_label":   "📚 Class Schedule",
        "todo_label":       "✅ Teaching To-Do",
        "notes_label":      "📝 Student Observations",
        "extra_label":      "💛 Teacher Self-Care",
        "habit_names": ["Lesson Prep Complete", "Morning Classroom Routine", "Student Check-Ins", "Grading Progress", "Parent Communication", "Classroom Management Note", "Professional Development", "Colleague Collaboration", "Self-Care Time", "Evening Wind-Down"],
        "gratitude_sections": [
            ("🍎 3 Student Wins I Witnessed", 3),
            ("💡 Most Meaningful Teaching Moment", 2),
            ("💛 How I Took Care of Myself", 2),
            ("🌟 What Worked Well Today", 2),
            ("📚 What I'll Try Differently Tomorrow", 2),
        ],
        "weekly_note_label": "🍎 Weekly Classroom Notes",
    },
    "pregnancy": {
        "date_label":       "Date: _______________ | Week # _____ | Trimester: 1 / 2 / 3",
        "priorities_label": "🤰 Today's Gentle Priorities",
        "schedule_label":   "💆 Prenatal Schedule",
        "todo_label":       "📋 Baby Prep To-Do",
        "notes_label":      "💭 Symptoms & Notes",
        "extra_label":      "👶 Baby Moment Today",
        "habit_names": ["Prenatal Vitamins", "Hydration (10+ glasses)", "Gentle Movement / Walk", "Healthy Meal / Nutrition", "Rest / Nap Time", "Kick Count (3rd tri)", "Prenatal Appointment Prep", "Hospital Bag Progress", "Partner / Support Check-In", "Gratitude for This Journey"],
        "gratitude_sections": [
            ("🤰 3 Things I'm Grateful for in This Pregnancy", 3),
            ("👶 Baby Moment I Want to Remember", 2),
            ("💪 How My Body Amazed Me Today", 2),
            ("💛 How I Nourished Myself", 2),
            ("🌟 Letter to My Baby", 2),
        ],
        "weekly_note_label": "🤰 Pregnancy Notes This Week",
    },
    "entrepreneur": {
        "date_label":       "Date: _______________ | Revenue Goal: $___________",
        "priorities_label": "🚀 Top 3 Revenue-Driving Tasks",
        "schedule_label":   "⏰ CEO Time Blocks",
        "todo_label":       "💼 Business To-Do",
        "notes_label":      "💡 Ideas & Insights",
        "extra_label":      "📈 Today's Business Win",
        "habit_names": ["Morning CEO Routine", "Deep Work Block (2hr)", "Revenue-Generating Activity", "Client / Customer Touchpoint", "Learning & Development (30min)", "Physical Exercise", "Content / Marketing", "Financial Review", "Networking / Relationships", "Evening Vision Review"],
        "gratitude_sections": [
            ("🚀 3 Business Wins Today", 3),
            ("💡 Best Idea or Insight", 2),
            ("💼 Revenue / Progress Highlight", 2),
            ("🌟 Who Helped My Business Today", 2),
            ("📈 Vision I'm Moving Toward", 2),
        ],
        "weekly_note_label": "🚀 Weekly Business Notes",
    },
    "perimenopause": {
        "date_label":       "Date: _______________ | Symptoms: Hot Flash / Mood / Sleep / Brain Fog",
        "priorities_label": "🌿 Hormone-Friendly Priorities",
        "schedule_label":   "💆 Gentle Daily Schedule",
        "todo_label":       "✅ Today's Manageable To-Do",
        "notes_label":      "📋 Symptom & Energy Log",
        "extra_label":      "🌸 Today's Self-Compassion",
        "habit_names": ["Morning Hormone-Support Routine", "Anti-Inflammatory Meal", "Weight-Bearing Exercise", "Stress Management (10min)", "Limit Caffeine / Alcohol", "Hydration", "Sleep Prep (by 9:30 PM)", "Supplements / HRT Tracking", "Hot Flash Log", "Gratitude & Self-Compassion"],
        "gratitude_sections": [
            ("🌿 3 Ways My Body Supported Me Today", 3),
            ("💪 Symptom Win (managed well)", 2),
            ("🌸 Act of Self-Compassion Today", 2),
            ("💛 Energy I'm Grateful For", 2),
            ("🌟 Wisdom This Season Is Teaching Me", 2),
        ],
        "weekly_note_label": "🌿 Weekly Symptom & Wellness Notes",
    },
    "cycle_syncing": {
        "date_label":       "Date: _______________ | Cycle Day # _____ | Phase: Menstrual / Follicular / Ovulatory / Luteal",
        "priorities_label": "🌙 Phase-Aligned Priorities",
        "schedule_label":   "⏰ Cycle-Informed Schedule",
        "todo_label":       "✅ Energy-Matched To-Do",
        "notes_label":      "📋 Cycle & Symptom Log",
        "extra_label":      "🌺 Body Wisdom Note",
        "habit_names": ["Cycle Day Tracking", "Phase-Aligned Nutrition", "Movement for This Phase", "Hormone-Support Supplement", "Stress & Cortisol Check", "Hydration", "Seed Cycling", "Sleep Quality (7-9hr)", "Cycle Journal Entry", "Self-Compassion Practice"],
        "gratitude_sections": [
            ("🌙 3 Ways I Honored My Cycle Today", 3),
            ("🌺 What My Body Was Asking For", 2),
            ("💪 Phase Win Today", 2),
            ("🌸 Body Appreciation Moment", 2),
            ("🌟 Wisdom From This Cycle Phase", 2),
        ],
        "weekly_note_label": "🌙 Cycle Tracking Notes",
    },
    "caregiver": {
        "date_label":       "Date: _______________",
        "priorities_label": "💛 Care Priorities + My Needs",
        "schedule_label":   "🕐 Care & Self Schedule",
        "todo_label":       "📋 Caregiving To-Do",
        "notes_label":      "📝 Care Notes & Observations",
        "extra_label":      "🌿 Caregiver Self-Care Today",
        "habit_names": ["Morning Care Routine", "Medication Management", "Appointments & Follow-Ups", "Safety Check", "Emotional Check-In (them + me)", "Respite / Break Time", "My Own Meal & Hydration", "Physical Self-Care", "Support Network Check-In", "Gratitude (I Am Enough)"],
        "gratitude_sections": [
            ("💛 3 Caregiving Wins Today", 3),
            ("🌿 How I Took Care of Myself", 2),
            ("💙 Meaningful Moment with My Loved One", 2),
            ("🌸 Support I'm Grateful For", 2),
            ("🌟 Reminder: I Am Doing Enough", 2),
        ],
        "weekly_note_label": "💛 Weekly Care Notes & Support",
    },
    "glp1": {
        "date_label":       "Date: _______________ | Injection Day: Y / N | Week # _____",
        "priorities_label": "🥗 Health & Wellness Priorities",
        "schedule_label":   "⏰ Eating & Movement Window",
        "todo_label":       "✅ Wellness To-Do",
        "notes_label":      "📋 Side Effects & Observations",
        "extra_label":      "💪 Non-Scale Victory Today",
        "habit_names": ["GLP-1 Injection (weekly)", "Protein Goal (grams)", "Hydration (64+ oz)", "Slow Eating Practice", "Movement / Steps", "Hunger / Fullness Check", "Vitamins & Supplements", "Sleep (7-9hr)", "Progress Photo / Measurement", "Gratitude for Progress"],
        "gratitude_sections": [
            ("🥗 3 Healthy Choices I Made Today", 3),
            ("💪 Non-Scale Victory Today", 2),
            ("💛 How My Body Felt Differently", 2),
            ("🌟 Progress I'm Most Proud Of", 2),
            ("🔄 Adjustment for Tomorrow", 2),
        ],
        "weekly_note_label": "🥗 Weekly Wellness Notes",
    },
    "ADHD_teacher": {
        "date_label":       "Date: _______________ | Energy: ○ ○ ○ ○ ○ | Shift: AM / PM",
        "priorities_label": "🧠 Top 3 Focus Tasks (Teaching + ADHD-Friendly)",
        "schedule_label":   "⏱ Time-Blocked Class Schedule",
        "todo_label":       "⚡ Lesson To-Do (broken into steps)",
        "notes_label":      "💡 Brain Dump & Student Notes",
        "extra_label":      "🍎 Classroom + Personal Win",
        "habit_names": ["Morning Classroom Prep (body double)", "Medication / Supplements", "Lesson Time-Blocking Done", "Student Check-Ins", "Transition Cue Used ✓", "Brain Break (for me too!)", "Documentation / Grading", "End-of-Day Desk Reset", "Decompression Routine", "Tomorrow's Top 3 Task Prep"],
        "gratitude_sections": [
            ("🧠 3 Classroom Wins (yours + students')", 3),
            ("⚡ ADHD Superpower I Used Today", 2),
            ("💙 Kindness to Myself Today", 1),
            ("🍎 Student Moment That Mattered", 2),
            ("🔄 What to Adjust Tomorrow", 2),
        ],
        "weekly_note_label": "🧠 Brain Dump & Weekly Class Notes",
    },
    "ADHD_nurse": {
        "date_label":       "Date: _______________ | Energy: ○ ○ ○ ○ ○ | Shift: AM / PM / NOC",
        "priorities_label": "🧠 Shift Priorities (Time-Boxed)",
        "schedule_label":   "⏱ Patient / Task Time Blocks",
        "todo_label":       "⚡ Clinical To-Do (step by step)",
        "notes_label":      "💡 Brain Dump & Handoff Notes",
        "extra_label":      "💙 Shift + Recovery Win",
        "habit_names": ["Pre-Shift Prep (visual list)", "Medication / Supplements", "Hydration & Timed Meals", "Patient Priorities List Made", "Hyperfocus Check-In", "Time Cue Used on Shift ✓", "Documentation Done", "Post-Shift Debrief (5min)", "Decompression Routine", "Sleep Prep (protect sleep!)"],
        "gratitude_sections": [
            ("🧠 3 Wins: Clinical + Personal", 3),
            ("⚡ ADHD Strength That Helped Today", 2),
            ("💙 Compassion Toward Myself", 1),
            ("💊 Patient Moment I'm Grateful For", 2),
            ("🔄 What to Try Differently Next Shift", 2),
        ],
        "weekly_note_label": "🧠 Brain Dump & Clinical Notes",
    },
    "christian_teacher": {
        "date_label":       "Date: _______________  | Verse: _______________",
        "priorities_label": "✝️ Teaching with Purpose Today",
        "schedule_label":   "📚 Spirit-Led Class Schedule",
        "todo_label":       "☑️ Teaching To-Do (done in love)",
        "notes_label":      "📖 Scripture + Student Observations",
        "extra_label":      "🙏 Prayer for My Students",
        "habit_names": ["Morning Prayer for My Class", "Bible / Devotional Reading", "Spirit-Led Lesson Prep", "Pray Over Each Student", "Act of Grace in Classroom", "Gratitude for My Calling", "Parent / Community Connection", "Professional Growth", "Evening Prayer & Release", "Rest (trust God with tomorrow)"],
        "gratitude_sections": [
            ("✝️ 3 Ways God Worked in My Classroom", 3),
            ("📖 Scripture That Guided Me Today", 2),
            ("🍎 Student I Saw God Working In", 2),
            ("💛 How I Loved My Students Well", 2),
            ("🙏 Prayer of Surrender for Tomorrow", 2),
        ],
        "weekly_note_label": "✝️ Prayer Requests & Classroom Notes",
    },
    "sobriety_mom": {
        "date_label":       "Date: _______________ | Day # Sober: _____ | Mom Win:",
        "priorities_label": "💙 Recovery + Family Priorities",
        "schedule_label":   "👨‍👩‍👧 Family & Recovery Schedule",
        "todo_label":       "✅ Sober Mom To-Do",
        "notes_label":      "💭 Trigger Check & Feelings",
        "extra_label":      "🏆 Today's Sober Mom Win",
        "habit_names": ["Sober Today ✓", "Morning Recovery Reflection", "Kids' Needs Met", "Meeting / Step Work", "Called Sponsor / Support Person", "Healthy Meal for Family", "Exercise / Movement", "Avoided Trigger", "Quality Moment with Kids", "Evening Gratitude & Check-In"],
        "gratitude_sections": [
            ("💙 3 Recovery + Mom Wins Today", 3),
            ("👨‍👩‍👧 Sober Parenting Moment I Treasure", 2),
            ("🏆 What Sobriety Has Given My Family", 2),
            ("🌸 How I Took Care of Myself", 2),
            ("🌟 Message from Sober-Me to My Kids", 2),
        ],
        "weekly_note_label": "💙 Recovery + Family Notes",
    },
}


# ═══════════════════════════════════════════════════════════
# 니치별 20% 시그니처 섹션 — _daily_html extra_label 대체
# 각 니치의 핵심 특성을 반영한 전용 미니 트래커
# ═══════════════════════════════════════════════════════════

def _cb_mini() -> str:
    """미니 체크박스 (12px)."""
    t = _current_theme
    color = t.get("primary", "#888")
    return (f'<span style="display:inline-block;width:12px;height:12px;border:1.5px solid {color};'
            f'border-radius:3px;margin-right:4px;vertical-align:middle"></span>')


def _input_mini(width: str = "70%") -> str:
    """미니 입력 라인."""
    return f'<span style="display:inline-block;width:{width};border-bottom:1.5px solid #ddd;vertical-align:middle"></span>'


def _niche_section_title(text: str) -> str:
    t = _current_theme
    color = t.get("primary", "#888")
    return (f'<div style="font-size:10px;font-weight:700;color:{color};'
            f'text-transform:uppercase;letter-spacing:0.4px;margin:5px 0 3px">{text}</div>')


def _build_niche_extra() -> str:
    """현재 니치(_current_niche) 기반 시그니처 섹션 HTML 반환."""
    niche = _current_niche

    # ── ADHD: Brain Dump + Step Breakdown + Dopamine Reward ──
    if niche == "ADHD":
        lines = "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(3))
        steps = "".join(
            f'<div style="margin:2px 0">{_cb_mini()}'
            f'<span style="font-size:10px;color:#bbb">Step {i+1}:</span> {_input_mini("65%")}</div>'
            for i in range(3)
        )
        return (
            _niche_section_title("🧠 Brain Dump (clear your head first)")
            + lines
            + _niche_section_title("⚡ Task Breakdown (small steps)")
            + steps
            + _niche_section_title("🎯 Dopamine Reward if done")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── anxiety: Worry Release + Coping Check + Affirmation ──
    elif niche == "anxiety":
        coping = ["Box Breathing", "Grounding Walk", "Journaling", "EFT Tapping"]
        checks = "".join(
            f'<span style="margin-right:8px;font-size:10px">{_cb_mini()}{c}</span>'
            for c in coping
        )
        return (
            _niche_section_title("💭 Worry Release (write it, release it)")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("🌿 Coping Used Today")
            + f'<div style="margin:3px 0">{checks}</div>'
            + _niche_section_title("🌱 Today's Affirmation")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── christian: Scripture + Prayer Requests + Gratitude ──
    elif niche == "christian":
        return (
            _niche_section_title("📖 Scripture of the Day")
            + f'<div style="margin:2px 0">{_input_mini("92%")}</div>'
            + _niche_section_title("🙏 Prayer Requests")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("💛 Gratitude to God (1 thing)")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── sobriety: Trigger Check + Sober Win + Meeting Tracker ──
    elif niche == "sobriety":
        return (
            _niche_section_title("💙 Trigger Check (what to watch for)")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("🏆 Today's Sober Win")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("📋 Recovery Actions")
            + f'<div style="margin:3px 0">'
            + f'{_cb_mini()}<span style="font-size:10px;margin-right:10px">Meeting</span>'
            + f'{_cb_mini()}<span style="font-size:10px;margin-right:10px">Step Work</span>'
            + f'{_cb_mini()}<span style="font-size:10px">Called Sponsor</span>'
            + '</div>'
        )

    # ── mom: Kids Needs + Me-Time + Mom Win ──
    elif niche == "mom":
        kids = ["Kid 1 need", "Kid 2 need", "Kid 3 need"]
        rows = "".join(
            f'<div style="margin:2px 0;font-size:10px;color:#999">{k}: {_input_mini("60%")}</div>'
            for k in kids
        )
        return (
            _niche_section_title("👨‍👩‍👧 Kids' Needs Today")
            + rows
            + _niche_section_title("💛 Me-Time Done?")
            + f'<div style="margin:3px 0">'
            + f'{_cb_mini()}<span style="font-size:10px;margin-right:10px">Yes!</span>'
            + f'{_cb_mini()}<span style="font-size:10px">Not yet — schedule: {_input_mini("40%")}</span>'
            + '</div>'
            + _niche_section_title("🌟 Mom Win Today")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── homeschool: Subjects Done + Learning Win + Reading Log ──
    elif niche == "homeschool":
        subjects = ["Math", "Reading/LA", "Science", "History", "Other"]
        checks = "".join(
            f'<span style="margin-right:6px;font-size:10px">{_cb_mini()}{s}</span>'
            for s in subjects
        )
        return (
            _niche_section_title("📚 Subjects Completed")
            + f'<div style="margin:3px 0;flex-wrap:wrap">{checks}</div>'
            + _niche_section_title("🌱 Learning Win Today")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("📖 Reading Log (title + pages)")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── self_care: Ritual Check + Body Check-in + Self-Love Act ──
    elif niche == "self_care":
        rituals = ["Sleep 7h+", "Move/Exercise", "Nourish", "Journal", "Outdoors"]
        checks = "".join(
            f'<span style="margin-right:6px;font-size:10px">{_cb_mini()}{r}</span>'
            for r in rituals
        )
        return (
            _niche_section_title("🌸 Rituals Done")
            + f'<div style="margin:3px 0">{checks}</div>'
            + _niche_section_title("💆 Body Check-In (how do you feel?)")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("🌺 Today's Act of Self-Love")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── nurse: Shift Summary + Handoff Notes + Post-Shift Self-Care ──
    elif niche == "nurse":
        care = ["Hydrated", "Ate lunch", "5-min break", "Decompressed"]
        checks = "".join(
            f'<span style="margin-right:6px;font-size:10px">{_cb_mini()}{c}</span>'
            for c in care
        )
        return (
            _niche_section_title("💊 Shift Summary")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("🏥 Key Handoff Note")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("💙 Post-Shift Self-Care")
            + f'<div style="margin:3px 0">{checks}</div>'
        )

    # ── teacher: Lesson Highlight + Student Note + Self-Care ──
    elif niche == "teacher":
        care = ["Coffee ✓", "Lunch break", "Moved body", "Left on time"]
        checks = "".join(
            f'<span style="margin-right:6px;font-size:10px">{_cb_mini()}{c}</span>'
            for c in care
        )
        return (
            _niche_section_title("🍎 Lesson Highlight Today")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("📝 Student Observation")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("💛 Teacher Self-Care Check")
            + f'<div style="margin:3px 0">{checks}</div>'
        )

    # ── pregnancy: Kick Count + Prenatal + Symptom + Water ──
    elif niche == "pregnancy":
        t = _current_theme
        color = t.get("primary", "#888")
        water = "".join(
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'border:1.5px solid {color};margin-right:3px"></span>'
            for _ in range(8)
        )
        return (
            _niche_section_title("🤰 Today's Tracking")
            + f'<div style="display:flex;gap:20px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>Kick Count: {_input_mini("30%")}</span>'
            + f'<span>Week #: {_input_mini("20%")}</span>'
            + f'<span>Prenatal: {_cb_mini()} ✓</span>'
            + '</div>'
            + _niche_section_title("💭 Symptom & Feeling Log")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("💧 Water Intake")
            + f'<div style="margin:3px 0">{water}</div>'
        )

    # ── entrepreneur: Revenue Win + CEO Insight + #1 Tomorrow ──
    elif niche == "entrepreneur":
        return (
            _niche_section_title("📈 Revenue-Moving Win Today")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("💡 CEO Insight / Lesson")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("🔥 Tomorrow's #1 Revenue Task")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── perimenopause: Hot Flash Log + HRT + Energy + Symptom ──
    elif niche == "perimenopause":
        t = _current_theme
        color = t.get("primary", "#888")
        energy = "".join(
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'border:1.5px solid {color};margin-right:3px"></span>'
            for _ in range(5)
        )
        return (
            _niche_section_title("🌡️ Today's Hormone Log")
            + f'<div style="display:flex;gap:16px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>Hot Flashes: {_input_mini("15%")} times</span>'
            + f'<span>HRT/Supp: {_cb_mini()} taken</span>'
            + f'<span>Sleep: {_input_mini("12%")} hrs</span>'
            + '</div>'
            + _niche_section_title("🌿 Energy Level (circle 1–5)")
            + f'<div style="margin:3px 0">{energy}</div>'
            + _niche_section_title("💭 Symptom Note")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── cycle_syncing: Phase Check + Seed Cycling + Energy + Body Note ──
    elif niche == "cycle_syncing":
        phases = ["🌑 Menstrual", "🌱 Follicular", "🌕 Ovulatory", "🍂 Luteal"]
        checks = "".join(
            f'<span style="margin-right:8px;font-size:9.5px">{_cb_mini()}{p}</span>'
            for p in phases
        )
        t = _current_theme
        color = t.get("primary", "#888")
        energy = "".join(
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'border:1.5px solid {color};margin-right:3px"></span>'
            for _ in range(5)
        )
        return (
            _niche_section_title("🌙 Today's Cycle Phase")
            + f'<div style="margin:3px 0">{checks}</div>'
            + _niche_section_title("🌱 Seed Cycling & Cycle Day")
            + f'<div style="display:flex;gap:16px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>Cycle Day #: {_input_mini("15%")}</span>'
            + f'<span>Seeds: {_cb_mini()} taken</span>'
            + '</div>'
            + _niche_section_title("🔥 Energy Level (circle 1–5)")
            + f'<div style="margin:3px 0">{energy}</div>'
        )

    # ── caregiver: Med Log + Care Notes + My Break + Care Team ──
    elif niche == "caregiver":
        return (
            _niche_section_title("💊 Medications Given")
            + f'<div style="display:flex;gap:12px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>{_cb_mini()} Morning</span>'
            + f'<span>{_cb_mini()} Afternoon</span>'
            + f'<span>{_cb_mini()} Evening</span>'
            + f'<span>{_cb_mini()} Night</span>'
            + '</div>'
            + _niche_section_title("📋 Care Notes / Observations")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("🌿 My Respite Break (I matter too)")
            + f'<div style="display:flex;gap:12px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>{_cb_mini()} Took a break</span>'
            + f'<span>Duration: {_input_mini("25%")}</span>'
            + '</div>'
        )

    # ── glp1: Injection + Protein + Non-Scale Win + Water ──
    elif niche == "glp1":
        t = _current_theme
        color = t.get("primary", "#888")
        water = "".join(
            f'<span style="display:inline-block;width:14px;height:14px;border-radius:50%;'
            f'border:1.5px solid {color};margin-right:3px"></span>'
            for _ in range(8)
        )
        return (
            _niche_section_title("💉 GLP-1 Daily Tracker")
            + f'<div style="display:flex;gap:16px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>Injection: {_cb_mini()} done</span>'
            + f'<span>Protein: {_input_mini("12%")}g / Goal: {_input_mini("12%")}g</span>'
            + '</div>'
            + _niche_section_title("⚖️ Non-Scale Victory")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("💧 Water Intake")
            + f'<div style="margin:3px 0">{water}</div>'
        )

    # ── ADHD_teacher: Brain Dump + Class Highlight + Prep ──
    elif niche == "ADHD_teacher":
        return (
            _niche_section_title("🧠 Brain Dump (before class)")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("🍎 Class Highlight / Win")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("⚡ Tomorrow's Prep (one task)")
            + f'<div style="margin:2px 0">{_cb_mini()}{_input_mini("75%")}</div>'
        )

    # ── ADHD_nurse: Brain Dump + Time-Box Slots + Post-Shift Debrief ──
    elif niche == "ADHD_nurse":
        slots = ["Task 1", "Task 2", "Task 3"]
        rows = "".join(
            f'<div style="margin:2px 0;font-size:10px;color:#999">{s}: {_input_mini("60%")}'
            f' <span style="color:#ccc">by</span> {_input_mini("12%")}</div>'
            for s in slots
        )
        return (
            _niche_section_title("🧠 Pre-Shift Brain Dump")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("⏱ Task Time-Boxes")
            + rows
            + _niche_section_title("💙 Post-Shift Debrief")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── christian_teacher: Scripture + Prayer for Class + Grace Moment ──
    elif niche == "christian_teacher":
        return (
            _niche_section_title("📖 Scripture for My Students Today")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("🙏 Prayer for My Class")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("✝️ Grace Moment in the Classroom")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── sobriety_mom: Sober Day + Mom Win + Trigger + Kids ──
    elif niche == "sobriety_mom":
        return (
            _niche_section_title("💙 Sobriety + Mom Tracking")
            + f'<div style="display:flex;gap:16px;font-size:10px;color:#999;margin:3px 0">'
            + f'<span>Sober Day #: {_input_mini("15%")}</span>'
            + f'<span>Sober: {_cb_mini()} ✓</span>'
            + '</div>'
            + _niche_section_title("🏆 Mom Win Today")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
            + _niche_section_title("💭 Trigger Check")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )

    # ── None (generic): Ideas + Today's Win ──
    else:
        return (
            _niche_section_title("💡 Ideas & Insights")
            + "".join(f'<div style="margin:2px 0">{_input_mini("92%")}</div>' for _ in range(2))
            + _niche_section_title("🌟 Today's Win")
            + f'<div style="margin:2px 0">{_input_mini("85%")}</div>'
        )


# ═══════════════════════════════════════════════════════════
# BUILDER
# ═══════════════════════════════════════════════════════════

TYPE_CONFIG = {
    # Why: 상위 셀러 = 100-200페이지 번들. 연/월/주/일 전부 포함 = 올인원 구성.
    "daily": {
        "title": "Daily Planner", "subtitle": "Undated All-in-One Life Organizer",
        "sections": [
            ("Yearly Overview", 2), ("Vision Board", 1),
            ("Monthly", 12), ("Monthly Review", 12),
            ("Weekly", 52), ("Daily", 52),
            ("Habit", 6), ("Mood", 1), ("Notes", 10),
        ],
    },  # total: 2 + 148 = 150 pages
    "weekly": {
        "title": "Weekly Planner", "subtitle": "Undated 52-Week Organizer",
        "sections": [
            ("Yearly Overview", 2), ("Vision Board", 1),
            ("Monthly", 12), ("Monthly Review", 12),
            ("Weekly", 52), ("Habit", 6), ("Notes", 15),
        ],
    },  # total: 2 + 100 = 102 pages
    "budget": {
        "title": "Budget Planner", "subtitle": "Annual Finance Tracker",
        "sections": [
            ("Yearly Overview", 2), ("Monthly", 12),
            ("Budget", 24), ("Monthly Review", 12), ("Notes", 10),
        ],
    },  # total: 2 + 60 = 62 pages
    "meal": {
        "title": "Meal Planner", "subtitle": "52-Week Menu & Grocery Planner",
        "sections": [
            ("Yearly Overview", 1), ("Meal", 52), ("Notes", 10),
        ],
    },  # total: 2 + 63 = 65 pages
    "habit_tracker": {
        "title": "Habit Tracker", "subtitle": "12-Month Habit Builder",
        "sections": [
            ("Yearly Overview", 2), ("Monthly", 12),
            ("Habit", 24), ("Monthly Review", 12), ("Notes", 8),
        ],
    },  # total: 2 + 58 = 60 pages
    "gratitude": {
        "title": "Gratitude Journal", "subtitle": "365-Day Mindfulness Journey",
        "sections": [
            ("Vision Board", 1), ("Yearly Overview", 1),
            ("Gratitude", 90), ("Monthly Review", 6), ("Notes", 10),
        ],
    },  # total: 2 + 108 = 110 pages
    "goal_setting": {
        "title": "Goal Setting Planner", "subtitle": "90-Day Action Plan",
        "sections": [
            ("Vision Board", 2), ("Yearly Overview", 2),
            ("Monthly", 6), ("Weekly", 13),
            ("Project Tracker", 3), ("Habit", 3), ("Notes", 10),
        ],
    },  # total: 2 + 39 = 41 pages (집중형)
    "fitness": {
        "title": "Fitness Planner", "subtitle": "12-Month Workout & Wellness Tracker",
        "sections": [
            ("Yearly Overview", 2), ("Vision Board", 1),
            ("Body Measurement", 2), ("Monthly", 12),
            ("Workout Log", 52), ("Habit", 6),
            ("Monthly Review", 12), ("Notes", 8),
        ],
    },  # total: 2 + 95 = 97 pages
}

def _mood_tracker_html(pg: int, total: int) -> str:
    """무드 트래커 페이지 — 상위 1% 플래너 필수 포함 요소."""
    t = _current_theme
    moods = [
        ("😊", "Happy",    t["primary"]),
        ("😌", "Calm",     t["accent"]),
        ("😐", "Neutral",  t["light"]),
        ("😔", "Sad",      "#B0C4DE"),
        ("😤", "Stressed", "#E8A598"),
        ("😴", "Tired",    "#C5B8D8"),
        ("🤩", "Excited",  "#FFD700"),
        ("😡", "Angry",    "#E88080"),
    ]
    legend = ""
    for emoji, label, color in moods:
        legend += f"""
        <div style="display:flex;align-items:center;gap:6px;margin-bottom:5px;">
            <div style="width:18px;height:18px;border-radius:4px;background:{color};
                 border:1.5px solid {t['line']};flex-shrink:0;
                 display:flex;align-items:center;justify-content:center;font-size:11px;">{emoji}</div>
            <span style="font-size:10px;color:{t['text']};font-family:'Quicksand',sans-serif;">{label}</span>
        </div>"""

    # 12개월 × 31일 그리드
    months_grid = ""
    for mi, mname in enumerate(MONTHS):
        cells = ""
        for d in range(1, 32):
            cells += f'<div style="width:16px;height:16px;border:1.5px solid {t["accent"]};border-radius:3px;font-size:6px;display:flex;align-items:center;justify-content:center;color:{t["text"]};background:white;">{d}</div>'
        months_grid += f"""
        <div style="margin-bottom:6px;">
            <div style="font-size:9px;font-weight:700;color:{t['primary']};letter-spacing:1px;
                 text-transform:uppercase;margin-bottom:3px;font-family:'Quicksand',sans-serif;">
                {mname}
            </div>
            <div style="display:flex;flex-wrap:wrap;gap:2px;max-width:490px;">{cells}</div>
        </div>"""

    return _page_frame(f"""
        {_make_header("Mood Tracker", "Color each day with how you feel", pg, total, "Mood")}
        <div style="display:flex;gap:20px;margin-right:32px;">
            <div style="flex:1;">{months_grid}</div>
            <div style="width:110px;flex-shrink:0;">
                <div style="font-size:10px;font-weight:700;color:{t['primary']};
                     letter-spacing:1px;text-transform:uppercase;margin-bottom:10px;
                     font-family:'Quicksand',sans-serif;">COLOR KEY</div>
                {legend}
                <div style="margin-top:16px;padding:8px;background:{t['light']};border-radius:8px;">
                    <div style="font-size:10px;color:{t['text']};line-height:1.5;
                         font-family:'Nunito',sans-serif;">
                        Fill each square with the matching color or initial
                    </div>
                </div>
            </div>
        </div>
    """)


def _sticker_page_html(t: dict) -> str:
    """스티커/데코 보너스 페이지 — 상위 1% 셀러 필수 포함 요소.

    30개 텍스트 스티커 + 감성 배지를 격자 배열.
    이미지 스티커 대신 CSS/Unicode 스티커 → 외부 에셋 없이 인쇄 가능.
    """
    stickers = [
        ("📌", "TODAY"),       ("✅", "DONE"),        ("⭐", "PRIORITY"),
        ("💡", "IDEA"),        ("🔥", "URGENT"),      ("💪", "GOAL MET"),
        ("📖", "READ"),        ("🎯", "FOCUS"),       ("🎉", "WIN!"),
        ("💤", "REST DAY"),    ("✈️", "TRAVEL"),      ("💊", "MEDS"),
        ("🏋️", "WORKOUT"),    ("🧘", "SELF-CARE"),   ("💰", "PAYDAY"),
        ("📞", "CALL"),        ("📧", "EMAIL"),       ("🍽️", "MEAL PREP"),
        ("🎁", "BIRTHDAY"),    ("🌿", "PLANT CARE"),  ("📝", "NOTES"),
        ("🚗", "ERRAND"),      ("🏥", "APPT"),        ("☕", "COFFEE RUN"),
        ("📅", "PLAN AHEAD"),  ("🌙", "NIGHT ROUTINE"),("☀️", "MORNING"),
        ("💬", "MEETING"),     ("📸", "PHOTO"),       ("🌸", "BLOOM"),
    ]
    rows = []
    cols = 6
    for row_i in range(0, len(stickers), cols):
        batch = stickers[row_i:row_i + cols]
        cells = ""
        for emoji, label in batch:
            cells += f"""
            <div style="
                background:{t['light']}; border:1.5px solid {t['accent']};
                border-radius:12px; padding:14px 8px; text-align:center;
                display:flex; flex-direction:column; align-items:center; gap:6px;
                font-family:'Nunito',sans-serif;">
              <span style="font-size:26px;">{emoji}</span>
              <span style="font-size:9px; font-weight:700; color:{t['primary']};
                    letter-spacing:1px; text-transform:uppercase;">{label}</span>
            </div>"""
        rows.append(f'<div style="display:grid;grid-template-columns:repeat({cols},1fr);gap:10px;">{cells}</div>')

    return f"""
    <div class="page" style="background:{t['bg']}; padding:0.5in 0.5in 0.5in 0.4in;">
        <div style="background:{t['gradient']};border-radius:16px;padding:14px 22px;
             margin-bottom:16px; text-align:center; margin-right:36px;">
            <h2 style="font-family:'Fredoka One',cursive;font-size:22px;color:white;margin:0;">
                ✦ Sticker &amp; Label Kit
            </h2>
            <p style="color:rgba(255,255,255,.85);font-size:10px;margin:4px 0 0;font-weight:600;">
                Print · Cut · Stick — or use digitally in GoodNotes / Notability
            </p>
        </div>
        <div style="display:flex;flex-direction:column;gap:10px;margin-right:36px;">
            {''.join(rows)}
        </div>
        <p style="font-size:10px;color:{t['line']};text-align:center;margin-top:12px;
             font-family:'Nunito',sans-serif;">
            Print on sticker paper and cut, or import page into GoodNotes as a sticker sheet
        </p>
    </div>
    """


def _color_palette_page_html(t: dict, theme_name: str) -> str:
    """컬러 팔레트 안내 페이지 — 고객이 테마 색상 코드를 알 수 있도록."""
    colors = [
        ("Primary",    t["primary"],    "Main accent color"),
        ("Light",      t["light"],      "Background tint"),
        ("Accent",     t["accent"],     "Highlight & borders"),
        ("Background", t["bg"],         "Page background"),
        ("Line",       t["line"],       "Dividers & grids"),
        ("Text",       t["text"],       "Body text"),
    ]
    swatches = ""
    for label, hex_val, desc in colors:
        # 어두운 색은 텍스트를 흰색으로
        is_dark = hex_val in (t["text"],) or hex_val.startswith("#1") or hex_val.startswith("#2") or hex_val.startswith("#3") or hex_val.startswith("#4")
        txt_color = "#FFFFFF" if is_dark else t["text"]
        swatches += f"""
        <div style="display:flex;align-items:center;gap:16px;margin-bottom:14px;">
            <div style="width:64px;height:64px;border-radius:12px;background:{hex_val};
                 border:2px solid {t['line']};flex-shrink:0;
                 display:flex;align-items:center;justify-content:center;">
            </div>
            <div>
                <div style="font-weight:700;font-size:13px;color:{t['primary']};
                     text-transform:uppercase;letter-spacing:1px;">{label}</div>
                <div style="font-family:'Courier New',monospace;font-size:14px;
                     color:{t['text']};margin:2px 0;">{hex_val}</div>
                <div style="font-size:11px;color:{t['line']};">{desc}</div>
            </div>
        </div>"""

    theme_display = theme_name.replace("_", " ").title()
    return f"""
    <div class="page" style="background:{t['bg']}; padding:0.5in 0.5in 0.5in 0.4in;">
        <div style="background:{t['gradient']};border-radius:16px;padding:14px 22px;
             margin-bottom:20px; margin-right:36px;">
            <h2 style="font-family:'Fredoka One',cursive;font-size:22px;color:white;margin:0;">
                ✦ Color Palette — {theme_display}
            </h2>
            <p style="color:rgba(255,255,255,.85);font-size:10px;margin:4px 0 0;font-weight:600;">
                Use these hex codes to customize in Canva, GoodNotes, or your design app
            </p>
        </div>
        <div style="margin-right:36px;">
            {swatches}
        </div>
        <div style="margin-top:20px;margin-right:36px;padding:14px;
             background:{t['light']};border-radius:12px;border-left:4px solid {t['primary']};">
            <p style="font-size:11px;color:{t['text']};margin:0;line-height:1.6;">
                <strong>Tip:</strong> All fonts used are free on Google Fonts —
                search <strong>Quicksand</strong>, <strong>Poppins</strong>,
                and <strong>Fredoka One</strong> at fonts.google.com
            </p>
        </div>
    </div>
    """


def _thank_you_page_html() -> str:
    """Thank You page embedded in every PDF -- top 1% review funnel strategy.

    Why: PDF buyers see this while using the product -> 3-5x review rate vs email alone.
    """
    return """
    <div class="page" style="display:flex; flex-direction:column; align-items:center;
         justify-content:center; text-align:center; background:#FFF8F5; page-break-before:always;">
        <div style="font-size:52px; margin-bottom:20px;">&#x2764;&#xfe0f;</div>
        <h1 style="font-size:32px; color:#E05A2B; margin:0 0 12px;">
            Thank You for Your Purchase!
        </h1>
        <p style="font-size:16px; color:#555; max-width:480px; line-height:1.7; margin:0 0 28px;">
            We hope this planner helps you stay organized and reach your goals.
            If you love it, a 30-second review on Etsy means the world to us --
            and helps us keep adding new printables every week!
        </p>
        <div style="background:#E05A2B; color:white; font-size:18px; font-weight:bold;
             padding:14px 36px; border-radius:30px; margin-bottom:28px; letter-spacing:0.5px;">
            Leave a Review on Etsy &#x2192; Search "DailyPrintHaus"
        </div>
        <p style="font-size:13px; color:#999; margin:0 0 6px;">
            Find matching worksheets, spreadsheets &amp; more printables:
        </p>
        <p style="font-size:15px; color:#E05A2B; font-weight:bold; margin:0;">
            etsy.com/shop/DailyPrintHaus
        </p>
        <div style="margin-top:40px; font-size:12px; color:#ccc;">
            For personal use only. Not for resale or redistribution. &copy; DailyPrintHaus
        </div>
    </div>
    """


SECTION_GENERATORS = {
    "Yearly Overview":   lambda m, pg, t: _yearly_overview_html(pg, t),
    "Monthly":           lambda m, pg, t: _monthly_html((m % 12) + 1, pg, t),
    "Weekly":            lambda m, pg, t: _weekly_html(m + 1, pg, t),
    "Daily":             lambda m, pg, t: _daily_html(pg, t),
    "Habit":             lambda m, pg, t: _habit_tracker_html(pg, t),
    "Gratitude":         lambda m, pg, t: _gratitude_html(pg, t),
    "Budget":            lambda m, pg, t: _budget_html(pg, t),
    "Meal":              lambda m, pg, t: _meal_html(pg, t),
    "Notes":             lambda m, pg, t: _notes_html(pg, t),
    "Monthly Review":    lambda m, pg, t: _monthly_review_html(pg, t),
    "Vision Board":      lambda m, pg, t: _vision_board_html(pg, t),
    "Project Tracker":   lambda m, pg, t: _project_tracker_html(pg, t),
    "Mood":              lambda m, pg, t: _mood_tracker_html(pg, t),
    "Workout Log":       lambda m, pg, t: _workout_log_html(pg, t),
    "Body Measurement":  lambda m, pg, t: _body_measurement_html(pg, t),
}


def generate_planner_html(planner_type: str = "daily",
                          theme_name: str = "pastel_pink",
                          niche: str | None = None) -> Optional[Product]:
    """Generate premium planner using HTML+CSS -> PDF (Letter + A4)."""
    global _current_theme, _current_niche

    base_config = TYPE_CONFIG.get(planner_type, TYPE_CONFIG["daily"])
    niche_cfg   = NICHE_CONFIG.get(niche, {})

    # 니치 적용 — title/subtitle만 오버라이드, 섹션 구조는 동일
    config = dict(base_config)
    if niche_cfg:
        prefix  = niche_cfg.get("title_prefix", "")
        config["title"]    = f"{prefix} {base_config['title']}".strip()
        config["subtitle"] = niche_cfg.get("subtitle_override", base_config["subtitle"])

    t = THEMES.get(theme_name, THEMES["pastel_pink"])
    _current_theme = t
    _current_niche = niche

    product_id = str(uuid.uuid4())[:8]
    product_dir = OUTPUT_DIR / "planner" / product_id
    product_dir.mkdir(parents=True, exist_ok=True)

    # 총 페이지 수 계산 (cover + toc + sections + sticker + color + thankyou)
    total = 2 + 2 + 1  # cover + toc + sticker + color_palette + thank_you
    for _, count in config["sections"]:
        total += count

    # HTML 빌드
    css = _base_css(t)
    toc_entries = []
    pg = 3
    for name, count in config["sections"]:
        toc_entries.append((name, pg))
        pg += count

    pages = _cover_html(config["title"], config["subtitle"], total, style=1)
    pages += _toc_html(toc_entries, t)

    pg = 3
    for section_name, count in config["sections"]:
        gen = SECTION_GENERATORS.get(section_name)
        if gen:
            for i in range(count):
                sec_html = gen(i, pg, total)
                if i == 0:
                    # Clickable anchor for TOC hyperlink navigation
                    sec_id = section_name.lower().replace(" ", "-")
                    sec_html = f'<span id="{sec_id}" style="display:block;"></span>' + sec_html
                pages += sec_html
                pg += 1

    # 스티커 + 컬러 팔레트 안내 페이지 (상위 1% 차별화 요소)
    pages += _sticker_page_html(t)
    pages += _color_palette_page_html(t, theme_name)
    # Thank You page: embedded review funnel (top 1% strategy -- 3-5x review rate vs email alone)
    pages += _thank_you_page_html()

    full_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{pages}</body></html>'
    (product_dir / "preview.html").write_text(full_html, encoding="utf-8")

    # 10개 커버 디자인 번들 HTML (단일 PDF에 10페이지)
    all_covers_html = "".join(
        _cover_html(config["title"], config["subtitle"], total, style=s)
        for s in range(1, 11)
    )

    file_paths = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch()

            from generator.seo_filename import planner_filename
            page = browser.new_page()

            # ── Letter 사이즈 (메인 플래너) ──
            letter_path = str(product_dir / planner_filename(planner_type, "letter", total))
            page.set_content(full_html, wait_until="networkidle")
            page.pdf(path=letter_path, format="Letter", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            file_paths.append(letter_path)
            logger.info("Planner Letter saved: %s (%d pages)", letter_path, total)
            # ── 페이지 수 검증 (상위 1%: 상품 설명 153페이지와 일치해야 함) ──
            _EXPECTED_PAGES = 153
            if total != _EXPECTED_PAGES:
                logger.warning("⚠️ 페이지 수 불일치: 실제 %d페이지 (기대 %d) — SEO '153 Pages' 문구와 불일치!",
                               total, _EXPECTED_PAGES)

            # ── A4 사이즈 (유럽/글로벌) ──
            a4_css = css.replace("size: letter", "size: A4").replace(
                "width: 8.5in", "width: 210mm").replace("height: 11in", "height: 297mm")
            a4_html = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{a4_css}</style></head><body>{pages}</body></html>'
            a4_path = str(product_dir / planner_filename(planner_type, "a4", total))
            page.set_content(a4_html, wait_until="networkidle")
            page.pdf(path=a4_path, format="A4", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            file_paths.append(a4_path)
            logger.info("Planner A4 saved: %s", a4_path)

            # ── 10 Cover Designs PDF (보너스 번들 — 상위 1% 차별화) ──
            covers_html_full = f'<!DOCTYPE html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{all_covers_html}</body></html>'
            covers_path = str(product_dir / f"BONUS_10_Cover_Designs_{planner_type}.pdf")
            page.set_content(covers_html_full, wait_until="networkidle")
            page.pdf(path=covers_path, format="Letter", print_background=True,
                     margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
            file_paths.append(covers_path)
            logger.info("10 Cover Designs PDF saved: %s", covers_path)

            browser.close()
    except Exception as e:
        logger.error("Planner PDF failed: %s", e, exc_info=True)
        return None

    # ── ZIP 패키징 (Letter + A4 → 단일 ZIP) ──
    import zipfile as _zf
    niche_suffix = f"_{niche.lower()}" if niche else ""
    zip_path = product_dir / f"planner_{planner_type}{niche_suffix}_{theme_name}.zip"
    try:
        with _zf.ZipFile(str(zip_path), "w", _zf.ZIP_DEFLATED, compresslevel=6) as zf:
            for fp in file_paths:
                p_fp = Path(fp)
                if p_fp.exists():
                    zf.write(str(p_fp), p_fp.name)
        logger.info("Planner ZIP: %s (%d PDFs)", zip_path.name, len(file_paths))
        etsy_file_paths = [str(zip_path)]
    except Exception as e:
        logger.warning("ZIP 패키징 실패, PDF 단독 사용: %s", e)
        etsy_file_paths = file_paths

    # Type-specific SEO keywords (top search terms per planner type on Etsy/eRank)
    _type_keywords = {
        "daily": [
            "daily planner pdf", "printable daily planner", "daily planner printable",
            "undated daily planner", "digital daily planner", "goodnotes daily planner",
            "day planner printable", "daily schedule planner", "to do list planner",
            f"{total} page planner", "all in one planner", "productivity planner",
            "daily planner instant download", "ipad daily planner", "hourly planner pdf",
        ],
        "weekly": [
            "weekly planner pdf", "printable weekly planner", "weekly planner printable",
            "undated weekly planner", "52 week planner", "digital weekly planner",
            "goodnotes weekly planner", "weekly schedule template", "week at a glance",
            f"{total} page planner", "weekly organizer printable", "monday start planner",
            "weekly planner instant download", "ipad weekly planner", "weekly layout planner",
        ],
        "budget": [
            "budget planner pdf", "printable budget planner", "monthly budget planner",
            "financial planner printable", "expense tracker printable", "money planner pdf",
            "budget tracker printable", "savings planner pdf", "finance planner printable",
            f"{total} page budget planner", "bill tracker printable", "debt payoff planner",
            "budget planner instant download", "personal finance planner", "budget binder printable",
        ],
        "meal": [
            "meal planner pdf", "printable meal planner", "weekly meal planner",
            "meal prep planner", "grocery list planner", "meal planning printable",
            "food planner printable", "dinner planner pdf", "menu planner printable",
            f"{total} page meal planner", "weekly dinner planner", "shopping list planner",
            "meal planner instant download", "family meal planner", "clean eating planner",
        ],
        "habit_tracker": [
            "habit tracker pdf", "printable habit tracker", "monthly habit tracker",
            "daily habit tracker", "habit planner printable", "routine tracker printable",
            "goal tracker pdf", "habit builder printable", "streak tracker pdf",
            f"{total} page habit tracker", "12 month habit tracker", "daily routine planner",
            "habit tracker instant download", "self improvement tracker", "wellness tracker pdf",
        ],
        "gratitude": [
            "gratitude journal pdf", "printable gratitude journal", "daily gratitude journal",
            "mindfulness journal printable", "gratitude planner pdf", "self care journal printable",
            "affirmation journal pdf", "positivity journal printable", "mental health journal",
            f"{total} page gratitude journal", "365 day gratitude journal", "mindset journal pdf",
            "gratitude journal instant download", "reflection journal printable", "morning journal pdf",
        ],
        "goal_setting": [
            "goal setting planner pdf", "printable goal planner", "90 day planner pdf",
            "goal tracker printable", "vision planner pdf", "action plan planner",
            "goal journal printable", "success planner pdf", "achievement planner",
            f"{total} page goal planner", "goal setting worksheet", "quarterly planner pdf",
            "goal planner instant download", "dream planner printable", "manifestation planner",
        ],
        "fitness": [
            "fitness planner pdf", "printable workout planner", "workout log printable",
            "exercise tracker pdf", "gym planner printable", "fitness journal pdf",
            "workout tracker printable", "body measurement tracker", "fitness log pdf",
            f"{total} page fitness planner", "12 month workout planner", "strength training log",
            "fitness planner instant download", "weight loss tracker printable", "cardio log pdf",
        ],
    }
    keywords = list(_type_keywords.get(planner_type, _type_keywords["daily"]))
    # 니치 키워드 앞에 삽입 (Etsy 태그 13개 한도 내에서 우선순위 높임)
    niche_kw = NICHE_CONFIG.get(niche, {}).get("seo_keywords", [])
    if niche_kw:
        keywords = niche_kw[:8] + keywords  # 니치 8개 + 기본 7개 = 15개

    product = Product(
        product_id=product_id,
        category=Category.PLANNER,
        style=f"{planner_type}_{theme_name}" + (f"_{niche}" if niche else ""),
        keywords=keywords,
        file_paths=etsy_file_paths,
        sizes=["letter", "A4"],
        status=ProductStatus.CREATED,
    )
    logger.info("Premium planner created: %s (type=%s, pages=%d)", product_id, planner_type, total)
    return product


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    p = generate_planner_html("daily", "pastel_pink")
    if p:
        print(f"Generated: {p.product_id}")
        print(f"Files: {p.file_paths}")
