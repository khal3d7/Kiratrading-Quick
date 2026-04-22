from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton("🆕 الصفقات الجديدة", callback_data="trades:new"),
         InlineKeyboardButton("🔄 الصفقات الجارية", callback_data="trades:open")],
        [InlineKeyboardButton("⚡ الصفقات السريعة", callback_data="quick:open"),
         InlineKeyboardButton("⚡ سجل السريعة", callback_data="quick:closed")],
        [InlineKeyboardButton("✅ الصفقات المنتهية", callback_data="trades:closed"),
         InlineKeyboardButton("📊 الإحصائيات", callback_data="stats")],
        [InlineKeyboardButton("📈 تقرير الأداء", callback_data="report"),
         InlineKeyboardButton("⚙️ الإعدادات", callback_data="settings")],
        [InlineKeyboardButton("🔔 الإشعارات", callback_data="notifications")],
    ]
    return InlineKeyboardMarkup(rows)


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ رجوع", callback_data="menu")]])


def pagination(prefix: str, page: int, has_next: bool) -> InlineKeyboardMarkup:
    row = []
    if page > 0:
        row.append(InlineKeyboardButton("◀️ السابق", callback_data=f"{prefix}:{page-1}"))
    if has_next:
        row.append(InlineKeyboardButton("التالي ▶️", callback_data=f"{prefix}:{page+1}"))
    rows = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton("⬅️ القائمة", callback_data="menu")])
    return InlineKeyboardMarkup(rows)
