from rest_framework.throttling import UserRateThrottle, AnonRateThrottle

class AnonymousUserThrottle(AnonRateThrottle):
    rate = '150/hour'


class AuthenticatedUserThrottle(UserRateThrottle):
    rate = '1500/hour'


class PhotoUploadThrottle(UserRateThrottle):
    scope = 'photo_upload'
    rate = '20/hour'


class PhotoViewThrottle(UserRateThrottle):
    scope = 'photo_view'
    rate = '2000/hour'