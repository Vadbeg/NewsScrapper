from django.urls import path

from .views import (index,
                    rss_source,
                    download_fb2,
                    download_pdf,
                    PostListView,
                    DatePostListView,
                    RSSPostListView,
                    SearchResultView,
                    remove_news)


urlpatterns = [
    path('', index, name='index'),
    path('home/rss', rss_source, name='rrs_source'),
    path('home/', PostListView.as_view(), name='home'),
    path('home/date/<str:date_id>',
         DatePostListView.as_view(),
         name='news-by-date'),
    path('home/rss_source/<str:rss_hash>',
         RSSPostListView.as_view(),
         name='news-by-rss'),
    path('home/search/',
         SearchResultView.as_view(),
         name='search-result'),
    path('home/remove',
         remove_news,
         name='remove-news'),
    path('render/pdf/<str:posts>',
         download_pdf,
         name='to-pdf'),
    path('render/fb2/<str:posts>',
         download_fb2,
         name='to-fb2')
]
