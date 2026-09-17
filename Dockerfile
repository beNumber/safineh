FROM mirror2.chabokan.net/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

# نصب nginx و ابزارهای لازم
RUN apt-get update && apt-get install -y --no-install-recommends \
    nginx \
    && rm -rf /var/lib/apt/lists/*

# نصب وابستگی‌های پایتون
COPY requirements.txt /code/

RUN pip install -i https://package-mirror.liara.ir/repository/pypi/simple --upgrade pip
RUN pip install -i https://package-mirror.liara.ir/repository/pypi/simple -r requirements.txt

# کپی پروژه
COPY . /code/

# کپی تنظیمات nginx
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf

# اسکریپت اجرای web
COPY docker/start-web.sh /start-web.sh
RUN chmod +x /start-web.sh

# حذف کانفیگ پیش‌فرض nginx اگر وجود داشت
RUN rm -f /etc/nginx/sites-enabled/default

EXPOSE 80

CMD ["/start-web.sh"]
