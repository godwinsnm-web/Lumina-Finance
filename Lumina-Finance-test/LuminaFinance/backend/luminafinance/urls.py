from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView

# ensure_csrf_cookie guarantees the browser holds a csrftoken cookie before any
# POST is attempted (login/logout). Without it, the first POST has no token
# to echo back as X-CSRFToken and Django rejects it.
index_view = ensure_csrf_cookie(TemplateView.as_view(template_name="index.html"))

urlpatterns = [
    path("", index_view, name="dashboard"),
    path("api/", include("api.urls")),
]
