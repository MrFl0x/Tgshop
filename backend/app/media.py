"""
Локальное файловое хранилище для картинок товаров (обложки), которые
редактор загружает прямо из формы в /admin — без ручной публикации файла
на CDN и вставки ссылки. Реализовано через fastapi-storages/Pillow (см.
Product.image_upload в app/models.py) — сохранённый файл лежит в MEDIA_ROOT,
FastAPI отдаёт его статикой по MEDIA_URL_PREFIX (см. app/main.py).

Важно: это хранилище на локальном диске процесса. На хостинге с эфемерной
файловой системой (например, Render на бесплатном плане) файлы пропадут при
рестарте/редеплое — для реального продакшена нужно заменить FileSystemStorage
на fastapi_storages.S3Storage (интерфейс ImageType не меняется).
"""
import os
from pathlib import Path

from fastapi_storages import FileSystemStorage

MEDIA_ROOT = Path(os.getenv("MEDIA_ROOT", Path(__file__).resolve().parent.parent / "media"))
MEDIA_URL_PREFIX = "/media"

product_images_storage = FileSystemStorage(path=str(MEDIA_ROOT))


def image_public_url(image) -> str:
    """StorageImage/StorageFile -> публичный URL под MEDIA_URL_PREFIX."""
    return f"{MEDIA_URL_PREFIX}/{image.name}"
