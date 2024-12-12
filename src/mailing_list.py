import requests
import json
import base64

from datetime import datetime
from premailer import transform

def image_to_base64(image_path):
    with open(image_path, 'rb') as image_file:
        image_data = image_file.read()
        base64_string = base64.b64encode(image_data).decode('utf-8')
    return base64_string

def upload_image(image_path, image_name, mailchimp_url, headers):
    base64_image = image_to_base64(image_path)
    data = {'name': image_name, 'file_data': base64_image}
    endpoint = 'file-manager/files'
    response = requests.post(f'{mailchimp_url}{endpoint}', headers=headers, json=data)
    return response.json().get('id'), response.json().get('full_size_url')

def get_list_id(mailchimp_url, headers):
    lists_endpoint = 'lists'
    response = requests.get(f'{mailchimp_url}{lists_endpoint}', headers=headers)
    if response.status_code == 200:
        data = response.json()
    else:
        print(f'Error: {response.status_code}, {response.text}')
    return response.json().get('lists')[0].get('id')

def add_member_to_list(email, first_name, last_name, list_id, mailchimp_url, headers):
    members_endpoint = f'lists/{list_id}/members'
    data = {
        'email_address': email,
        'status': 'subscribed',  
        'merge_fields': {
            'FNAME': first_name,
            'LNAME': last_name
        }
    }
    response = requests.post(f'{mailchimp_url}{members_endpoint}', json=data, headers=headers)
    if response.status_code in (200, 201):
        print(f'Subscriber {email} added successfully!')
    else:
        print(f'Error adding subscriber: {response.status_code}, {response.text}') 

def send_welcome_email(api_key, data_center='us3', segment_tag='Welcome to the Open Decks!'):
    mailchimp_url = f'https://{data_center}.api.mailchimp.com/3.0/'
    headers = {
        'Authorization': f'Bearer {api_key}'
    }
    
    data = {
        'name': segment_tag,
        'static_segment': ['dj.antivaxx@gmail.com']
    }

    list_id = get_list_id(mailchimp_url, headers)
    segments_endpoint = f'lists/{list_id}/segments'
    
    response = requests.post(f'{mailchimp_url}{segments_endpoint}', json=data, headers=headers)
    try:
        segment_id = response.json()['id']
    except KeyError: # segment exists
        response = requests.get(f'{mailchimp_url}{segments_endpoint}', headers=headers, params={'count': 100, 'offset': 0})
        segments = response.json()['segments']
        # add emails to segment
        for seg in segments:
            if seg['name'] == segment_tag:
                segment_id = seg['id']

    campaigns_endpoint = 'campaigns'
    data = {
        'type': 'regular',
        'recipients': {
            'list_id': list_id,
            'segment_opts': {'saved_segment_id': segment_id}
        },
        'settings': {
            'subject_line': 'Welcome to the Open Decks!',
            'from_name': 'DJ Antivaxx',
            'reply_to': 'dj.antivaxx@gmail.com',
            'preview_text': ' Hello! Welcome to the open decks!',
        },
        'send_time': datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    response = requests.post(f'{mailchimp_url}{campaigns_endpoint}', data=json.dumps(data), headers=headers)
    
    if response.status_code in (200, 201):
        campaign_id = response.json()['id']
        print(f'Campaign created successfully with ID: {campaign_id}')
    else:
        print(f'Error creating campaign: {response.status_code}, {response.text}')

    with open('welcome_email.html', 'r') as f:
        html_content = transform(f.read())
    
    content_endpoint = f'campaigns/{campaign_id}/content'
    data = {
        'html': html_content
    }
    response = requests.put(f'{mailchimp_url}{content_endpoint}', json=data, headers=headers)
    
    send_endpoint = f'campaigns/{campaign_id}/actions/send'
    response = requests.post(f'{mailchimp_url}{send_endpoint}', headers=headers)

