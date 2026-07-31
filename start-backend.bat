@echo off
cd /d "C:\AmericanNational\DevSecOps\Green Software Applications\sci-carbon-dashboard"

set KUBECONFIG=C:\AmericanNational\DevSecOps\Green Software Applications\ucp-bundle-cliftonreddy\kube.yml
set KUBECTL_PATH=C:\Program Files\Docker\Docker\resources\bin\kubectl.exe
set PROMETHEUS_POD=ucp-metrics-7n2kc

echo KUBECONFIG=%KUBECONFIG%
echo Starting SCI backend...

"C:\Program Files\Python313\python.exe" backend\app.py
pause
