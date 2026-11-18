from __future__ import annotations

import re


INJECTION_PATTERNS = (
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"reveal\s+(the\s+)?(system\s+prompt|api\s*key|secret)",
    r"you\s+are\s+now",
    r"bypass\s+(the\s+)?(security|guardrails|rules)",
    r"تجاهل\s+(جميع\s+)?التعليمات",
    r"اعرض\s+(المفتاح|السر|الإعدادات)",
)

EMAIL_PATTERN = re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}")
IDENTIFIER_PATTERN = re.compile(r"(?<!\d)\d{9,16}(?!\d)")
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+966|00966|05)\s?\d{8,9}(?!\d)")


class SecurityGuardrails:
    @staticmethod
    def validate_input(user_input: str) -> tuple[bool, str]:
        if not isinstance(user_input, str):
            return False, "يجب أن يكون الطلب نصًا."
        if not user_input.strip():
            return False, "الطلب فارغ."
        if len(user_input) > 500:
            return False, "الطلب يتجاوز الحد المسموح وهو 500 حرف."

        normalized = re.sub(r"\s+", " ", user_input.lower())
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, normalized, re.IGNORECASE):
                return False, "تم رفض الطلب لأسباب أمنية: تم اكتشاف محاولة حقن أوامر."
        return True, "الطلب اجتاز فحص الأمان."

    @staticmethod
    def mask_pii(text: str) -> str:
        masked = IDENTIFIER_PATTERN.sub("[REDACTED_ID]", text)
        masked = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", masked)
        masked = PHONE_PATTERN.sub("[REDACTED_PHONE]", masked)
        return masked

    @staticmethod
    def validate_output(plan: dict | None, max_budget: float) -> tuple[bool, str]:
        if not plan:
            return False, "لا توجد خطة سفر صالحة."
        price = plan.get("total_price_sar")
        if price is None:
            return False, "مخرجات الخطة لا تحتوي سعرًا صحيحًا."
        if not isinstance(price, (int, float)):
            return False, "مخرجات الخطة تحتوي سعرًا غير صالح."
        if price > max_budget:
            return False, "السعر يتجاوز ميزانية المستخدم."
        return True, "الخرج آمن ومطابق للميزانية."
