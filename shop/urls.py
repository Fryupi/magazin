from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'categories', views.CategoryViewSet)
router.register(r'products', views.ProductViewSet)
router.register(r'cart', views.CartItemViewSet, basename='cart')
router.register(r'orders', views.OrderViewSet, basename='order')
router.register(r'reviews', views.ReviewViewSet)

urlpatterns = [
    # Web views
    path('', views.index, name='index'),
    path('register/', views.register_view, name='register'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('product/<int:pk>/', views.product_detail, name='product_detail'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    path('profile/add-balance/', views.add_balance, name='add_balance'),
    path('profile/confirm-order/<int:order_id>/', views.confirm_order_received, name='confirm_order_received'),
    path('seller/', views.seller_dashboard, name='seller_dashboard'),
    path('seller/add-stock/<int:product_id>/', views.add_product_stock, name='add_product_stock'),
    
    # API
    path('api/', include(router.urls)),
]
