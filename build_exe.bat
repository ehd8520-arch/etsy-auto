@echo off
chcp 65001 >nul
echo ========================================
echo  DailyPrintHaus GUI exe 빌드
echo ========================================
cd /d "%~dp0"

pip install pyinstaller >nul 2>&1

pyinstaller ^
  --onefile ^
  --windowed ^
  --name "DailyPrintHaus" ^
  --icon NONE ^
  --add-data ".env;." ^
  --add-data "config;config" ^
  --add-data "generator;generator" ^
  --add-data "publisher;publisher" ^
  --add-data "seo;seo" ^
  --add-data "db;db" ^
  --add-data "monitor;monitor" ^
  --add-data "optimizer;optimizer" ^
  --hidden-import playwright ^
  --hidden-import dotenv ^
  --hidden-import PIL ^
  --hidden-import requests ^
  --hidden-import google.generativeai ^
  gui.py

echo.
if exist "dist\DailyPrintHaus.exe" (
  echo ✅ 빌드 완료!
  echo 파일: dist\DailyPrintHaus.exe
  copy "dist\DailyPrintHaus.exe" "%USERPROFILE%\Desktop\DailyPrintHaus.exe"
  echo 바탕화면에 복사 완료!
) else (
  echo ❌ 빌드 실패
)
pause
