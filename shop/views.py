from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from rest_framework import viewsets, status
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import User, Category, Product, CartItem, Order, Review
from .serializers import (UserSerializer, CategorySerializer, ProductSerializer, 
                          CartItemSerializer, OrderSerializer, ReviewSerializer)


# Web Views
def index(request):
    products = Product.objects.all()[:12]
    categories = Category.objects.all()
    return render(request, 'index.html', {'products': products, 'categories': categories})


def register_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password = request.POST.get('password')
        user_type = request.POST.get('user_type', 'buyer')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Пользователь с таким именем уже существует')
            return redirect('register')
        
        user = User.objects.create_user(username=username, email=email, password=password, user_type=user_type)
        user.balance = 10000  # Начальный баланс
        user.save()
        login(request, user)
        messages.success(request, 'Регистрация успешна!')
        return redirect('index')
    
    return render(request, 'register.html')


def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user:
            login(request, user)
            messages.success(request, 'Вход выполнен успешно!')
            return redirect('index')
        else:
            messages.error(request, 'Неверное имя пользователя или пароль')
    
    return render(request, 'login.html')


def logout_view(request):
    logout(request)
    messages.success(request, 'Вы вышли из системы')
    return redirect('index')


def product_detail(request, pk):
    product = get_object_or_404(Product, pk=pk)
    reviews = product.reviews.all()
    return render(request, 'product_detail.html', {'product': product, 'reviews': reviews})


@login_required
def profile_view(request):
    cart_items = CartItem.objects.filter(user=request.user)
    # Активные заказы (не в истории)
    active_orders = Order.objects.filter(
        buyer=request.user,
        status__in=['pending', 'accepted', 'processing', 'shipped', 'delivered']
    ).exclude(is_received=True).order_by('-created_at')
    
    # История заказов (получены или отменены)
    history_orders = Order.objects.filter(
        buyer=request.user
    ).filter(
        Q(status__in=['received', 'cancelled']) | Q(is_received=True)
    ).order_by('-created_at')
    
    return render(request, 'profile.html', {
        'cart_items': cart_items,
        'active_orders': active_orders,
        'history_orders': history_orders
    })


@login_required
def edit_profile(request):
    """Редактирование личных данных"""
    if request.method == 'POST':
        # Получаем данные из формы
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        email = request.POST.get('email', '').strip()
        phone = request.POST.get('phone', '').strip()
        address = request.POST.get('address', '').strip()
        
        # Проверяем email на уникальность
        if email and email != request.user.email:
            if User.objects.filter(email=email).exclude(id=request.user.id).exists():
                messages.error(request, 'Пользователь с таким email уже существует')
                return redirect('edit_profile')
        
        # Обновляем данные
        request.user.first_name = first_name
        request.user.last_name = last_name
        request.user.email = email
        request.user.phone = phone
        request.user.address = address
        request.user.save()
        
        messages.success(request, 'Личные данные успешно обновлены!')
        return redirect('profile')
    
    return render(request, 'edit_profile.html')


@login_required
def add_balance(request):
    """Пополнение баланса"""
    if request.method == 'POST':
        try:
            amount = float(request.POST.get('amount', 0))
            if amount <= 0:
                messages.error(request, 'Сумма должна быть больше нуля')
            elif amount > 1000000:
                messages.error(request, 'Максимальная сумма пополнения: 1,000,000 ₽')
            else:
                request.user.balance = float(request.user.balance) + amount
                request.user.save()
                messages.success(request, f'Баланс пополнен на {amount:,.2f} ₽')
        except (ValueError, TypeError):
            messages.error(request, 'Неверная сумма')
    
    return redirect('profile')


@login_required
def confirm_order_received(request, order_id):
    """Подтверждение получения заказа покупателем"""
    order = get_object_or_404(Order, id=order_id, buyer=request.user)
    
    if order.status not in ['delivered', 'received']:
        messages.error(request, 'Заказ ещё не доставлен')
    elif order.is_received:
        messages.info(request, 'Заказ уже подтверждён')
    else:
        order.is_received = True
        order.status = 'received'
        order.save()
        messages.success(request, 'Спасибо! Получение заказа подтверждено')
    
    return redirect('profile')


@login_required
def add_product_stock(request, product_id):
    """Пополнение количества товара"""
    product = get_object_or_404(Product, id=product_id, seller=request.user)
    
    if request.method == 'POST':
        try:
            quantity = int(request.POST.get('quantity', 0))
            if quantity <= 0:
                messages.error(request, 'Количество должно быть больше нуля')
            elif quantity > 10000:
                messages.error(request, 'Максимальное количество: 10,000 шт.')
            else:
                product.stock += quantity
                product.save()
                messages.success(request, f'Добавлено {quantity} шт. к товару "{product.name}"')
        except (ValueError, TypeError):
            messages.error(request, 'Неверное количество')
    
    return redirect('seller_dashboard')


