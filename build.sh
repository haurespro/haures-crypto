#!/bin/bash

# تحديث مستودعات الحزم
apt-get update -y

# تثبيت أدوات البناء الأساسية والمكتبات الضرورية
apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    libssl-dev \
    libffi-dev

# ثم قم بتشغيل أمر التثبيت الطبيعي لـ pip
pip install -r requirements.txt
