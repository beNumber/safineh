import shutil
from pathlib import Path

root = Path.cwd()  # دایرکتوری فعلی که اسکریپت رو اجرا می‌کنی

removed = 0
for pycache in root.rglob("__pycache__"):
    if pycache.is_dir():
        shutil.rmtree(pycache, ignore_errors=True)
        removed += 1
        print(f"🗑️ حذف شد: {pycache}")

print(f"\n✅ در مجموع {removed} پوشه‌ی __pycache__ حذف شد.")
