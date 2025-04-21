# Whiteboard Capture System

A web application for capturing, storing, and managing whiteboard images. This application uses Flask, Cloudinary for image storage, and can be deployed on Render.

## Local Setup

1. Clone this repository
2. Create a `.env` file with your Cloudinary credentials:
   ```
   CLOUDINARY_CLOUD_NAME=your_cloud_name
   CLOUDINARY_API_KEY=your_api_key
   CLOUDINARY_API_SECRET=your_api_secret
   SECRET_KEY=random_secret_key_for_sessions
   ```
3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
4. Run the application:
   ```
   python main.py
   ```

## Deployment to Render

1. Create a new Web Service on Render
2. Connect your repository
3. Set the following configuration:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn main:app`
4. Add the following environment variables:
   - `CLOUDINARY_CLOUD_NAME`
   - `CLOUDINARY_API_KEY`
   - `CLOUDINARY_API_SECRET`
   - `SECRET_KEY` (a random string for session encryption)

## Raspberry Pi Image Capture

To set up image capture on a Raspberry Pi:

1. Install necessary dependencies:
   ```
   pip install requests pillow python-dotenv
   ```
2. Create a script to capture and upload images to your deployed application.

## Testing

- Test Cloudinary connection: `/test-cloudinary-page`
- Test image upload: `/test-upload`