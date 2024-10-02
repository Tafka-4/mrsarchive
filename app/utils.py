import bleach
import re
import base64
import requests

from io import BytesIO
from bleach.css_sanitizer import CSSSanitizer

allowed_tags = [
    'b', 'i', 'u', 's', 'span', 'img'
]

allowed_attributes = {
    'span': ['style'],
    'img': ['src', 'alt', 'title']
}

allowed_styles = [
    'color', 'background-color'
]

def sanitize_html(content):
    css_sanitizer = CSSSanitizer(allowed_css_properties=allowed_styles)
    sanitized_content = bleach.clean(
        content,
        tags=allowed_tags,
        attributes=allowed_attributes,
        css_sanitizer=css_sanitizer,
        protocols=['https'],
        strip=False 
    )

    def filter_img_src(attrs, new=False):
        src = attrs.get('src', '')
        if src.startswith('https://mscarchive.s3.amazonaws.com/'):
            return attrs
        else:
            return None

    sanitized_content = bleach.linkify(sanitized_content, callbacks=[filter_img_src])

    return sanitized_content