@login_required
def seller_dashboard(request):
    if request.user.user_type != 'seller':
        messages.error(request, 'Доступ запрещен')
        return redirect('index')
    
    # Товары продавца
    products = Product.objects.filter(seller=request.user)
    
    # Активные заказы (не в истории)
    active_orders = Order.objects.filter(
        seller=request.user,
        status__in=['pending', 'accepted', 'processing', 'shipped', 'delivered']
    ).exclude(is_received=True).order_by('-created_at')
    
    # История заказов (получены или отменены)
    history_orders = Order.objects.filter(
        seller=request.user
    ).filter(
        Q(status__in=['received', 'cancelled']) | Q(is_received=True)
    ).order_by('-created_at')
    
    # Статистика
    from django.db.models import Sum, Count, Avg
    from decimal import Decimal
    
    # Общая статистика
    total_products = products.count()
    total_orders = Order.objects.filter(seller=request.user).count()
    active_orders_count = active_orders.count()
    completed_orders_count = history_orders.filter(status='received').count()
    
    # Финансовая статистика
    total_revenue = Order.objects.filter(
        seller=request.user,
        status='received'
    ).aggregate(total=Sum('total_price'))['total'] or Decimal('0')
    
    pending_revenue = active_orders.aggregate(
        total=Sum('total_price')
    )['total'] or Decimal('0')
    
    # Статистика по товарам
    total_stock = products.aggregate(total=Sum('stock'))['total'] or 0
    avg_price = products.aggregate(avg=Avg('price'))['avg'] or Decimal('0')
    
    # Популярные товары (по количеству заказов)
    from django.db.models import Count as CountFunc
    popular_products = Product.objects.filter(
        seller=request.user,
        order__status='received'
    ).annotate(
        orders_count=CountFunc('order')
    ).order_by('-orders_count')[:5]
    
    # Статистика по статусам
    status_stats = {}
    for status_code, status_name in Order.STATUS_CHOICES:
        count = Order.objects.filter(
            seller=request.user,
            status=status_code
        ).count()
        if count > 0:
            status_stats[status_name] = count
    
    context = {
        'products': products,
        'active_orders': active_orders,
        'history_orders': history_orders,
        'stats': {
            'total_products': total_products,
            'total_orders': total_orders,
            'active_orders': active_orders_count,
            'completed_orders': completed_orders_count,
            'total_revenue': total_revenue,
            'pending_revenue': pending_revenue,
            'total_stock': total_stock,
            'avg_price': avg_price,
            'popular_products': popular_products,
            'status_stats': status_stats,
        }
    }
    
    return render(request, 'seller_dashboard.html', context)


