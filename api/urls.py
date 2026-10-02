from rest_framework.routers import DefaultRouter
from django.urls import include, path

from api.views import ProjectViewSet, QuestionAnswerView, VivaSessionViewSet

router = DefaultRouter()
router.register("projects", ProjectViewSet, basename="api-project")
router.register("vivas", VivaSessionViewSet, basename="api-viva")

urlpatterns = [
    path("", include(router.urls)),
    path("questions/<int:question_id>/answer/", QuestionAnswerView.as_view(), name="api-answer"),
]