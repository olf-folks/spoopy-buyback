from .base import *

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config("DEBUG", default=False, cast=bool)


MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "../", "mediafiles")
STATIC_URL = "http://157.250.203.42/static/"
#STATIC_ROOT = os.path.join(BASE_DIR, "../", "staticfiles")



#SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
#

print("Django production settings loaded successfully")