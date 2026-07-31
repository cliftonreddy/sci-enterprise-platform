@echo off
cd /d "%~dp0"

set KUBECONFIG=%~dp0..\ucp-bundle\kube.yml
set KUBECTL_PATH=C:\Program Files\Docker\Docker\resources\bin\kubectl.exe
set PROMETHEUS_POD=ucp-metrics

echo KUBECONFIG=%KUBECONFIG%
echo Starting SCI backend...

"C:\Program Files\Python313\python.exe" backend\app.py
pause
