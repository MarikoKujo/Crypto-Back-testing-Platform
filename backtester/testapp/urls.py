from django.conf.urls import url

from . import views

app_name = 'testapp'
urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^results/$', views.results, name='results'),
    url(r'^processing/$', views.processing, name='processing')
]