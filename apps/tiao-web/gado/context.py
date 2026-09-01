"""Things every page needs, without every view having to remember them."""

from django.conf import settings


def tiao(request):
    return {"bot_telegram": settings.TELEGRAM_BOT}
