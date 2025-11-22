"""
Minimal test function to verify Vercel Python runtime works
"""

def handler(request):
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
        },
        'body': '{"status": "ok", "message": "Python is working!"}'
    }
