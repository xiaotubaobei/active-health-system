FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt psycopg2-binary
COPY backend /app/backend
COPY data/fitness_scales /app/data/fitness_scales
COPY data/prescription_templates /app/data/prescription_templates
COPY scripts/set_user_role.py /app/scripts/set_user_role.py
RUN mkdir -p /app/storage /app/uploads
WORKDIR /app/backend
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
