FROM python:3.10-slim

WORKDIR /app

# Create a non-root user and group
RUN addgroup --system nonroot && adduser --system --ingroup nonroot nonroot

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Change ownership of the app directory to the new user
RUN chown -R nonroot:nonroot /app

# Switch to the non-root user
USER nonroot

EXPOSE 5001

CMD ["gunicorn", "--workers", "4", "--bind", "0.0.0.0:5001", "app:app"]
