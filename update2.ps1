# Step 1: Build Docker image
docker build -t k8s-manager:latest C:\dev\MSaaS\interface\k8s-manager\

# Step 2: Load image into kind cluster
kind load docker-image k8s-manager:latest

# Step 3: Restart deployment to use the new image
kubectl rollout restart deployment k8s-manager-app
