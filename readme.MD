# Photo Album API

A Django REST Framework API for managing users, photos with visibility options and albums. Supports full CRUD operations with JWT authentication.

## Setup

1. Clone the repository
2. Create and activate virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate   # Linux/Mac
   venv\Scripts\activate      # Windows

#install dependencies
pip install -r requirements.txt

#run migrations
python manage.py migrate

#run server
python manage.py runserver

AUTHORIZATION 
- Register: POST /api/core/register/
- Login: POST /api/core/login/
- Refresh token: POST /api/core/refresh/
Uses JWT. Include Authorization: Bearer <access_token> in protected requests.

PHOTOS
- Upload photo: POST /api/photos/ (multipart/form-data)
- List photos: GET /api/photos/
- A photo: GET /api/photos/1/


ALBUMS
- Create album: POST /api/albums/
- Update album: PATCH /api/albums/<id>/
- List albums: GET /api/albums/
- Get album details: GET /api/albums/<id>/
- Add photo to album: POST /api/albums/<id>/add_photo/
- Remove photo from album: POST /api/albums/<id>/remove_photo/
- List my albums: GET /api/albums/my_albums/
- Flag inappropriate album (admin only): POST /api/albums/<id>/flag_inappropriate/

Before you go
- Success: 200 OK or 201 Created
- Unauthorized: 401 Unauthorized
- Forbidden: 403 Forbidden
- Validation errors: 400 Bad Request

TAKE NOTE!
- Users can only add their own photos to albums.
- Albums are private to owners unless flagged by admin.
- Admin can delete inappropriate albums.


