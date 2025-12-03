# X-RAG Troubleshooting Guide

This guide covers common issues and their solutions when working with X-RAG.

## Quick Diagnostics

Always start with these commands:

```bash
# Validate prerequisites and identify issues
make check

# Check cluster and pod status
make cluster-status

# View detailed pod information
kubectl get pods -n rag-system -o wide
```

## Common Issues

### Docker Issues

#### "Docker daemon not running"

**Symptom**: Commands fail with "Cannot connect to the Docker daemon"

**Solution**:
- macOS: Start Docker Desktop application
- Linux: `sudo systemctl start docker`

Verify with:
```bash
docker info
```

#### "Insufficient Docker resources"

**Symptom**: Pods stuck in Pending or cluster fails to start

**Solution**: Allocate more resources to Docker Desktop:
1. Open Docker Desktop → Settings → Resources
2. Set memory to at least **6GB** (recommended: 10GB)
3. Set CPUs to at least **4 cores** (recommended: 8)
4. Click "Apply & Restart"

Verify with:
```bash
make check
```

### Port Conflicts

#### "Port already in use"

**Symptom**: Services fail to start, error mentions port binding

**Solution**: Identify the process using the port:

```bash
# macOS
lsof -i :8080  # Replace with the conflicting port

# Linux
sudo netstat -tulpn | grep :8080
```

Then either stop the conflicting process or change the X-RAG port.

**Common port assignments**:
| Port | Service | Alternative |
|------|---------|-------------|
| 8080 | Search UI | Change in infra/k8s/search-ui/ |
| 8081 | Weaviate | Change in infra/k8s/weaviate/ |
| 8082 | Ingestion API | Change in infra/k8s/ingestion-api/ |
| 3000 | Grafana | Change in infra/k8s/monitoring/ |
| 9090 | Prometheus | Change in infra/k8s/monitoring/ |

### Cluster Issues

#### "Cluster not found"

**Symptom**: kubectl commands fail with "context not found"

**Solution**: The cluster hasn't been created yet:
```bash
make cluster-init   # Build images
make cluster-start  # Start cluster
```

#### Pods stuck in Pending

**Symptom**: `kubectl get pods` shows pods in Pending state

**Causes and solutions**:

1. **Insufficient resources**: Increase Docker resources (see above)
   ```bash
   kubectl describe pod <pod-name> -n rag-system
   # Look for "Insufficient cpu" or "Insufficient memory"
   ```

2. **Image pull issues**: Check image availability
   ```bash
   kubectl describe pod <pod-name> -n rag-system
   # Look for "ImagePullBackOff" or "ErrImagePull"

   # Rebuild and push images
   make cluster-init
   ```

3. **PVC issues**: Storage not available
   ```bash
   kubectl get pvc -n rag-system
   # Check for Pending PVCs
   ```

#### Pods in CrashLoopBackOff

**Symptom**: Pods repeatedly restart

**Solution**: Check pod logs for errors:
```bash
# View logs for the failing pod
kubectl logs <pod-name> -n rag-system

# Or use make target
make logs-<service>  # e.g., make logs-indexer

# View previous instance logs
kubectl logs <pod-name> -n rag-system --previous
```

Common causes:
- Missing environment variables (check secrets)
- Connection refused to dependencies (service not ready)
- Application configuration errors

### Service Connectivity

#### "Connection refused" between services

**Symptom**: Services can't communicate with each other

**Diagnostic steps**:

1. Check all services are running:
   ```bash
   kubectl get pods -n rag-system
   ```

2. Verify service endpoints:
   ```bash
   kubectl get svc -n rag-system
   kubectl get endpoints -n rag-system
   ```

3. Test connectivity from inside a pod:
   ```bash
   kubectl exec -it <pod-name> -n rag-system -- /bin/sh
   # Then try: wget -qO- http://service-name:port/health
   ```

#### Weaviate not responding

**Symptom**: Search fails with Weaviate connection errors

