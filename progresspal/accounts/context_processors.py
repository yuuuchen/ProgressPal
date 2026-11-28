from urllib.parse import quote

from django.conf import settings


def experiment_forms(request):
    """
    提供 navbar 的 Google 表單連結。網址中的 {participant_id} 會換成目前登入的受試者編號
    （Google 表單預填連結），未登入時換成空字串。
    """
    user = getattr(request, "user", None)
    participant_id = user.username if user is not None and user.is_authenticated else ""

    def fill(url):
        return url.replace("{participant_id}", quote(participant_id))

    return {
        "form_pretest_url": fill(settings.FORM_PRETEST_URL),
        "form_posttest_url": fill(settings.FORM_POSTTEST_URL),
    }
