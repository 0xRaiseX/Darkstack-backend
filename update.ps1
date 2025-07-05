# Step 1: Build Docker image
docker build -t darkstack_backend:latest C:\dev\MSaaS\interface\darkstack_backend

# Step 2: Load image into kind cluster
kind load docker-image darkstack_backend:latest

# Step 3: Restart deployment to use the new image
kubectl rollout restart deployment fastapi-deployment
