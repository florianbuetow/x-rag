# **Practical Guide for Working With Pods in kind (Kubernetes-in-Docker)**

This guide covers:

1. Copying files in/out of pods
2. Connecting to pods that have no shell
3. Opening debug ephemeral containers
4. Inspecting containerd inside kind nodes
5. Reaching services from outside kind (ingress, LoadBalancer, NodePort)

---

## **1. Copy Files In and Out of Pods**

### **Copy local → pod**

```bash
kubectl cp ./local-file.txt <namespace>/<pod-name>:/path/in/pod/
```

### **Copy pod → local**

```bash
kubectl cp <namespace>/<pod-name>:/path/in/pod/ ./local-dir/
```

### Notes

* Works even if the container has no shell.
* Use the correct container if the pod has multiple:

```bash
kubectl cp <namespace>/<pod-name>:<container>/<path> <local-path>
```

---

## **2. Connect to Pods That Have *No Shell***

Some containers (e.g., distroless, scratch) do not include `/bin/sh`.

### **Strategy A — Exec into a different container in the same pod**

If the pod has a “sidecar” with a shell:

```bash
kubectl exec -it <pod> -c <container-with-shell> -- sh
```

### **Strategy B — Run commands directly without interactive shell**

```bash
kubectl exec <pod> -- <binary> <args>
```

Example:

```bash
kubectl exec mypod -- /app/server --version
```

### **Strategy C — Attach a debug ephemeral container (best option)**

Use Kubernetes' ephemeral debug container feature.

---

## **3. Open a Debug Ephemeral Container**

Ephemeral containers give you a real shell (e.g., busybox or ubuntu) *inside the pod namespace*.

### **Start a debug container:**

```bash
kubectl debug -it <pod-name> --image=busybox --target=<container-name> -- sh
```

This attaches BusyBox into the pod’s namespaces (network, PID, etc.).

### **Example for a container with no shell:**

```bash
kubectl debug -it mypod --image=ubuntu --target=myapp -- bash
```

### **Inspect ephemeral containers**

```bash
kubectl describe pod <pod-name> | grep -A5 "Ephemeral Containers"
```

---

## **4. Inspect containerd Runtime Inside kind Nodes**

kind nodes are Docker containers running containerd inside.

### **List kind nodes**

```bash
docker ps --format '{{.Names}}'
```

Typically yields:

```
kind-control-plane
kind-worker
```

### **Exec into node**

```bash
docker exec -it kind-control-plane bash
```

### **List containerd containers (pods)**

```bash
ctr -n k8s.io containers ls
```

### **List tasks (running processes)**

```bash
ctr -n k8s.io tasks ls
```

### **Inspect a container**

```bash
ctr -n k8s.io containers info <container-id>
```

### **View logs of containerd**

```bash
journalctl -u containerd
```

### **Check CNI network inside node**

```bash
ls /etc/cni/net.d
```

### **View pod sandboxes**

```bash
crictl ps -a
```

If crictl is not installed, install it inside the node or run it externally with the right socket.

---

## **5. Accessing Services From Outside kind**

### **Option A — Use Port Forwarding (simple, good for local dev)**

```bash
kubectl port-forward svc/my-service 8080:80 -n <ns>
```

Access at:

```
http://localhost:8080
```

### **Option B — Use NodePort (direct access through Docker node IP)**

1. Patch your service:

```bash
kubectl patch svc my-service -n <ns> \
  -p '{"spec": {"type": "NodePort"}}'
```

2. Get assigned port:

```bash
kubectl get svc my-service -n <ns>
```

3. Get node IP:

```bash
docker inspect -f '{{range.NetworkSettings.Networks}}{{.IPAddress}}{{end}}' kind-control-plane
```

4. Access it:

```
http://<node-ip>:<node-port>
```

### **Option C — Install an Ingress Controller (recommended for real setups)**

Install NGINX ingress for kind:

```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/kind/deploy.yaml
```

This config is *specifically designed* to work with kind’s networking.

Create an Ingress:

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-app
spec:
  rules:
    - host: local.test
      http:
        paths:
          - path: /
            pathType: Prefix
            backend:
              service:
                name: my-service
                port:
                  number: 80
```

Then add to `/etc/hosts`:

```
127.0.0.1 local.test
```

Access:

```
http://local.test
```

### **Option D — Use MetalLB for LoadBalancer Support**

If you want `type: LoadBalancer` on kind:

Install MetalLB:

```bash
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.3/config/manifests/metallb-native.yaml
```

Define an IP range for MetalLB (example):

```yaml
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: pool1
  namespace: metallb-system
spec:
  addresses:
    - 172.18.0.200-172.18.0.250
```

(Make sure the IPs match your Docker bridge network.)

Enable a L2 advertisement:

```yaml
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: l2adv1
  namespace: metallb-system
```

Now `type: LoadBalancer` services work natively.

---

## **Summary Cheat Sheet**

| Task                            | Command / Method                         |
| ------------------------------- | ---------------------------------------- |
| Copy files into/out of pods     | `kubectl cp`                             |
| Connect to pods with no shell   | `kubectl debug` or direct exec           |
| Start ephemeral debug container | `kubectl debug`                          |
| Inspect containerd inside node  | `docker exec`, `ctr`, `crictl`           |
| Access services externally      | port-forward, NodePort, Ingress, MetalLB |
