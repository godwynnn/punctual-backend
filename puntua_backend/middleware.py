# from stores.models import Store

# class CurrentStoreMiddleware:

#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):

#         request.store = None
#         store_slug = request.headers.get('X-Tenant-slug')

#         if not store_slug:
#             host = request.get_host()
#             parts = host.split('.')
#             if len(parts) > 1:
#                 if 'localhost' in host or '127.0.0.1' in host:
#                     if not parts[0].startswith('localhost') and not parts[0].startswith('127'):
#                         store_slug = parts[0]
#                 else:
#                     if len(parts) > 2:
#                         first_part = parts[0]
#                         if first_part not in ['api', 'app', 'www']:
#                             store_slug = first_part

#         if store_slug:
#             try:
#                 request.store = Store.objects.get(slug=store_slug)
#             except Store.DoesNotExist:
#                 pass

#         if not request.store and request.user.is_authenticated:
#             request.store = request.user.stores.first()

#         return self.get_response(request)