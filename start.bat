@echo off
chcp 65001 >nul
cls
echo ========================================
echo   Запуск приложения Магазин
echo ========================================
echo.

set PYTHON=C:\Users\dmitr\AppData\Local\Programs\Python\Python310\python.exe

echo Применение миграций...
%PYTHON% manage.py migrate

echo.
echo Проверка файла инициализации...
if exist init_db.py (
    echo Инициализация тестовых данных...
    %PYTHON% init_db.py
) else (
    echo Файл init_db.py не найден, пропускаем инициализацию
)

echo.
echo ========================================
echo   Запуск сервера разработки...
echo ========================================
echo.
echo Приложение будет доступно по адресу:
echo http://127.0.0.1:8000/
echo.
echo Для создания администратора выполните:
echo CREATE_ADMIN.bat
echo.
echo Для остановки сервера нажмите Ctrl+C
echo ========================================
echo.

%PYTHON% manage.py runserver
