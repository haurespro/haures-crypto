#!/bin/bash

# تحديث مستودعات الحزم وتثبيت مكتبات التطوير الأساسية
apt-get update -y
apt-get install -y libpq-dev libssl-dev libffi-dev build-essential python3-dev

# ثم قم بتشغيل أمر التثبيت الطبيعي لـ pip
pip install -r requirements.txt