**Solution**:
```bash
# Check Weaviate pod status
kubectl get pods -n rag-system -l app=weaviate

# Check Weaviate logs
kubectl logs -l app=weaviate -n rag-system

# Restart Weaviate if needed
kubectl rollout restart deployment/weaviate -n rag-system
```

#### Kafka connectivity issues

**Symptom**: Indexer can't consume messages, ingestion stalls

**Solution**:
```bash
# Check Kafka pod
kubectl get pods -n rag-system -l app=kafka

# View Kafka logs
kubectl logs -l app=kafka -n rag-system

# Restart Kafka (note: may lose uncommitted messages)
kubectl rollout restart deployment/kafka -n rag-system
```

### Application Issues

#### Embeddings not generating

**Symptom**: Documents ingested but search returns no results

**Diagnostic steps**:

1. Check indexer logs:
   ```bash
   make logs-indexer
   ```

2. Check embedding service:
   ```bash
   make logs-embedding
   ```

3. Verify OpenAI API key is set:
   ```bash
   kubectl get secret openai-credentials -n rag-system -o yaml
   ```

4. Check embedding service health:
   ```bash
   kubectl exec -it <any-pod> -n rag-system -- \
     grpcurl -plaintext embedding-service:50051 grpc.health.v1.Health/Check
   ```

#### Search returns empty results

**Symptom**: Search works but returns no documents

**Causes**:

1. **Documents not indexed yet**: Check indexer logs
2. **Wrong namespace**: Ensure query namespace matches document namespace
3. **Weaviate collection empty**: Check Weaviate directly
   ```bash
   curl http://localhost:8081/v1/objects | jq '.totalResults'
   ```

## Log Analysis

### Viewing Service Logs

```bash
# Using make targets
make logs-search-ui
make logs-embedding
make logs-indexer
make logs-ingestion

# Using kubectl directly
kubectl logs -f deployment/<service> -n rag-system

# View logs with timestamps
kubectl logs -f deployment/<service> -n rag-system --timestamps

# View last N lines
kubectl logs deployment/<service> -n rag-system --tail=100
```

### Aggregating Logs

View logs from all pods of a service:
```bash
kubectl logs -l app=<service-name> -n rag-system --all-containers
```

## Recovery Procedures

### Restart a Single Service

```bash
kubectl rollout restart deployment/<service> -n rag-system
kubectl rollout status deployment/<service> -n rag-system
```

### Restart All Application Services

```bash
kubectl rollout restart deployment -n rag-system
```

### Full Cluster Reset

If nothing else works:
```bash
make cluster-clean   # Delete cluster and data
make cluster-init    # Rebuild images
make cluster-start   # Fresh start
```

### Preserve Data During Reset

```bash
make cluster-stop    # Stop but preserve data
make cluster-start   # Restart with existing data
```

## Getting Help

If you're still stuck:

1. Run `make check` and note any errors
2. Collect relevant logs: `kubectl logs -l app=<failing-service> -n rag-system`
3. Check pod events: `kubectl describe pod <pod-name> -n rag-system`
4. Review [AGENTS.md](../AGENTS.md) for known issues and fixes
5. See [KIND-ACCESS-CHEAT-SHEET.md](./KIND-ACCESS-CHEAT-SHEET.md) for advanced debugging

## FAQ

**Q: Why do I only see 4 containers in `docker ps`?**

A: That's correct! X-RAG uses Kind (Kubernetes in Docker). The 4 containers are the Kind cluster infrastructure (registry + control plane + 2 workers). Your actual services run as Kubernetes pods inside these containers. Use `kubectl get pods -n rag-system` to see them.

**Q: Can I run services locally instead of in Kubernetes?**

A: The project is designed to run entirely in Kubernetes for production parity. There are no `dev-*` targets for local development outside the cluster.

**Q: How do I access a service that's only available inside the cluster?**

A: Use port-forwarding:
```bash
kubectl port-forward svc/<service-name> <local-port>:<service-port> -n rag-system
```

**Q: Why is my OPENAI_API_KEY not working?**

A: Ensure the key is properly set in your `.env` file and the cluster was started after setting it. The key is read during `make cluster-start` and stored as a Kubernetes secret.
