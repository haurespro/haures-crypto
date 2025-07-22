#!/bin/bash

# تحديث مستودعات الحزم
apt-get update -y

# تثبيت أدوات البناء الأساسية والمكتبات الضرورية
apt-get install -y \
    build-essential \
    python3-dev \
    libpq-dev \
    libssl-dev \
    libffi-dev \
    pkg-config \
    zlib1g-dev \
    libxml2-dev \
    libxslt1-dev # هذه المكتبات قد لا تكون ضرورية لـ aiohttp مباشرة، لكنها تغطي حالات تجميع أخرى

# ثم قم بتشغيل أمر التثبيت الطبيعي لـ pip
pip install -r requirements.txt
