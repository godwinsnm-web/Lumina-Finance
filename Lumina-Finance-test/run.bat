@echo off
cd LuminaFinance\backend

if not exist .venv\Scripts\activate.bat (
    echo Creating virtual environment...
    python -m venv .venv
    call .venv\Scripts\activate.bat
    echo Installing dependencies...
    pip install -r requirements.txt
) else (
    call .venv\Scripts\activate.bat
)

echo Applying database migrations...
python manage.py migrate

echo Starting server...
python manage.py runserver
pause
