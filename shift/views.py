from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated

from organization.models import Organization
from .models import Shift
from .serializers import ShiftSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_shifts(request, org_id):
    try:
        organization = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        
    shifts = Shift.objects.filter(organization=organization).order_by('created_at')
    serializer = ShiftSerializer(shifts, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_shift(request, org_id):
    try:
        organization = Organization.objects.get(id=org_id)
    except Organization.DoesNotExist:
        return Response({'error': 'Organization not found.'}, status=status.HTTP_404_NOT_FOUND)
        
    # Check if the requesting user is the owner of the organization
    if organization.owner != request.user:
        return Response({'error': 'You do not have permission to manage shifts for this organization.'}, status=status.HTTP_403_FORBIDDEN)
        
    serializer = ShiftSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(organization=organization)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
