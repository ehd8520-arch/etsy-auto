"""
SEO 파일명 생성 유틸리티

Why: Etsy는 업로드한 파일명 그대로 고객에게 전달됨.
     고객이 다운로드한 파일명 = 브랜드 경험 + SEO 시그널.
     상위 1% 셀러: 'Kids-Math-Addition-Worksheet-Printable-152-Pages-Letter.pdf'
     일반 셀러:    'math_addition_letter.pdf'

적용 규칙:
- 단어 구분: hyphen (-)
- 대소문자: Title-Case
- 키워드 순서: [카테고리] - [타입] - [특성] - [포맷] - [사이즈]
- 최대 60자 (파일 시스템 호환)
"""

# ── 워크시트 파일명 맵 ──
_WS_OPERATION_NAMES = {
    "addition":       "Math-Addition-Worksheet",
    "subtraction":    "Math-Subtraction-Worksheet",
    "multiplication": "Math-Multiplication-Worksheet",
    "division":       "Math-Division-Worksheet",
    "tracing_letters":"Alphabet-Tracing-Worksheet",
    "tracing_numbers":"Number-Tracing-Worksheet",
    "tracing_shapes": "Shape-Tracing-Worksheet",
    "sight_words":    "Sight-Words-Practice-Worksheet",
    "handwriting":    "Handwriting-Practice-Worksheet",
}

# ── 플래너 파일명 맵 ──
_PL_TYPE_NAMES = {
    "daily":          "Daily-Planner-Printable-Undated",
    "weekly":         "Weekly-Planner-Printable-Undated",
    "monthly":        "Monthly-Planner-Printable-Undated",
    "yearly":         "Yearly-Planner-Printable",
    "budget":         "Budget-Planner-Printable",
    "meal":           "Meal-Planner-Printable",
    "fitness":        "Fitness-Planner-Printable",
    "habit_tracker":  "Habit-Tracker-Planner-Printable",
    "goal_setting":   "Goal-Setting-Planner-Printable",
    "gratitude":      "Gratitude-Journal-Planner-Printable",
    "reading_log":    "Reading-Log-Planner-Printable",
}

# ── 스프레드시트 파일명 맵 ──
_SS_TYPE_NAMES = {
    "monthly_budget":  "Monthly-Budget-Spreadsheet-Google-Sheets-Excel",
    "debt_payoff":     "Debt-Payoff-Tracker-Spreadsheet-Google-Sheets",
    "savings_tracker": "Savings-Tracker-Spreadsheet-Google-Sheets-Excel",
    "wedding_budget":  "Wedding-Budget-Planner-Spreadsheet-Google-Sheets",
    "small_business":  "Small-Business-Budget-Tracker-Spreadsheet",
}

# ── 사이즈 표기 ──
_SIZE_LABELS = {
    "letter": "US-Letter",
    "a4":     "A4",
    "both":   "Letter-and-A4",
}


def worksheet_filename(operation: str, size: str = "letter", page_count: int = 152) -> str:
    """워크시트 SEO 파일명 생성.

    Examples:
        'addition', 'letter' -> 'Kids-Math-Addition-Worksheet-Printable-152-Pages-US-Letter.pdf'
    """
    base = _WS_OPERATION_NAMES.get(operation, f"{operation.replace('_', '-').title()}-Worksheet")
    size_label = _SIZE_LABELS.get(size.lower(), size.upper())
    name = f"Kids-{base}-Printable-{page_count}-Pages-{size_label}"
    return f"{name[:80]}.pdf"


def planner_filename(planner_type: str, size: str = "letter", page_count: int = 149) -> str:
    """플래너 SEO 파일명 생성.

    Examples:
        'daily', 'letter' -> 'Daily-Planner-Printable-Undated-149-Pages-US-Letter-PDF.pdf'
    """
    base = _PL_TYPE_NAMES.get(planner_type, f"{planner_type.replace('_', '-').title()}-Planner-Printable")
    size_label = _SIZE_LABELS.get(size.lower(), size.upper())
    name = f"{base}-{page_count}-Pages-{size_label}-PDF"
    return f"{name[:80]}.pdf"


def spreadsheet_filename(ss_type: str) -> str:
    """스프레드시트 SEO 파일명 생성.

    Examples:
        'monthly_budget' -> 'Monthly-Budget-Spreadsheet-Google-Sheets-Excel-Template.xlsx'
    """
    base = _SS_TYPE_NAMES.get(ss_type, f"{ss_type.replace('_', '-').title()}-Spreadsheet")
    name = f"{base}-Template"
    return f"{name[:80]}.xlsx"


def bundle_filename(category: str, theme: str = "") -> str:
    """번들 ZIP 파일명 생성."""
    cat_map = {
        "worksheet":   "Kids-Printable-Worksheet-Bundle-Mega-Pack",
        "planner":     "Printable-Planner-Bundle-Undated-PDF",
        "spreadsheet": "Budget-Spreadsheet-Bundle-Google-Sheets-Excel",
    }
    base = cat_map.get(category, f"{category.title()}-Bundle")
    return f"{base}-Instant-Download.zip"