# API ViewSets
class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'], permission_classes=[IsAuthenticated])
    def add_balance(self, request):
        """API для пополнения баланса"""
        try:
            amount = float(request.data.get('amount', 0))
            if amount <= 0:
                return Response({'error': 'Сумма должна быть больше нуля'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            if amount > 1000000:
                return Response({'error': 'Максимальная сумма: 1,000,000 ₽'}, 
                              status=status.HTTP_400_BAD_REQUEST)
            
            request.user.balance = float(request.user.balance) + amount
            request.user.save()
            
            serializer = self.get_serializer(request.user)
            return Response({
                'message': f'Баланс пополнен на {amount:,.2f} ₽',
                'user': serializer.data
            })
        except (ValueError, TypeError):
            return Response({'error': 'Неверная сумма'}, 
                          status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_profile(self, request):
        """API для обновления личных данных"""
        user = request.user
        
        # Получаем данные
        first_name = request.data.get('first_name')
        last_name = request.data.get('last_name')
        email = request.data.get('email')
        phone = request.data.get('phone')
        address = request.data.get('address')
        
        # Проверяем email на уникальность
        if email and email != user.email:
            if User.objects.filter(email=email).exclude(id=user.id).exists():
                return Response({'error': 'Пользователь с таким email уже существует'}, 
                              status=status.HTTP_400_BAD_REQUEST)
        
        # Обновляем данные
        if first_name is not None:
            user.first_name = first_name
        if last_name is not None:
            user.last_name = last_name
        if email is not None:
            user.email = email
        if phone is not None:
            user.phone = phone
        if address is not None:
            user.address = address
        
        user.save()
        
        serializer = self.get_serializer(user)
        return Response({
            'message': 'Личные данные успешно обновлены',
            'user': serializer.data
        })


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    
    def get_queryset(self):
        queryset = Product.objects.all()
        category = self.request.query_params.get('category', None)
        search = self.request.query_params.get('search', None)
        
        if category:
            queryset = queryset.filter(category_id=category)
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(description__icontains=search))
        
        return queryset
    
    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)


class CartItemViewSet(viewsets.ModelViewSet):
    serializer_class = CartItemSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user)
    
    def create(self, request):
        product_id = request.data.get('product_id')
        quantity = int(request.data.get('quantity', 1))
        
        product = get_object_or_404(Product, id=product_id)
        
        # Проверка наличия товара
        if product.stock <= 0:
            return Response(
                {'error': 'Товар отсутствует на складе'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if product.stock < quantity:
            return Response(
                {'error': f'Недостаточно товара. Доступно: {product.stock} шт.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        cart_item, created = CartItem.objects.get_or_create(
            user=request.user,
            product=product,
            defaults={'quantity': quantity}
        )
        
        if not created:
            new_quantity = cart_item.quantity + quantity
            if new_quantity > product.stock:
                return Response(
                    {'error': f'Недостаточно товара. Доступно: {product.stock} шт., в корзине: {cart_item.quantity} шт.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            cart_item.quantity = new_quantity
            cart_item.save()
        
        serializer = self.get_serializer(cart_item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        user = self.request.user
        if user.user_type == 'seller':
            return Order.objects.filter(seller=user)
        return Order.objects.filter(buyer=user)
    
    def create(self, request):
        cart_item_id = request.data.get('cart_item_id')
        cart_item = get_object_or_404(CartItem, id=cart_item_id, user=request.user)
        
        if cart_item.product.stock < cart_item.quantity:
            return Response({'error': 'Недостаточно товара на складе'}, status=status.HTTP_400_BAD_REQUEST)
        
        total_price = cart_item.total_price
        
        if request.user.balance < total_price:
            return Response({'error': 'Недостаточно средств на балансе'}, status=status.HTTP_400_BAD_REQUEST)
        
        # Создаем заказ
        order = Order.objects.create(
            buyer=request.user,
            seller=cart_item.product.seller,
            product=cart_item.product,
            quantity=cart_item.quantity,
            total_price=total_price
        )
        
        # Списываем средства
        request.user.balance -= total_price
        request.user.save()
        
        # Обновляем склад
        cart_item.product.stock -= cart_item.quantity
        cart_item.product.save()
        
        # Удаляем из корзины
        cart_item.delete()
        
        serializer = self.get_serializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['patch'], permission_classes=[IsAuthenticated])
    def update_status(self, request, pk=None):
        order = self.get_object()
        
        if order.seller != request.user:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        new_status = request.data.get('status')
        if new_status in dict(Order.STATUS_CHOICES):
            order.status = new_status
            order.save()
            serializer = self.get_serializer(order)
            return Response(serializer.data)
        
        return Response({'error': 'Неверный статус'}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticated])
    def confirm_received(self, request, pk=None):
        """Подтверждение получения заказа покупателем"""
        order = self.get_object()
        
        if order.buyer != request.user:
            return Response({'error': 'Доступ запрещен'}, status=status.HTTP_403_FORBIDDEN)
        
        if order.status not in ['delivered', 'received']:
            return Response({'error': 'Заказ ещё не доставлен'}, status=status.HTTP_400_BAD_REQUEST)
        
        if order.is_received:
            return Response({'message': 'Заказ уже подтверждён'}, status=status.HTTP_200_OK)
        
        order.is_received = True
        order.status = 'received'
        order.save()
        
        serializer = self.get_serializer(order)
        return Response({
            'message': 'Получение заказа подтверждено',
            'order': serializer.data
        })


class ReviewViewSet(viewsets.ModelViewSet):
    queryset = Review.objects.all()
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]
    
    def create(self, request, *args, **kwargs):
        product_id = request.data.get('product')
        rating = request.data.get('rating')
        comment = request.data.get('comment')
        
        if not product_id:
            return Response({'error': 'Не указан товар'}, status=status.HTTP_400_BAD_REQUEST)
        
        try:
            product = Product.objects.get(id=product_id)
        except Product.DoesNotExist:
            return Response({'error': 'Товар не найден'}, status=status.HTTP_404_NOT_FOUND)
        
        # Проверяем, не оставлял ли пользователь уже отзыв
        if Review.objects.filter(product=product, user=request.user).exists():
            return Response({'error': 'Вы уже оставили отзыв на этот товар'}, status=status.HTTP_400_BAD_REQUEST)
        
        review = Review.objects.create(
            product=product,
            user=request.user,
            rating=rating,
            comment=comment
        )
        
        serializer = self.get_serializer(review)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
