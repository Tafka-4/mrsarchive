import re
import base64
import requests
from io import BytesIO

def upload_episode_images_to_api(novel_id: int, episode: int, jwt_token: str, content: str):
    img_data_list = re.findall(r'<img src="data:image/(png|jpeg|webp|gif);base64,([^"]+)"', content)

    if not img_data_list: return

    headers = {
        'Authorization': f'Bearer {jwt_token}'
    }

    files = []
    for i, (img_type, img_data) in enumerate(img_data_list):
        img_data = base64.b64decode(img_data)   
        file = (f'image_{i}.{img_type}', BytesIO(img_data), f'image/{img_type}')
        files.append(('images', file))

    response = requests.post(f'http://api:5000/api/uploads/novel/{novel_id}/episode/{episode}/', headers=headers, files=files)

    return response

def upload_notice_images_to_api(novel_id: int, num: int, jwt_token: str, content: str):
    img_data_list = re.findall(r'<img src="data:image/(png|jpeg|webp|gif);base64,([^"]+)"', content)

    if not img_data_list: return

    headers = {
        'Authorization': f'Bearer {jwt_token}'
    }

    files = []
    for i, (img_type, img_data) in enumerate(img_data_list):
        img_data = base64.b64decode(img_data)   
        file = (f'image_{i}.{img_type}', BytesIO(img_data), f'image/{img_type}')
        files.append(('images', file))

    response = requests.post(f'http://api:5000/api/uploads/novel/{novel_id}/notice/{num}', headers=headers, files=files)

    return response