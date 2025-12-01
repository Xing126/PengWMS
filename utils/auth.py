from userprofile.models import Users
from rest_framework.exceptions import AuthenticationFailed

class Authtication(object):
    def authenticate(self, request):
        if request.path in ['/api/docs/', '/api/debug/', '/api/']:
            return (False, None)
        else:
            token = request.META.get('HTTP_TOKEN')
            if token:
                if Users.objects.filter(openid__exact=str(token)).exists():
                    user = Users.objects.filter(openid__exact=str(token)).first()
                    return (True, user)
                else:
                    raise AuthenticationFailed({"detail": "User Does Not Exists"})
            else:
                raise AuthenticationFailed({"detail": "Please Add Token To Your Request Headers"})

    def authenticate_header(self, request):
        pass
