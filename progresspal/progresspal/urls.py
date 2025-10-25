"""
URL configuration for progresspal project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls import url
import accounts.views as accounts
import learning.views as learning

urlpatterns = [
    path('', learning.homepage, name='homepage'),
    path('admin/', admin.site.urls),
    # 使用者相關
    path('user/register/', accounts.register, name='register'),# 註冊頁面
    path('user/login/', accounts.login_view, name='login'), # 登入頁面
    path('user/logout/', accounts.logout_view, name='logout'), # 登出動作
    path('user/profile/', accounts.profile, name='profile'),  # 會員中心（需登入）
    path('user/delete/', accounts.delete_account, name='delete_account'),  # 刪除帳號（需登入）
    path('user/study/', accounts.learning_portfolio, name='learning-portfolio'),  # 學習歷程頁面
    # 學習相關
    path('lessons/', learning.lessons, name='lessons'),  # 學習章節列表頁面
    # path('lesson/<int:chapter_code>/<int:unit_code>/study/', learning.study_view, name='learning'),  #學習頁面

]
