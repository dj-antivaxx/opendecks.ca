def client_meta(request):
    xff = request.headers.get('X-Forwarded-For', '')
    vercel_ip = request.headers.get('x-vercel-forwarded-for') or request.headers.get('X-Real-IP')
    if vercel_ip:
        ip = vercel_ip.split(',')[0].strip()
    elif xff:
        ip = xff.split(',')[0].strip()
    else:
        ip = request.remote_addr or ''

    return {
        'ip': (ip or '')[:64],
        'user_agent': (request.headers.get('User-Agent') or '')[:512],
        'accept_language': (request.headers.get('Accept-Language') or '')[:128],
        'country': (request.headers.get('x-vercel-ip-country') or '')[:8],
        'region': (request.headers.get('x-vercel-ip-country-region') or '')[:32],
        'city': (request.headers.get('x-vercel-ip-city') or '')[:64],
    }
