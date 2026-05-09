from django.urls import path

from . import views

urlpatterns = [
    path("login/",     views.login,     name="login"),
    path("register/",  views.register,  name="register"),
    path("logout/",    views.logout,    name="logout"),
    path("me/",        views.me,        name="me"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("add-transaction/", views.add_transaction, name="add_transaction"),
    path("delete-transaction/<int:txn_id>/", views.delete_transaction, name="delete_transaction"),
]
