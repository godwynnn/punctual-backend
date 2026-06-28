from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from .serializers import RegisterSerializer, UserSerializer
from django.contrib.auth import get_user_model
from django.conf import settings
from social_django.utils import psa

# For Google ID token verification
from google.oauth2 import id_token as google_id_token
from google.auth.transport import requests as google_auth_requests
from django.contrib.auth import login, authenticate


User = get_user_model()

def get_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {
        'refresh': str(refresh),
        'access': str(refresh.access_token),
    }

class RegisterAPIView(generics.CreateAPIView):
    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        user_data = UserSerializer(user).data
        return Response({
            "message": "User created successfully",
            "user": user_data
        }, status=status.HTTP_201_CREATED)


class LoginAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        password = request.data.get('password')

        if not email or not password:
            return Response({'error': 'Please provide both email and password.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Invalid Email or password'}, status=status.HTTP_401_UNAUTHORIZED)
        
        # Check if user is active
        if not user.is_active:
            return Response({'error': 'Account deactivated'}, status=status.HTTP_401_UNAUTHORIZED)

        # Check if user has a usable password
        if not user.has_usable_password():
            return Response({'error': 'This email is associated with a social account. Please use Google Login.'}, status=status.HTTP_401_UNAUTHORIZED)

        # Authenticate
        if user.check_password(password):
            tokens = get_tokens_for_user(user)
            return Response({
                'status': 'success',
                'access': tokens['access'],
                'refresh': tokens['refresh'],
                'user': UserSerializer(user).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({'error': 'Invalid Email or password'}, status=status.HTTP_401_UNAUTHORIZED)

from rest_framework.decorators import api_view, permission_classes

@api_view(['POST'])
@permission_classes([AllowAny])
def logout_view(request):
    try:
        refresh_token = request.data.get('refresh')
        if refresh_token:
            token = RefreshToken(refresh_token)
            token.blacklist()
        return Response({'message': 'Successfully logged out.'}, status=status.HTTP_200_OK)
    except Exception:
        return Response({'message': 'Logged out.'}, status=status.HTTP_200_OK)

def verify_google_id_token(token):
    try:
        # We need the Google Client ID from settings
        client_id = getattr(settings, 'SOCIAL_AUTH_GOOGLE_OAUTH2_KEY', None)
        idinfo = google_id_token.verify_oauth2_token(
            token, google_auth_requests.Request(), client_id
        )
        return idinfo
    except Exception:
        return None



@api_view(["POST"])
@permission_classes([AllowAny])
@psa()
def VerifySocialLogin(request, backend):
    access_token = request.data.get("access_token")
    id_token = request.data.get("id_token")

    if access_token:
        token = access_token
        social_user = request.backend.do_auth(token)

        if not social_user:
            return Response(
                {"status": "failed", "error": "Invalid social token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # THIS is the Django user
        user = User.objects.get(email=social_user.email)

    elif id_token:
        idinfo = verify_google_id_token(id_token)
        if not idinfo:
            return Response(
                {"status": "failed", "error": "Invalid ID token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = idinfo.get("email")
        first_name = idinfo.get("given_name", "")
        last_name = idinfo.get("family_name", "")

        user, _ = User.objects.get_or_create(
            email=email,
            defaults={
                "username": str(email).split('@')[0],
                "first_name": first_name,
                "last_name": last_name
            },
        )

    else:
        return Response(
            {"status": "failed", "error": "No token provided"},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        # Explicitly activate
        if not user.is_active:
            user.is_active = True
            user.save(update_fields=["is_active"])
    
        #  SESSION AUTH (NO authenticate())
        login(
            request,
            user,
            backend="django.contrib.auth.backends.ModelBackend",
        )

        #  JWT TOKENS
        tokens = get_tokens_for_user(user)

        response = Response(
            {
                "status": "success",
                "tokens": {
                    "access_token": str(tokens["access"]),
                    "refresh_token": str(tokens["refresh"]),
                },
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

        return response
    
    except Exception as e:
        return Response(
            {"status": "failed", "error": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )






